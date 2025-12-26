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
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from models import DatabaseConnection, ConnectionStatus
from schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseConnectionResponse,
    ConnectionStatusUpdate,
    ConnectionTestResponse,
    TableResponse,
    MetadataObject,
    TableMetadata,
)
from services.database_service import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["connections"])

# Database connection routes
@router.post("/connections", response_model=DatabaseConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(connection: DatabaseConnectionCreate, db = Depends(get_db)):
    """Create a new database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection with the same name already exists
    existing_connection = db_service.get_connection_by_name(connection.name)
    if existing_connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection with name '{connection.name}' already exists"
        )
    
    try:
        new_connection = db_service.create_connection(connection)
        return new_connection
    except Exception as e:
        logger.error(f"Error creating connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating connection: {str(e)}"
        )

@router.get(
    "/connections/{connection_id}/metadata/objects",
    response_model=List[MetadataObject],
)
def get_schema_objects(
    connection_id: int,
    schema: Optional[str] = None,
    db = Depends(get_db),
):
    """List objects (tables/views/procs) for a connection and optional schema."""
    db_service = DatabaseService(db)
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found",
        )
    try:
        return db_service.get_schema_objects(connection_id, schema)
    except Exception as e:
        logger.error(f"Error getting metadata objects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting metadata objects: {str(e)}",
        )


@router.get(
    "/connections/{connection_id}/metadata/tables/{table_name}",
    response_model=TableMetadata,
)
def get_table_metadata(
    connection_id: int,
    table_name: str,
    schema: Optional[str] = None,
    db = Depends(get_db),
):
    """Get table metadata (columns, PK/FK, indexes) for a given table."""
    db_service = DatabaseService(db)
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found",
        )
    try:
        return db_service.get_table_metadata(connection_id, table_name, schema)
    except Exception as e:
        logger.error(f"Error getting table metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting table metadata: {str(e)}",
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
def get_connections(skip: int = 0, limit: int = 100, db = Depends(get_db)):
    """Get all database connections."""
    db_service = DatabaseService(db)
    connections = db_service.get_connections(skip=skip, limit=limit)
    logger.debug("DEBUG: API called, returning connections")
    return connections
    """Get all database connections."""
    db_service = DatabaseService(db)
    connections = db_service.get_connections(skip=skip, limit=limit)

@router.get("/connections/", response_model=List[DatabaseConnectionResponse])
def get_connections_trailing_slash(skip: int = 0, limit: int = 100, db = Depends(get_db)):
    """Get all database connections (with trailing slash)."""
    return get_connections(skip=skip, limit=limit, db=db)


@router.get("/connections/{connection_id}", response_model=DatabaseConnectionResponse)
def get_connection(connection_id: int, db = Depends(get_db)):
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
    db = Depends(get_db)
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
def delete_connection(connection_id: int, db = Depends(get_db)):
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


@router.delete("/connections/{connection_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection_trailing_slash(connection_id: int, db = Depends(get_db)):
    """Delete a database connection (with trailing slash)."""
    return delete_connection(connection_id, db)


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
def test_connection(connection_id: int, db = Depends(get_db)):
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
        success = db_service.test_connection(connection_id)
        status_value = ConnectionStatus.CONNECTED if success else ConnectionStatus.ERROR
        message = "Connection successful." if success else "Unable to establish connection with provided settings."
        try:
            db_service.update_connection_status(connection_id, status_value)
        except Exception as status_error:
            logger.warning(f"Unable to update connection status after test: {status_error}")
        return ConnectionTestResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}")
        try:
            db_service.update_connection_status(connection_id, ConnectionStatus.ERROR)
        except Exception:
            pass
        return ConnectionTestResponse(success=False, message=str(e))


@router.get("/connections/{connection_id}/schemas", response_model=List[str])
def get_schemas(connection_id: int, db = Depends(get_db)):
    """Get all schemas for a database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    existing_connection = db_service.get_connection(connection_id)
    if not existing_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Get schemas
    try:
        schemas = db_service.get_schemas(connection_id)
        return schemas
    except Exception as e:
        logger.error(f"Error getting schemas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting schemas: {str(e)}"
        )


@router.put("/connections/{connection_id}/status", response_model=DatabaseConnectionResponse)
def update_connection_status(
    connection_id: int, 
    status_update: ConnectionStatusUpdate, 
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
