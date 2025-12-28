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

import asyncio
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi import UploadFile, File
import io
import csv

from database import get_db
from models import DatabaseType, OperationType, ConnectionStatus
from schemas import (
    TableOperationRequest, 
    DatabaseConnectionResponse, 
    TableConfigResponse,
    ConnectionTestResponse,
    TableListResponse,
    TableSchemaResponse,
    SqlQueryRequest,
    SqlQueryResponse,
    CsvQueryExportRequest,
    CsvImportResponse
)
from services.whisperer_service import WhispererService
from services.connection_service import ConnectionService

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])

# Store active automation tasks
active_automations: Dict[str, WhispererService] = {}

@router.get("/connections/{connection_id}/tables", response_model=TableListResponse)
def list_tables(
    connection_id: int,
    schema: str,
    db = Depends(get_db)
):
    """List all tables for a connection with the specified schema."""
    try:
        # Get the connection service
        connection_service = ConnectionService(db)
        
        # Check if connection exists
        connection = connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {connection_id} not found"
            )
        
        # Get tables for the specified schema
        tables = connection_service.get_tables(connection_id, schema)
        
        return TableListResponse(
            connection_id=connection_id,
            schema=schema,
            tables=tables
        )
    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing tables: {str(e)}"
        )

@router.get("/connections/{connection_id}/tables/{table_name}/schema", response_model=TableSchemaResponse)
def get_table_schema(
    connection_id: int,
    table_name: str,
    db = Depends(get_db)
):
    """Get schema for a specific table."""
    try:
        # Get the connection service
        connection_service = ConnectionService(db)
        
        # Check if connection exists
        connection = connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {connection_id} not found"
            )
        
        # Get table schema
        schema = connection_service.get_table_schema(connection_id, table_name)
        
        return schema
    except Exception as e:
        logger.error(f"Error getting table schema: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting table schema: {str(e)}"
        )

