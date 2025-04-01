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
import time
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
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
    status: str
    fight_id: str

# Schema for pillow fight status
class PillowFightStatusItem(BaseModel):
    fight_id: str
    connection_id: int
    table_id: int
    table_name: str
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

@router.post("/start", response_model=PillowFightResponse)
def start_pillow_fight(
    request: TableOperationRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Start a pillow fight (automated operations) on tables."""
    try:
        # Get the connection service
        connection_service = ConnectionService(db)
        table_service = TableService(db)
        
        # Check if connection exists
        connection = connection_service.get_connection(request.connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {request.connection_id} not found"
            )
        
        # Check if tables exist
        table_ids = request.table_ids if hasattr(request, 'table_ids') else []
        if not table_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No table IDs provided"
            )
        
        tables = []
        for table_id in table_ids:
            table = table_service.get_table(table_id)
            if not table:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table with ID {table_id} not found"
                )
            tables.append(table)
        
        # Check operation types
        operation_types = request.operation_types if hasattr(request, 'operation_types') else ["INSERT", "UPDATE", "DELETE"]
        valid_operation_types = [op.value for op in OperationType]
        valid_operation_types_upper = [op.upper() for op in valid_operation_types]
        
        # Normalize operation types to lowercase for comparison
        normalized_operation_types = []
        for op_type in operation_types:
            if op_type.upper() in valid_operation_types_upper:
                # Find the corresponding enum value
                index = valid_operation_types_upper.index(op_type.upper())
                normalized_operation_types.append(valid_operation_types[index])
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operation type: {op_type}"
                )
        
        # Replace the original operation_types with normalized ones
        operation_types = normalized_operation_types
        
        # Create a unique ID for this pillow fight
        fight_id = f"{request.connection_id}_{'-'.join(map(str, table_ids))}"
        
        # Check if pillow fight is already running
        if fight_id in active_pillow_fights:
            return PillowFightResponse(
                connection_id=request.connection_id,
                table_ids=table_ids,
                operation_types=operation_types,
                operation_delay=request.operation_delay if hasattr(request, 'operation_delay') else 1.0,
                batch_size=request.batch_size if hasattr(request, 'batch_size') else 1,
                status="already_running",
                fight_id=fight_id
            )
        
        # Create a new pillow fight service
        pillow_fight_service = PillowFightService(db)
        
        # Start the pillow fight
        pillow_fight_service.start_pillow_fight(
            connection_id=request.connection_id,
            table_ids=table_ids,
            operation_types=operation_types,
            operation_delay=request.operation_delay if hasattr(request, 'operation_delay') else 1.0,
            batch_size=request.batch_size if hasattr(request, 'batch_size') else 1
        )
        
        # Store the pillow fight
        active_pillow_fights[fight_id] = pillow_fight_service
        
        # Add a background task to check when pillow fight is complete
        background_tasks.add_task(
            pillow_fight_complete,
            fight_id,
            request.connection_id
        )
        
        return PillowFightResponse(
            connection_id=request.connection_id,
            table_ids=table_ids,
            operation_types=operation_types,
            operation_delay=request.operation_delay if hasattr(request, 'operation_delay') else 1.0,
            batch_size=request.batch_size if hasattr(request, 'batch_size') else 1,
            status="started",
            fight_id=fight_id
        )
    except Exception as e:
        logger.error(f"Error starting pillow fight: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting pillow fight: {str(e)}"
        )

@router.post("/stop/{connection_id}/{table_id}", status_code=status.HTTP_202_ACCEPTED)
def stop_pillow_fight(
    connection_id: int,
    table_id: int,
    db = Depends(get_db)
):
    """Stop a pillow fight for a specific table."""
    try:
        # Create the fight ID
        fight_id = f"{connection_id}_{table_id}"
        
        # Check if pillow fight is running
        if fight_id not in active_pillow_fights:
            return {
                "status": "not_running",
                "message": f"Pillow fight for connection {connection_id} and table {table_id} is not running"
            }
        
        # Stop the pillow fight
        pillow_fight_service = active_pillow_fights[fight_id]
        pillow_fight_service.stop_pillow_fight(connection_id, table_id)
        
        # Remove from active pillow fights
        del active_pillow_fights[fight_id]
        
        # Update the connection status
        connection_service = ConnectionService(db)
        connection = connection_service.get_connection(connection_id)
        if connection:
            # Use string value 'idle' instead of enum to avoid 'str' object has no attribute 'value' error
            connection.status = "idle"
            connection_service.update_connection(connection_id, connection)
        
        return {
            "status": "stopped",
            "message": f"Pillow fight stopped for connection {connection_id} and table {table_id}"
        }
    except Exception as e:
        logger.error(f"Error stopping pillow fight: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping pillow fight: {str(e)}"
        )

@router.post("/stop-all", status_code=status.HTTP_202_ACCEPTED)
def stop_all_pillow_fights(db = Depends(get_db)):
    """Stop all running pillow fights."""
    try:
        # Stop all pillow fights
        for fight_id, pillow_fight_service in active_pillow_fights.items():
            try:
                # Parse the fight ID
                parts = fight_id.split('_')
                if len(parts) >= 2:
                    connection_id = int(parts[0])
                    table_id = int(parts[1])
                    
                    # Stop the pillow fight
                    pillow_fight_service.stop_pillow_fight(connection_id, table_id)
                    
                    # Update the connection status
                    connection_service = ConnectionService(db)
                    connection = connection_service.get_connection(connection_id)
                    if connection:
                        # Use string value 'idle' instead of enum to avoid 'str' object has no attribute 'value' error
                        connection.status = "idle"
                        connection_service.update_connection(connection_id, connection)
            except Exception as e:
                logger.error(f"Error stopping pillow fight {fight_id}: {str(e)}")
        
        # Clear active pillow fights
        active_pillow_fights.clear()
        
        return {
            "status": "stopped",
            "message": "All pillow fights stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping all pillow fights: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping all pillow fights: {str(e)}"
        )

@router.get("/status", response_model=PillowFightStatusResponse)
def get_pillow_fight_status(db = Depends(get_db)):
    """Get status of all running pillow fights."""
    try:
        # Get status of all pillow fights
        status_items = []
        table_service = TableService(db)
        
        for fight_id, pillow_fight_service in active_pillow_fights.items():
            try:
                # Parse the fight ID
                parts = fight_id.split('_')
                if len(parts) >= 2:
                    connection_id = int(parts[0])
                    table_id = int(parts[1])
                    
                    # Get the table
                    table = table_service.get_table(table_id)
                    if not table:
                        continue
                    
                    # Get the status
                    status = pillow_fight_service.get_status(connection_id, table_id)
                    if status:
                        status_item = PillowFightStatusItem(
                            fight_id=fight_id,
                            connection_id=connection_id,
                            table_id=table_id,
                            table_name=table.table_name,
                            operation_types=status.get("operation_types", []),
                            operation_delay=status.get("operation_delay", 1.0),
                            batch_size=status.get("batch_size", 1),
                            start_time=status.get("start_time"),
                            last_operation_time=status.get("last_operation_time"),
                            status=status.get("status", "unknown"),
                            operations=status.get("operations", {}),
                            duration=status.get("duration")
                        )
                        status_items.append(status_item)
            except Exception as e:
                logger.error(f"Error getting status for pillow fight {fight_id}: {str(e)}")
        
        return PillowFightStatusResponse(pillow_fights=status_items)
    except Exception as e:
        logger.error(f"Error getting pillow fight status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pillow fight status: {str(e)}"
        )

def pillow_fight_complete(fight_id: str, connection_id: int):
    """Callback when a pillow fight is complete."""
    try:
        # Add a delay to allow the pillow fight to start properly
        time.sleep(5)
        
        # Check if pillow fight is still running
        if fight_id not in active_pillow_fights:
            return
        
        # Get the pillow fight service
        pillow_fight_service = active_pillow_fights[fight_id]
        
        # Check if the connection is still running
        db = get_db()
        connection_service = ConnectionService(db)
        connection = connection_service.get_connection(connection_id)
        
        # Only stop the pillow fight if the connection is explicitly stopped or deleted
        if not connection or connection.status == "stopped":
            # Stop the pillow fight
            parts = fight_id.split('_')
            if len(parts) >= 2:
                table_id = int(parts[1])
                pillow_fight_service.stop_pillow_fight(connection_id, table_id)
            
            # Remove from active pillow fights
            del active_pillow_fights[fight_id]
            logger.info(f"Pillow fight {fight_id} completed")
        else:
            # If the connection is still active, schedule another check later
            # This creates a recurring check without stopping the pillow fight prematurely
            background_tasks = BackgroundTasks()
            background_tasks.add_task(pillow_fight_complete, fight_id, connection_id)
            logger.info(f"Pillow fight {fight_id} still running, scheduling another check")
    except Exception as e:
        logger.error(f"Error in pillow fight complete callback: {str(e)}")
