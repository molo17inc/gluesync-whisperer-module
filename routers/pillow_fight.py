#!/usr/bin/env python3
"""
 * This file is part of Gluesync Whisperer.
 *
 * Gluesync Whisperer is dual-licensed under the following licenses:
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

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from models import DatabaseType, OperationType, ConnectionStatus
from schemas import TableOperationRequest
from services.pillow_fight_service import PillowFightService
from services.connection_service import ConnectionService
from services.table_service import TableService

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pillow-fight", tags=["pillow-fight"])

# Store active pillow fights
active_pillow_fights: Dict[str, PillowFightService] = {}

# Schema for pillow fight response
class PillowFightResponse(BaseModel):
    connection_id: int
    table_ids: List[int]
    operation_types: List[str]
    operation_delay: float
    batch_size: int
    fight_ids: List[str]
    message: str

# Schema for pillow fight status
class PillowFightStatusItem(BaseModel):
    fight_id: str
    connection_id: int
    table_id: int
    table_name: str  # Keep table_name for display purposes
    operation_types: List[str]
    operation_delay: float
    batch_size: int
    start_time: Optional[str] = None
    last_operation_time: Optional[str] = None
    status: str
    operations: Dict[str, int]
    duration: Optional[float] = None

class PillowFightStatusResponse(BaseModel):
    pillow_fights: List[PillowFightStatusItem]

@router.post("/start", response_model=PillowFightResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_pillow_fight(
    request: TableOperationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a pillow fight (automated operations) on tables."""
    connection_service = ConnectionService(db)
    table_service = TableService(db)
    connection = connection_service.get_connection(request.connection_id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with id {request.connection_id} not found"
        )
    
    # Convert operation_type to a list of operations
    operations = []
    if request.operation_type == OperationType.INSERT:
        operations = ["insert"]
    elif request.operation_type == OperationType.UPDATE:
        operations = ["update"]
    elif request.operation_type == OperationType.DELETE:
        operations = ["delete"]
    else:  # ALL
        operations = ["insert", "update", "delete"]
    
    # Update connection status
    connection_service.update_connection_status(
        connection_id=connection.id,
        status=ConnectionStatus.BUSY
    )
    
    # Initialize pillow fight service
    pillow_fight = PillowFightService(
        db_type=connection.db_type,
        host=connection.host,
        port=connection.port,
        database=connection.database_name,
        username=connection.username,
        password=connection.password,
        operation_types=operations,
        operation_delay=request.operation_delay,
        batch_size=request.batch_size
    )
    
    # Register the pillow fight
    fight_ids = []
    table_ids_found = []
    
    for table_id in request.table_ids:
        # Get table config from database
        table_config = table_service.get_table(table_id)
        if not table_config:
            logger.warning(f"Table with ID {table_id} not found, skipping")
            continue
            
        if table_config.connection_id != connection.id:
            logger.warning(f"Table with ID {table_id} does not belong to connection {connection.id}, skipping")
            continue
            
        table_name = table_config.table_name
        fight_id = f"{connection.id}_{table_id}"
        
        # Stop existing pillow fight if running
        if fight_id in active_pillow_fights:
            await active_pillow_fights[fight_id].stop_pillow_fight(table_name)
        
        # Store the pillow fight service
        active_pillow_fights[fight_id] = pillow_fight
        
        # Start new pillow fight
        background_tasks.add_task(
            pillow_fight.start_pillow_fight,
            table_name=table_name,
            on_complete=lambda: pillow_fight_complete(fight_id, connection.id)
        )
        
        fight_ids.append(fight_id)
        table_ids_found.append(table_id)
    
    if not table_ids_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No valid tables found for the provided table IDs"
        )
    
    return PillowFightResponse(
        connection_id=connection.id,
        table_ids=table_ids_found,
        operation_types=operations,
        operation_delay=request.operation_delay,
        batch_size=request.batch_size,
        fight_ids=fight_ids,
        message=f"Started pillow fight for {len(table_ids_found)} tables"
    )


