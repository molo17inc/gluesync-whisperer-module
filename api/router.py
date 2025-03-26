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
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import DatabaseConnection, ConnectionStatus
from schemas import (
    DatabaseConnectionCreate, 
    DatabaseConnectionUpdate, 
    DatabaseConnectionResponse,
    ConnectionStatusUpdate,
    ConnectionTestResponse
)
from services.database_service import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["connections"])

# Database connection routes
@router.post("/connections", response_model=DatabaseConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(connection: DatabaseConnectionCreate, db: Session = Depends(get_db)):
    """Create a new database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection with the same name already exists
    existing_connection = db_service.get_connection_by_name(connection.name)
    if existing_connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection with name '{connection.name}' already exists"
        )
    
    # Create connection
    try:
        new_connection = db_service.create_connection(connection)
        return new_connection
    except Exception as e:
        logger.error(f"Error creating connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating connection: {str(e)}"
        )


@router.get("/connections", response_model=List[DatabaseConnectionResponse])
def get_connections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all database connections."""
    db_service = DatabaseService(db)
    connections = db_service.get_connections(skip=skip, limit=limit)
    return connections


@router.get("/connections/{connection_id}", response_model=DatabaseConnectionResponse)
def get_connection(connection_id: int, db: Session = Depends(get_db)):
    """Get a specific database connection by ID."""
    db_service = DatabaseService(db)
    connection = db_service.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    return connection


@router.put("/connections/{connection_id}", response_model=DatabaseConnectionResponse)
def update_connection(
    connection_id: int, 
    connection_update: DatabaseConnectionUpdate, 
    db: Session = Depends(get_db)
):
    """Update a database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Update connection
    try:
        updated_connection = db_service.update_connection(connection_id, connection_update)
        return updated_connection
    except Exception as e:
        logger.error(f"Error updating connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating connection: {str(e)}"
        )


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    """Delete a database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Check if connection is running
    if existing_connection.status == ConnectionStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a connection that is currently running. Please stop it first."
        )
    
    # Delete connection
    try:
        db_service.delete_connection(connection_id)
        return None
    except Exception as e:
        logger.error(f"Error deleting connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting connection: {str(e)}"
        )


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
def test_connection(connection_id: int, db: Session = Depends(get_db)):
    """Test a database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Test connection
    try:
        result = db_service.test_connection(connection_id)
        return result
    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}")
        return ConnectionTestResponse(success=False, message=str(e))


@router.get("/connections/{connection_id}/tables", response_model=List[str])
def get_tables(connection_id: int, db: Session = Depends(get_db)):
    """Get all tables for a database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Get tables
    try:
        tables = db_service.get_tables(connection_id)
        return tables
    except Exception as e:
        logger.error(f"Error getting tables: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting tables: {str(e)}"
        )


@router.put("/connections/{connection_id}/status", response_model=DatabaseConnectionResponse)
def update_connection_status(
    connection_id: int, 
    status_update: ConnectionStatusUpdate, 
    db: Session = Depends(get_db)
):
    """Update a database connection status (start/stop/pause)."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Update status
    try:
        updated_connection = db_service.update_connection_status(connection_id, status_update.status)
        return updated_connection
    except Exception as e:
        logger.error(f"Error updating connection status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating connection status: {str(e)}"
        )