@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
def start_automation(
    request: TableOperationRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Start database automation for specified tables."""
    try:
        # Get the connection service
        connection_service = ConnectionService(db)
        
        # Check if connection exists
        connection = connection_service.get_connection(request.connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {request.connection_id} not found"
            )
        
        # Check if tables exist
        for table_name in request.table_names:
            if not connection_service.table_exists(request.connection_id, table_name):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table {table_name} not found in connection {request.connection_id}"
                )
        
        # Create a unique ID for this automation
        automation_id = f"{request.connection_id}_{'-'.join(request.table_names)}"
        
        # Check if automation is already running
        if automation_id in active_automations:
            return {
                "status": "already_running",
                "message": f"Automation for connection {request.connection_id} and tables {request.table_names} is already running",
                "automation_id": automation_id
            }
        
        # Create a new whisperer service
        whisperer_service = WhispererService(db)
        
        # Start the automation
        whisperer_service.start_whisperer(request.connection_id)
        
        # Store the automation
        active_automations[automation_id] = whisperer_service
        
        # Add a background task to check when automation is complete
        background_tasks.add_task(
            automation_complete,
            automation_id,
            request.connection_id
        )
        
        return {
            "status": "started",
            "message": f"Automation started for connection {request.connection_id} and tables {request.table_names}",
            "automation_id": automation_id
        }
    except Exception as e:
        logger.error(f"Error starting automation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting automation: {str(e)}"
        )

@router.post("/stop/{connection_id}/{table_name}", status_code=status.HTTP_202_ACCEPTED)
def stop_automation(
    connection_id: int,
    table_name: str,
    db = Depends(get_db)
):
    """Stop automation for a specific table."""
    try:
        # Create the automation ID
        automation_id = f"{connection_id}_{table_name}"
        
        # Check if automation is running
        if automation_id not in active_automations:
            return {
                "status": "not_running",
                "message": f"Automation for connection {connection_id} and table {table_name} is not running"
            }
        
        # Stop the automation
        whisperer_service = active_automations[automation_id]
        whisperer_service.stop_whisperer(connection_id)
        
        # Remove from active automations
        del active_automations[automation_id]
        
        return {
            "status": "stopped",
            "message": f"Automation stopped for connection {connection_id} and table {table_name}"
        }
    except Exception as e:
        logger.error(f"Error stopping automation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping automation: {str(e)}"
        )

@router.post("/stop-all", status_code=status.HTTP_202_ACCEPTED)
def stop_all_automations(db = Depends(get_db)):
    """Stop all running automations."""
    try:
        # Stop all automations
        for automation_id, whisperer_service in active_automations.items():
            connection_id = int(automation_id.split('_')[0])
            whisperer_service.stop_whisperer(connection_id)
        
        # Clear active automations
        active_automations.clear()
        
        return {
            "status": "stopped",
            "message": "All automations stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping all automations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping all automations: {str(e)}"
        )

@router.get("/status", status_code=status.HTTP_200_OK)
def get_automation_status():
    """Get status of all running automations."""
    try:
        # Get status of all automations
        status_list = []
        for automation_id, whisperer_service in active_automations.items():
            parts = automation_id.split('_')
            connection_id = int(parts[0])
            table_names = parts[1].split('-')
            
            status_list.append({
                "automation_id": automation_id,
                "connection_id": connection_id,
                "table_names": table_names,
                "status": "running"
            })
        
        return {
            "automations": status_list
        }
    except Exception as e:
        logger.error(f"Error getting automation status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting automation status: {str(e)}"
        )

def stop_automation_task(automation_id: str):
    """Helper function to stop an automation task."""
    if automation_id in active_automations:
        connection_id = int(automation_id.split('_')[0])
        whisperer_service = active_automations[automation_id]
        whisperer_service.stop_whisperer(connection_id)
        del active_automations[automation_id]

def automation_complete(automation_id: str, connection_id: int):
    """Callback when automation is complete."""
    try:
        # Check if automation is still running
        if automation_id not in active_automations:
            return
        
        # Get the whisperer service
        whisperer_service = active_automations[automation_id]
        
        # Check if the connection is still running
        db = get_db()
        connection = db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
        
        if not connection or connection["status"] != ConnectionStatus.RUNNING.value:
            # Stop the automation
            whisperer_service.stop_whisperer(connection_id)
            del active_automations[automation_id]
            logger.info(f"Automation {automation_id} completed")
    except Exception as e:
        logger.error(f"Error in automation complete callback: {str(e)}")


@router.post("/connections/{connection_id}/query", response_model=SqlQueryResponse)
async def execute_query(connection_id: int, request: SqlQueryRequest, db = Depends(get_db)):
    """Execute a SQL query against a database connection."""
    try:
        # Get database connection
        db_service = ConnectionService(db)
        connection = db_service.get_connection(connection_id)
        
        if not connection:
            return SqlQueryResponse(
                success=False,
                message=f"Connection with ID {connection_id} not found",
                results=[],
                column_names=[],
                row_count=0
            )
        
        if connection.status not in [
            ConnectionStatus.RUNNING,
            ConnectionStatus.IDLE,
            ConnectionStatus.CONNECTED,
        ]:
            return SqlQueryResponse(
                success=False,
                message=f"Connection with ID {connection_id} is not active (status: {connection.status})",
                results=[],
                column_names=[],
                row_count=0
            )
        
        # Create a database connector
        connector_db_type = connection.db_type
        if isinstance(connector_db_type, str):
            try:
                connector_db_type = DatabaseType[connector_db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {connector_db_type}")
                
        # Map database field from database_name to database if needed
        database = getattr(connection, 'database', None)
        if not database and hasattr(connection, 'database_name'):
            database = connection.database_name
            logger.info(f"Using database_name field: {database}")
        
        from utils.db_connector import DatabaseConnector
        db_connector = DatabaseConnector(
            db_type=connector_db_type,
            host=connection.host,
            port=connection.port,
            database=database,
            username=connection.username,
            password=connection.password
        )
        
        # Connect to the database
        connected = db_connector.connect()
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to database for connection ID {connection_id}"
            )
        
        try:
            # Log query information
            logger.info(f"Executing query on connection {connection_id}: {request.query}")
            
            # Execute the query
            params = request.params if request.params else []
            
            # For SQLite, ensure we explicitly commit transactions
            if connector_db_type == DatabaseType.SQLITE:
                # Execute and commit explicitly for SQLite
                cursor = db_connector.connection.cursor()
                try:
                    cursor.execute(request.query, params)
                    db_connector.connection.commit()
                    
                    # Check if this is a SELECT query to get results
                    is_select = request.query.strip().upper().startswith("SELECT")
                    if is_select and cursor.description:
                        # Get column names and ensure they are Python strings
                        column_names = []
                        for desc in cursor.description:
                            col_name = str(desc[0]) if desc[0] else 'column_' + str(len(column_names))
                            column_names.append(col_name)
                        
                        # Fetch results (limited by max_rows)
                        result_set = cursor.fetchmany(request.max_rows) if request.max_rows else cursor.fetchall()
                        
                        # Convert results to dictionaries
                        results = []
                        for row in result_set:
                            row_dict = {}
                            for i, col_name in enumerate(column_names):
                                # Convert Java objects to Python types
                                row_dict[col_name] = str(row[i]) if row[i] is not None else None
                            results.append(row_dict)
                    else:
                        # For non-SELECT queries, return empty results
                        results = []
                finally:
                    cursor.close()
            else:
                # Use the standard execute_query method for other database types
                results = db_connector.execute_query(request.query, params=params, max_rows=request.max_rows)
            
            # Get column names if results are available
            column_names = []
            if results and len(results) > 0:
                column_names = list(results[0].keys())
            
            # Disconnect from the database
            db_connector.disconnect()
            
            # Return the results
            return SqlQueryResponse(
                success=True,
                message=f"Query executed successfully. Retrieved {len(results)} rows.",
                results=results,
                column_names=column_names,
                row_count=len(results)
            )
        except Exception as e:
            # Disconnect from the database in case of error
            db_connector.disconnect()
            
            # Log the error and return an error response
            logger.error(f"Error executing query: {str(e)}")
            return SqlQueryResponse(
                success=False,
                message=f"Error executing query: {str(e)}",
                results=[],
                column_names=[],
                row_count=0
            )
        finally:
            # Disconnect from the database
            try:
                db_connector.disconnect()
                logger.info("Disconnected from database")
            except Exception as e:
                logger.error(f"Error disconnecting from database: {str(e)}")
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing query: {str(e)}"
        )


@router.post("/connections/{connection_id}/query/export-csv", response_class=StreamingResponse)
async def export_query_csv(connection_id: int, request: CsvQueryExportRequest, db = Depends(get_db)):
    """Export query results to CSV with streaming and size limit enforcement."""
    try:
        # Get database connection
        db_service = ConnectionService(db)
        connection = db_service.get_connection(connection_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {connection_id} not found"
            )
        
        if connection.status not in [
            ConnectionStatus.RUNNING,
            ConnectionStatus.IDLE,
            ConnectionStatus.CONNECTED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection with ID {connection_id} is not active (status: {connection.status})"
            )
        
        # Create a database connector
        connector_db_type = connection.db_type
        if isinstance(connector_db_type, str):
            try:
                connector_db_type = DatabaseType[connector_db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {connector_db_type}")
                
        from utils.db_connector import DatabaseConnector
        db_connector = DatabaseConnector(
            db_type=connector_db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        # Connect to the database
        connected = db_connector.connect()
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to database for connection ID {connection_id}"
            )
        
        try:
            # Determine max rows based on include_all_rows flag
            max_rows = None if request.include_all_rows else request.max_rows
            if request.include_all_rows:
                logger.info(f"Exporting all rows for query on connection {connection_id}")
            
            # Execute the query
            params = request.params if request.params else []
            results = db_connector.execute_query(request.query, params, max_rows)
            
            # Stream the CSV response with size limit
            def generate_csv():
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                if results and len(results) > 0:
                    writer.writerow(results[0].keys())
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
                    
                    total_size = 0
                    max_size_bytes = 500 * 1024 * 1024  # 500 MB limit
                    
                    # Write data rows
                    for row in results:
                        writer.writerow(row.values())
                        csv_row = output.getvalue()
                        
                        # Check size limit
                        total_size += len(csv_row.encode('utf-8'))
                        if total_size > max_size_bytes:
                            logger.warning(f"CSV export exceeded 500 MB limit for connection {connection_id}")
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="CSV export exceeds 500 MB limit"
                            )
                        
                        yield csv_row
                        output.seek(0)
                        output.truncate(0)
            
            # Log export information
            logger.info(f"Starting CSV export for connection {connection_id}, query: {request.query[:100]}...")
            
            return StreamingResponse(
                generate_csv(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=query_export_{connection_id}.csv"
                }
            )
            
        finally:
            db_connector.disconnect()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting query CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting query CSV: {str(e)}"
        )

@router.get("/connections/{connection_id}/tables/{table_name}/export-csv", response_class=StreamingResponse)
async def export_table_csv(connection_id: int, table_name: str, schema_name: Optional[str] = None, db = Depends(get_db)):
    """Export entire table to CSV with streaming and size limit enforcement."""
    try:
        # Get database connection
        db_service = ConnectionService(db)
        connection = db_service.get_connection(connection_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {connection_id} not found"
            )
        
        if connection.status not in [
            ConnectionStatus.RUNNING,
            ConnectionStatus.IDLE,
            ConnectionStatus.CONNECTED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection with ID {connection_id} is not active (status: {connection.status})"
            )
        
        # Create a database connector
        connector_db_type = connection.db_type
        if isinstance(connector_db_type, str):
            try:
                connector_db_type = DatabaseType[connector_db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {connector_db_type}")
                
        from utils.db_connector import DatabaseConnector
        db_connector = DatabaseConnector(
            db_type=connector_db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        # Connect to the database
        connected = db_connector.connect()
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to database for connection ID {connection_id}"
            )
        
        try:
            # Build the SELECT query for the table
            if schema_name:
                qualified_table = f"{schema_name}.{table_name}"
            else:
                qualified_table = table_name
                
            query = f"SELECT * FROM {qualified_table}"
            
            # Execute the query to get all rows
            results = db_connector.execute_query(query, max_rows=None)
            
            # Stream the CSV response with size limit
            def generate_csv():
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                if results and len(results) > 0:
                    writer.writerow(results[0].keys())
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
                    
                    total_size = 0
                    max_size_bytes = 500 * 1024 * 1024  # 500 MB limit
                    
                    # Write data rows
                    for row in results:
                        writer.writerow(row.values())
                        csv_row = output.getvalue()
                        
                        # Check size limit
                        total_size += len(csv_row.encode('utf-8'))
                        if total_size > max_size_bytes:
                            logger.warning(f"CSV export exceeded 500 MB limit for table {qualified_table}")
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="CSV export exceeds 500 MB limit"
                            )
                        
                        yield csv_row
                        output.seek(0)
                        output.truncate(0)
            
            # Log export information
            logger.info(f"Starting CSV export for table {qualified_table} on connection {connection_id}")
            
            return StreamingResponse(
                generate_csv(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=table_export_{table_name}_{connection_id}.csv"
                }
            )
            
        finally:
            db_connector.disconnect()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting table CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting table CSV: {str(e)}"
        )

@router.post("/connections/{connection_id}/tables/{table_name}/import-csv", response_model=CsvImportResponse)
async def import_table_csv(
    connection_id: int, 
    table_name: str, 
    file: UploadFile = File(...), 
    schema_name: Optional[str] = None, 
    db = Depends(get_db)
):
    """Import CSV file into a database table with size limit enforcement."""
    try:
        # Check file size (500 MB limit)
        file_size = 0
        content = await file.read()
        file_size = len(content)
        
        if file_size > 500 * 1024 * 1024:  # 500 MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="CSV file exceeds 500 MB limit"
            )
        
        # Reset file pointer
        await file.seek(0)
        
        # Get database connection
        db_service = ConnectionService(db)
        connection = db_service.get_connection(connection_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection with ID {connection_id} not found"
            )
        
        if connection.status not in [
            ConnectionStatus.RUNNING,
            ConnectionStatus.IDLE,
            ConnectionStatus.CONNECTED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection with ID {connection_id} is not active (status: {connection.status})"
            )
        
        # Create a database connector
        connector_db_type = connection.db_type
        if isinstance(connector_db_type, str):
            try:
                connector_db_type = DatabaseType[connector_db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {connector_db_type}")
                
        from utils.db_connector import DatabaseConnector
        db_connector = DatabaseConnector(
            db_type=connector_db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        # Connect to the database
        connected = db_connector.connect()
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to connect to database for connection ID {connection_id}"
            )
        
        try:
            # Parse CSV content
            csv_content = content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Get column names from CSV
            csv_columns = csv_reader.fieldnames
            if not csv_columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CSV file has no columns"
                )
            
            # Build the qualified table name
            if schema_name:
                qualified_table = f"{schema_name}.{table_name}"
            else:
                qualified_table = table_name
            
            # Get table schema to validate columns
            table_schema = db_connector.get_table_schema(table_name, schema_name)
            if not table_schema or 'columns' not in table_schema:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not get schema for table {qualified_table}"
                )
            
            table_columns = list(table_schema['columns'].keys())
            
            # Validate that CSV columns exist in the table
            missing_columns = [col for col in csv_columns if col not in table_columns]
            if missing_columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CSV columns not found in table: {', '.join(missing_columns)}"
                )
            
            # Prepare insert statement
            placeholders = ', '.join(['?' for _ in csv_columns])
            columns_str = ', '.join(f'"{col}"' if ' ' in col or col.upper() in ['ORDER', 'GROUP', 'SELECT'] else col for col in csv_columns)
            insert_query = f"INSERT INTO {qualified_table} ({columns_str}) VALUES ({placeholders})"
            
            # Execute inserts in batches
            batch_size = 1000
            inserted_rows = 0
            
            batch_data = []
            for row in csv_reader:
                # Convert empty strings to None for nullable columns
                processed_row = []
                for col in csv_columns:
                    value = row.get(col, '')
                    if value == '' and table_schema['columns'][col].get('nullable', True):
                        processed_row.append(None)
                    else:
                        processed_row.append(value)
                
                batch_data.append(processed_row)
                inserted_rows += 1
                
                # Execute batch when it reaches batch_size
                if len(batch_data) >= batch_size:
                    db_connector.connection.cursor().executemany(insert_query, batch_data)
                    db_connector.connection.commit()
                    batch_data = []
            
            # Execute remaining batch
            if batch_data:
                db_connector.connection.cursor().executemany(insert_query, batch_data)
                db_connector.connection.commit()
            
            logger.info(f"Successfully imported {inserted_rows} rows into table {qualified_table}")
            
            return CsvImportResponse(
                success=True,
                inserted_rows=inserted_rows
            )
            
        finally:
            db_connector.disconnect()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importing CSV: {str(e)}"
        )
