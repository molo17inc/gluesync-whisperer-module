#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Database Automator is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Database Automator.  If not, see <http://www.gnu.org/licenses/>.
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

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pillow-fight", tags=["pillow-fight"])

# Store active pillow fights
active_pillow_fights: Dict[str, PillowFightService] = {}

# Schema for pillow fight response
class PillowFightResponse(BaseModel):
    connection_id: int
    tables: List[str]
    operation_types: List[str]
    operation_delay: float
    batch_size: int
    fight_ids: List[str]
    message: str

# Schema for pillow fight status
class PillowFightStatusItem(BaseModel):
    fight_id: str
    connection_id: int
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

@router.post("/start", response_model=PillowFightResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_pillow_fight(
    request: TableOperationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a pillow fight (automated operations) on tables."""
    connection_service = ConnectionService(db)
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
    for table_name in request.table_names:
        fight_id = f"{connection.id}_{table_name}"
        
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
    
    return PillowFightResponse(
        connection_id=connection.id,
        tables=request.table_names,
        operation_types=operations,
        operation_delay=request.operation_delay,
        batch_size=request.batch_size,
        fight_ids=fight_ids,
        message=f"Started pillow fight for {len(request.table_names)} tables"
    )


@router.post("/stop/{connection_id}/{table_name}", status_code=status.HTTP_200_OK)
async def stop_pillow_fight(
    connection_id: int,
    table_name: str,
    db: Session = Depends(get_db)
):
    """Stop a pillow fight for a specific table."""
    fight_id = f"{connection_id}_{table_name}"
    
    if fight_id not in active_pillow_fights:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active pillow fight found for table {table_name}"
        )
    
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
    
    # Stop all pillow fights
    for fight_id in list(active_pillow_fights.keys()):
        connection_id, table_name = fight_id.split("_", 1)
        connection_ids.add(int(connection_id))
        
        pillow_fight = active_pillow_fights[fight_id]
        await pillow_fight.stop_pillow_fight(table_name)
    
    # Update all connections to CONNECTED
    connection_service = ConnectionService(db)
    for connection_id in connection_ids:
        connection_service.update_connection_status(
            connection_id=connection_id,
            status=ConnectionStatus.CONNECTED
        )
    
    return {"message": f"Stopped all pillow fights ({len(active_pillow_fights)} total)"}


@router.get("/status", response_model=PillowFightStatusResponse, status_code=status.HTTP_200_OK)
async def get_pillow_fight_status():
    """Get status of all running pillow fights."""
    status_items = []
    
    for fight_id, pillow_fight in active_pillow_fights.items():
        connection_id, table_name = fight_id.split("_", 1)
        stats = pillow_fight.get_stats(table_name)
        
        start_time = stats.get("start_time")
        last_operation_time = stats.get("last_operation_time")
        
        status_items.append(PillowFightStatusItem(
            fight_id=fight_id,
            connection_id=int(connection_id),
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
