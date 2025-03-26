#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is dual-licensed under the following licenses:
 *
 * 1. GNU General Public License (GPL) Version 3
 *    You may use, modify, and distribute this software under the terms of the GPL v3.
 *    See the LICENSE-GPL file or <http://www.gnu.org/licenses/gpl-3.0.html> for details.
 *    This option is available at no cost, but any derivative works must also be licensed under GPL v3.
 *
 * 2. MOLO17 Commercial License
 *    Alternatively, you may use this software under the MOLO17 Commercial License,
 *    which includes a warranty and permits proprietary use. Contact MOLO17 at info@molo17.com
 *    for licensing terms and conditions.
 *
 * You must choose one of these licenses to use this software. Using this software implies
 * acceptance of one of these licenses. See the accompanying LICENSE files or contact
 * MOLO17 for more information.
 *
 * Copyright (C) 2025 MOLO17. All rights reserved.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import DatabaseType, OperationType, ConnectionStatus
from schemas import (
    TableOperationRequest, 
    DatabaseConnectionResponse, 
    TableConfigResponse,
    ConnectionTestResponse,
    TableListResponse,
    TableSchemaResponse
)
from services.automator_service import AutomatorService
from services.connection_service import ConnectionService

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])

# Store active automation tasks
active_automations: Dict[str, AutomatorService] = {}

@router.post("/connections/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_request: TableOperationRequest,
    db: Session = Depends(get_db)
):
    """Test a database connection without saving it"""
    connection_service = ConnectionService(db)
    connection = connection_service.get_connection(connection_request.connection_id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id {connection_request.connection_id} not found"
        )
    
    from services.database_service import DatabaseService
    db_service = DatabaseService(db)
    automator = AutomatorService(db=db)
    
    success, message = await automator.test_connection()
    return ConnectionTestResponse(success=success, message=message)


@router.get("/connections/{connection_id}/tables", response_model=TableListResponse)
async def list_tables(
    connection_id: int,
    db: Session = Depends(get_db)
):
    """List all tables for a connection"""
    connection_service = ConnectionService(db)
    connection = connection_service.get_connection(connection_id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id {connection_id} not found"
        )
    
    from services.database_service import DatabaseService
    db_service = DatabaseService(db)
    automator = AutomatorService(db=db)
    
    tables = await automator.list_tables(connection_id=connection_id)
    return TableListResponse(tables=tables)


@router.get("/connections/{connection_id}/tables/{table_name}/schema", response_model=TableSchemaResponse)
async def get_table_schema(
    connection_id: int,
    table_name: str,
    db: Session = Depends(get_db)
):
    """Get schema for a specific table"""
    connection_service = ConnectionService(db)
    connection = connection_service.get_connection(connection_id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id {connection_id} not found"
        )
    
    from services.database_service import DatabaseService
    db_service = DatabaseService(db)
    automator = AutomatorService(db=db)
    
    schema = await automator.get_table_schema(table_name)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table {table_name} not found"
        )
    
    return TableSchemaResponse(
        table_name=table_name,
        columns=schema["columns"],
        primary_keys=schema["primary_keys"]
    )


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_automation(
    request: TableOperationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start database automation for specified tables"""
    connection_service = ConnectionService(db)
    connection = connection_service.get_connection(request.connection_id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id {request.connection_id} not found"
        )
    
    # Update connection status
    connection_service.update_connection_status(
        connection_id=connection.id,
        status=ConnectionStatus.BUSY
    )
    
    # Initialize automator service
    automator = AutomatorService(
        db_type=connection.db_type,
        host=connection.host,
        port=connection.port,
        database=connection.database_name,
        username=connection.username,
        password=connection.password,
        operation_type=request.operation_type,
        operation_delay=request.operation_delay,
        batch_size=request.batch_size
    )
    
    # Register the automation tasks
    for table_name in request.table_names:
        automation_id = f"{connection.id}_{table_name}"
        
        # Stop existing automation if running
        if automation_id in active_automations:
            await stop_automation_task(automation_id)
        
        # Start new automation
        active_automations[automation_id] = automator
        background_tasks.add_task(
            automator.run_automation,
            table_name=table_name,
            on_complete=lambda: automation_complete(automation_id, connection.id)
        )
    
    return {
        "message": f"Started automation for {len(request.table_names)} tables",
        "connection_id": connection.id,
        "tables": request.table_names,
        "automation_ids": [f"{connection.id}_{table}" for table in request.table_names]
    }


@router.post("/stop/{connection_id}/{table_name}", status_code=status.HTTP_200_OK)
async def stop_automation(
    connection_id: int,
    table_name: str,
    db: Session = Depends(get_db)
):
    """Stop automation for a specific table"""
    automation_id = f"{connection_id}_{table_name}"
    
    if automation_id not in active_automations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active automation found for table {table_name}"
        )
    
    await stop_automation_task(automation_id)
    
    # Check if there are any other automations for this connection
    connection_automations = [aid for aid in active_automations.keys() if aid.startswith(f"{connection_id}_")]
    
    # If no other automations are running for this connection, update status
    if not connection_automations:
        connection_service = ConnectionService(db)
        connection_service.update_connection_status(
            connection_id=connection_id,
            status=ConnectionStatus.CONNECTED
        )
    
    return {"message": f"Stopped automation for table {table_name}"}


@router.post("/stop/all", status_code=status.HTTP_200_OK)
async def stop_all_automations(db: Session = Depends(get_db)):
    """Stop all running automations"""
    for automation_id in list(active_automations.keys()):
        await stop_automation_task(automation_id)
    
    # Update all busy connections to connected
    connection_service = ConnectionService(db)
    connection_service.update_all_busy_connections(ConnectionStatus.CONNECTED)
    
    return {"message": "Stopped all automations"}


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_automation_status():
    """Get status of all running automations"""
    automations = []
    
    for automation_id, automator in active_automations.items():
        connection_id, table_name = automation_id.split("_", 1)
        stats = automator.get_stats(table_name)
        
        automations.append({
            "automation_id": automation_id,
            "connection_id": int(connection_id),
            "table_name": table_name,
            "operation_type": automator.operation_type.value,
            "operation_delay": automator.operation_delay,
            "batch_size": automator.batch_size,
            "stats": stats
        })
    
    return {"automations": automations}


async def stop_automation_task(automation_id: str):
    """Helper function to stop an automation task"""
    if automation_id in active_automations:
        automator = active_automations[automation_id]
        await automator.stop_automation()
        del active_automations[automation_id]


def automation_complete(automation_id: str, connection_id: int):
    """Callback when automation is complete"""
    if automation_id in active_automations:
        del active_automations[automation_id]
    
    # Check if there are any other automations for this connection
    connection_automations = [aid for aid in active_automations.keys() if aid.startswith(f"{connection_id}_")]
    
    # If no other automations are running for this connection, update status
    if not connection_automations:
        # Need to create a new DB session since this is called from a background task
        from database import SessionLocal
        db = SessionLocal()
        try:
            connection_service = ConnectionService(db)
            connection_service.update_connection_status(
                connection_id=connection_id,
                status=ConnectionStatus.CONNECTED
            )
        finally:
            db.close()