@router.post("/stop/{connection_id}/{table_id}", status_code=status.HTTP_200_OK)
async def stop_pillow_fight(
    connection_id: int,
    table_id: int,
    db: Session = Depends(get_db)
):
    """Stop a pillow fight for a specific table."""
    fight_id = f"{connection_id}_{table_id}"
    
    if fight_id not in active_pillow_fights:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active pillow fight found for table ID {table_id}"
        )
    
    # Get table name for the table ID
    table_service = TableService(db)
    table_config = table_service.get_table(table_id)
    
    if not table_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table with ID {table_id} not found"
        )
        
    table_name = table_config.table_name
    pillow_fight = active_pillow_fights[fight_id]
    await pillow_fight.stop_pillow_fight(table_name)
    
    # Check if there are any other pillow fights for this connection
    connection_fights = [fid for fid in active_pillow_fights.keys() if fid.startswith(f"{connection_id}_")]
    
    # If no other pillow fights are running for this connection, update status
    if not connection_fights:
        connection_service = ConnectionService(db)
        connection_service.update_connection_status(
            connection_id=connection_id,
            status=ConnectionStatus.CONNECTED
        )
    
    return {"message": f"Stopped pillow fight for table {table_name}"}


@router.post("/stop/all", status_code=status.HTTP_200_OK)
async def stop_all_pillow_fights(db: Session = Depends(get_db)):
    """Stop all running pillow fights."""
    connection_ids = set()
    table_service = TableService(db)
    
    # Stop all pillow fights
    for fight_id in list(active_pillow_fights.keys()):
        connection_id, table_id_str = fight_id.split("_", 1)
        connection_ids.add(int(connection_id))
        
        try:
            # Convert table_id from string to int
            table_id = int(table_id_str)
            
            # Look up the table info from the database
            table_config = table_service.get_table(table_id)
            if not table_config:
                logger.warning(f"Table with ID {table_id} not found when stopping all pillow fights")
                continue
                
            table_name = table_config.table_name
            pillow_fight = active_pillow_fights[fight_id]
            await pillow_fight.stop_pillow_fight(table_name)
        except Exception as e:
            logger.error(f"Error stopping pillow fight {fight_id}: {str(e)}")
    
    # Update all connections to CONNECTED
    connection_service = ConnectionService(db)
    for connection_id in connection_ids:
        connection_service.update_connection_status(
            connection_id=connection_id,
            status=ConnectionStatus.CONNECTED
        )
    
    return {"message": f"Stopped all pillow fights ({len(active_pillow_fights)} total)"}


@router.get("/status", response_model=PillowFightStatusResponse, status_code=status.HTTP_200_OK)
async def get_pillow_fight_status(db: Session = Depends(get_db)):
    """Get status of all running pillow fights."""
    status_items = []
    table_service = TableService(db)
    
    for fight_id, pillow_fight in active_pillow_fights.items():
        connection_id, table_id_str = fight_id.split("_", 1)
        
        try:
            # Convert table_id from string to int
            table_id = int(table_id_str)
            
            # Look up the table info from the database
            table_config = table_service.get_table(table_id)
            if not table_config:
                logger.warning(f"Table with ID {table_id} not found, skipping status")
                continue
                
            table_name = table_config.table_name
            stats = pillow_fight.get_stats(table_name)
            
            start_time = stats.get("start_time")
            last_operation_time = stats.get("last_operation_time")
            
            status_items.append(PillowFightStatusItem(
                fight_id=fight_id,
                connection_id=int(connection_id),
                table_id=table_id,
                table_name=table_name,
                operation_types=pillow_fight.operation_types,
                operation_delay=pillow_fight.operation_delay,
                batch_size=pillow_fight.batch_size,
                start_time=start_time.isoformat() if start_time else None,
                last_operation_time=last_operation_time.isoformat() if last_operation_time else None,
                status=stats.get("status", "unknown"),
                operations=stats.get("operations", {"insert": 0, "update": 0, "delete": 0}),
                duration=stats.get("duration")
            ))
        except Exception as e:
            logger.error(f"Error processing fight_id {fight_id}: {str(e)}")
    
    return PillowFightStatusResponse(pillow_fights=status_items)


def pillow_fight_complete(fight_id: str, connection_id: int):
    """Callback when a pillow fight is complete."""
    if fight_id in active_pillow_fights:
        del active_pillow_fights[fight_id]
    
    # Check if there are any other pillow fights for this connection
    connection_fights = [fid for fid in active_pillow_fights.keys() if fid.startswith(f"{connection_id}_")]
    
    # If no other pillow fights are running for this connection, update status
    if not connection_fights:
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
