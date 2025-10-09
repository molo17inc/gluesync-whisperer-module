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
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from schemas import (
    TableConfigCreate,
    TableConfigUpdate,
    TableConfigResponse,
    TableSchemaResponse,
    TableOperationRequest,
    TableResponse  # Add this import
)
from services.table_service import TableService
from services.database_service import DatabaseService

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tables"])

# Table configuration routes
@router.post("/tables", response_model=TableConfigResponse, status_code=status.HTTP_201_CREATED)
def create_table_config(table: TableConfigCreate, db = Depends(get_db)):
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
        # Use the schema_name provided in the request
        tables = db_service.get_tables(table.connection_id, schema=table.schema_name)
        # Handle both string array and object array formats
        table_names = [t['name'] if isinstance(t, dict) else t for t in tables]
        if table.table_name not in table_names:
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
        # Pass the schema_name to ensure we're getting the correct schema, especially important for AS400
        logger.info(f"Retrieving schema for {table.schema_name}.{table.table_name} from connection {table.connection_id}")
        schema = db_service.get_table_schema(
            connection_id=table.connection_id, 
            table_name=table.table_name, 
            schema_name=table.schema_name
        )
        
        # Check if schema retrieval was successful
        if not schema.columns:
            logger.warning(f"No columns retrieved for {table.schema_name}.{table.table_name}. This may cause issues with operations.")
        
        if not schema.primary_keys:
            logger.warning(f"No primary keys retrieved for {table.schema_name}.{table.table_name}. This may cause issues with update/delete operations.")
        
        logger.info(f"Retrieved {len(schema.columns)} columns and {len(schema.primary_keys)} primary keys for {table.schema_name}.{table.table_name}")
        
        # Create table configuration with schema information
        new_table = table_service.create_table(
            table=table,
            column_definitions=schema.columns,
            primary_keys=schema.primary_keys
        )
        return new_table
    except Exception as e:
        logger.error(f"Error creating table configuration: {str(e)}")
        # Try to create the table with empty schema as fallback
        try:
            logger.warning(f"Attempting to create table configuration with empty schema as fallback")
            new_table = table_service.create_table(
                table=table,
                column_definitions={},
                primary_keys=[]
            )
            return new_table
        except Exception as fallback_error:
            logger.error(f"Fallback creation also failed: {str(fallback_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating table configuration: {str(e)}. Fallback also failed: {str(fallback_error)}"
            )


@router.get("/connections/{connection_id}/table-configs", response_model=List[TableConfigResponse])
def get_tables_for_connection(
    connection_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db = Depends(get_db)
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
def get_tables(skip: int = 0, limit: int = 100, db = Depends(get_db)):
    """Get all table configurations."""
    table_service = TableService(db)
    tables = table_service.get_tables(skip=skip, limit=limit)
    return tables


@router.get("/tables/{table_id}", response_model=TableConfigResponse)
def get_table(table_id: int, db = Depends(get_db)):
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
    db = Depends(get_db)
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
def delete_table(table_id: int, db = Depends(get_db)):
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


@router.get("/connections/{connection_id}/schemas", response_model=List[str])
def get_schemas(connection_id: int, db = Depends(get_db)):
    """Get all schemas for a database connection."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    connection = db_service.get_connection(connection_id)
    if not connection:
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


@router.get("/connections/{connection_id}/tables", response_model=List[TableResponse])
def get_database_tables(connection_id: int, schema: str = None, db = Depends(get_db)):
    """Get all tables from the database for a connection. Optionally specify a schema."""
    db_service = DatabaseService(db)
    
    # Check if connection exists
    connection = db_service.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    
    # Get tables
    try:
        tables = db_service.get_tables(connection_id, schema=schema)
        return tables
    except Exception as e:
        logger.error(f"Error getting database tables: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting database tables: {str(e)}"
        )


@router.get("/connections/{connection_id}/tables/{table_name}/schema", response_model=TableSchemaResponse)
def get_table_schema(connection_id: int, table_name: str, schema_name: str = None, db = Depends(get_db)):
    """Get the schema of a table in the database."""
    logger.info(f"API CALL: get_table_schema for connection_id={connection_id}, table_name={table_name}, schema_name={schema_name}")
    db_service = DatabaseService(db)
    
    # Check if connection exists
    logger.info(f"Checking if connection {connection_id} exists")
    connection = db_service.get_connection(connection_id)
    if not connection:
        logger.error(f"Connection with ID {connection_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )
    logger.info(f"Connection found: {connection.name}, type: {connection.db_type}")
    
    # Get table schema
    try:
        # Pass schema_name parameter if provided, especially important for AS400
        logger.info(f"Calling db_service.get_table_schema for {connection_id}, {table_name}, {schema_name}")
        schema = db_service.get_table_schema(connection_id=connection_id, table_name=table_name, schema_name=schema_name)
        
        # Log the results
        column_count = len(schema.columns) if schema and schema.columns else 0
        pk_count = len(schema.primary_keys) if schema and schema.primary_keys else 0
        
        # Use appropriate default schema based on database type
        default_schema = 'dbo' if connection.db_type.lower() == 'mssql' else 'default'
        effective_schema = schema_name or default_schema
        
        logger.info(f"Retrieved {column_count} columns and {pk_count} primary keys for {effective_schema}.{table_name}")
        
        if column_count == 0:
            logger.warning(f"No columns retrieved for {effective_schema}.{table_name}. This may cause issues with operations.")
        
        if pk_count == 0:
            logger.warning(f"No primary keys retrieved for {effective_schema}.{table_name}. This may cause issues with update/delete operations.")
            
        return schema
    except Exception as e:
        logger.error(f"Error getting table schema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting table schema: {str(e)}"
        )


@router.post("/operations", status_code=status.HTTP_202_ACCEPTED)
def start_operations(operation_request: TableOperationRequest, db = Depends(get_db)):
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
        # Handle both string array and object array formats
        available_table_names = [t['name'] if isinstance(t, dict) else t for t in available_tables]
        invalid_tables = [table for table in operation_request.table_names if table not in available_table_names]
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
