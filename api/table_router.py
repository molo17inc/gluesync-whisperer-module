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
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    TableConfigCreate,
    TableConfigUpdate,
    TableConfigResponse,
    TableSchemaResponse,
    TableOperationRequest,
)
from services.table_service import TableService
from services.database_service import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["tables"])

# Table configuration routes
@router.post("/tables", response_model=TableConfigResponse, status_code=status.HTTP_201_CREATED)
def create_table_config(table: TableConfigCreate, db: Session = Depends(get_db)):
    """Create a new table configuration for automation."""
    table_service = TableService(db)
    db_service = DatabaseService(db)
    
    # Check if connection exists
    connection = db_service.get_connection(table.connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {table.connection_id} not found"
        )
    
    # Check if table exists in the database
    try:
        tables = db_service.get_tables(table.connection_id)
        if table.table_name not in tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table '{table.table_name}' not found in the database"
            )
    except Exception as e:
        logger.error(f"Error checking table existence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking table existence: {str(e)}"
        )
    
    # Check if table config already exists
    existing_table = table_service.get_table_by_name_and_connection(
        connection_id=table.connection_id, 
        table_name=table.table_name
    )
    if existing_table:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table configuration for '{table.table_name}' already exists"
        )
    
    # Get table schema
    try:
        schema = db_service.get_table_schema(connection_id=table.connection_id, table_name=table.table_name)
        
        # Create table configuration with schema information
        new_table = table_service.create_table(
            table=table,
            column_definitions=schema.columns,
            primary_keys=schema.primary_keys
        )
        return new_table
    except Exception as e:
        logger.error(f"Error creating table configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating table configuration: {str(e)}"
        )


@router.get("/connections/{connection_id}/tables", response_model=List[TableConfigResponse])
def get_tables_for_connection(
    connection_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """Get all table configurations for a connection."""
    table_service = TableService(db)
    db_service = DatabaseService(db)
    
    # Check if connection exists
    connection = db_service.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    tables = table_service.get_tables_by_connection(connection_id=connection_id, skip=skip, limit=limit)
    return tables


@router.get("/tables", response_model=List[TableConfigResponse])
def get_tables(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all table configurations."""
    table_service = TableService(db)
    tables = table_service.get_tables(skip=skip, limit=limit)
    return tables


@router.get("/tables/{table_id}", response_model=TableConfigResponse)
def get_table(table_id: int, db: Session = Depends(get_db)):
    """Get a specific table configuration by ID."""
    table_service = TableService(db)
    table = table_service.get_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table configuration with ID {table_id} not found"
        )
    return table


@router.put("/tables/{table_id}", response_model=TableConfigResponse)
def update_table(
    table_id: int, 
    table_update: TableConfigUpdate, 
    db: Session = Depends(get_db)
):
    """Update a table configuration."""
    table_service = TableService(db)
    
    # Check if table exists
    existing_table = table_service.get_table(table_id)
    if not existing_table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table configuration with ID {table_id} not found"
        )
    
    # Update table
    try:
        updated_table = table_service.update_table(table_id, table_update)
        return updated_table
    except Exception as e:
        logger.error(f"Error updating table configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating table configuration: {str(e)}"
        )


@router.delete("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table(table_id: int, db: Session = Depends(get_db)):
    """Delete a table configuration."""
    table_service = TableService(db)
    
    # Check if table exists
    existing_table = table_service.get_table(table_id)
    if not existing_table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table configuration with ID {table_id} not found"
        )
    
    # Delete table
    try:
        table_service.delete_table(table_id)
        return None
    except Exception as e:
        logger.error(f"Error deleting table configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting table configuration: {str(e)}"
        )


@router.get("/connections/{connection_id}/tables/{table_name}/schema", response_model=TableSchemaResponse)
def get_table_schema(connection_id: int, table_name: str, db: Session = Depends(get_db)):
    """Get the schema of a table in the database."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    connection = db_service.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Get table schema
    try:
        schema = db_service.get_table_schema(connection_id=connection_id, table_name=table_name)
        return schema
    except Exception as e:
        logger.error(f"Error getting table schema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting table schema: {str(e)}"
        )


@router.post("/operations", status_code=status.HTTP_202_ACCEPTED)
def start_operations(operation_request: TableOperationRequest, db: Session = Depends(get_db)):
    """Start automated operations on tables."""
    table_service = TableService(db)
    db_service = DatabaseService(db)
    
    # Check if connection exists
    connection = db_service.get_connection(operation_request.connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {operation_request.connection_id} not found"
        )
    
    # Check if tables exist in the database
    try:
        available_tables = db_service.get_tables(operation_request.connection_id)
        invalid_tables = [table for table in operation_request.table_names if table not in available_tables]
        if invalid_tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tables not found in the database: {', '.join(invalid_tables)}"
            )
    except Exception as e:
        logger.error(f"Error checking tables existence: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking tables existence: {str(e)}"
        )
    
    # Configure and start operations
    try:
        table_service.start_operations(operation_request)
        return {"message": "Operations started successfully"}
    except Exception as e:
        logger.error(f"Error starting operations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting operations: {str(e)}"
        )
