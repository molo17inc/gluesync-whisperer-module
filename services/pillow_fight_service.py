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
import random
import string
import time
import threading
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from models import DatabaseConnection, TableConfig, OperationType, ConnectionStatus, DatabaseType
from services.database_service import DatabaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global registry for active pillow fights
active_pillow_fights = {}

class PillowFightService:
    """Service to manage database pillow fights (automated operations)."""
    
    def __init__(self, db):
        """Initialize the pillow fight service."""
        self.db = db
        self.db_service = DatabaseService(db)
        self.stop_events = {}  # {(connection_id, table_id): threading.Event}
        self.threads = {}  # {(connection_id, table_id): threading.Thread}
        self.status = {}  # {(connection_id, table_id): status_dict}
        self._schema_cache = {}  # {(connection_id, table_name, schema_name): TableSchemaResponse}
    
    def start_pillow_fight(
        self,
        connection_id: int,
        table_ids: List[int],
        operation_types: List[str],
        operation_delay: float = 1.0,
        batch_size: int = 1
    ) -> None:
        """Start a pillow fight for a connection and tables."""
        # Get the connection
        connection_data = self.db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
        if not connection_data:
            logger.error(f"Connection with ID {connection_id} not found")
            return
        
        # Convert database_name to database for the DatabaseConnection model
        connection_dict = dict(connection_data)
        
        # Ensure we have the required fields with correct names
        if 'database_name' in connection_dict:
            connection_dict['database'] = connection_dict['database_name']
        
        # Make sure we have db_type field
        if 'type' in connection_dict and 'db_type' not in connection_dict:
            connection_dict['db_type'] = connection_dict['type']
        
        # Log the fields we're working with
        logger.debug(f"Connection data fields: {connection_dict.keys()}")
        
        # Create a clean dictionary with only the fields that DatabaseConnection expects
        clean_dict = {
            'id': connection_dict.get('id'),
            'name': connection_dict.get('name'),
            'description': connection_dict.get('description'),
            'db_type': connection_dict.get('db_type'),
            'host': connection_dict.get('host'),
            'port': connection_dict.get('port'),
            'username': connection_dict.get('username'),
            'password': connection_dict.get('password'),
            'database': connection_dict.get('database_name'),  # Use database_name from DB as database in model
            'connection_string': connection_dict.get('connection_string'),
            'status': connection_dict.get('status'),
            'created_at': connection_dict.get('created_at'),
            'updated_at': connection_dict.get('updated_at'),
            'last_operation_at': connection_dict.get('last_operation_at')
        }
        
        # Remove any None values to avoid passing None to required fields
        clean_dict = {k: v for k, v in clean_dict.items() if v is not None}
        
        logger.debug(f"Creating DatabaseConnection with fields: {clean_dict.keys()}")
        connection = DatabaseConnection(**clean_dict)
        
        # Update the connection status
        self.db.execute("UPDATE database_connections SET status = ? WHERE id = ?", 
                        (ConnectionStatus.RUNNING.value, connection_id))
        self.db.commit()
        
        # Start a pillow fight for each table
        for table_id in table_ids:
            # Get the table
            table_data = self.db.query_one("SELECT * FROM table_configs WHERE id = ?", (table_id,))
            if not table_data:
                logger.error(f"Table with ID {table_id} not found")
                continue
            
            # Parse JSON fields
            if 'column_definitions' in table_data and table_data['column_definitions']:
                try:
                    table_data['column_definitions'] = json.loads(table_data['column_definitions'])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse column_definitions for table {table_id}")
                    continue
                    
            if 'primary_keys' in table_data and table_data['primary_keys']:
                try:
                    table_data['primary_keys'] = json.loads(table_data['primary_keys'])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse primary_keys for table {table_id}")
                    continue
            
            # Convert operation_type to enum if needed
            if 'operation_type' in table_data:
                try:
                    table_data['operation_type'] = OperationType(table_data['operation_type'])
                except (ValueError, TypeError):
                    pass  # Keep as string if not a valid enum value
            
            table = TableConfig(**table_data)
            
            # Check if a pillow fight is already running for this table
            key = (connection_id, table_id)
            if key in self.threads and self.threads[key].is_alive():
                logger.info(f"Pillow fight already running for connection {connection_id} and table {table_id}")
                continue
            
            # Create a stop event
            stop_event = threading.Event()
            self.stop_events[key] = stop_event
            
            # Initialize status
            self.status[key] = {
                "connection_id": connection_id,
                "table_id": table_id,
                "operation_types": operation_types,
                "operation_delay": operation_delay,
                "batch_size": batch_size,
                "start_time": datetime.now().isoformat(),
                "last_operation_time": None,
                "status": "running",
                "operations": {
                    "insert": 0,
                    "update": 0,
                    "delete": 0,
                    "errors": 0
                }
            }
            
            # Start the pillow fight in a separate thread
            thread = threading.Thread(
                target=self._run_pillow_fight,
                args=(connection, table, operation_types, operation_delay, batch_size, stop_event, key),
                daemon=True
            )
            thread.start()
            
            # Store the thread
            self.threads[key] = thread
            
            logger.info(f"Started pillow fight for connection {connection_id} and table {table_id}")
    
    def stop_pillow_fight(self, connection_id: int, table_id: int) -> None:
        """Stop a pillow fight for a connection and table."""
        key = (connection_id, table_id)
        
        # Check if a pillow fight is running for this table
        if key not in self.threads or not self.threads[key].is_alive():
            logger.info(f"No pillow fight running for connection {connection_id} and table {table_id}")
            return
        
        # Set the stop event
        if key in self.stop_events:
            self.stop_events[key].set()
        
        # Wait for the thread to finish
        if key in self.threads:
            self.threads[key].join(timeout=5)
        
        # Update the status
        if key in self.status:
            self.status[key]["status"] = "stopped"
            self.status[key]["duration"] = (
                datetime.now() - datetime.fromisoformat(self.status[key]["start_time"])
            ).total_seconds()
        
        # Remove from tracking
        if key in self.stop_events:
            del self.stop_events[key]
        if key in self.threads:
            del self.threads[key]
        
        logger.info(f"Stopped pillow fight for connection {connection_id} and table {table_id}")
    
    def get_status(self, connection_id: int, table_id: int) -> Optional[Dict[str, Any]]:
        """Get the status of a pillow fight."""
        key = (connection_id, table_id)
        
        # Check if a pillow fight is running for this table
        if key not in self.status:
            return None
        
        # Check if the thread is still alive
        if key in self.threads and not self.threads[key].is_alive():
            self.status[key]["status"] = "stopped"
            self.status[key]["duration"] = (
                datetime.now() - datetime.fromisoformat(self.status[key]["start_time"])
            ).total_seconds()
        
        return self.status[key]
    
    def _run_pillow_fight(
        self,
        connection: DatabaseConnection,
        table: TableConfig,
        operation_types: List[str],
        operation_delay: float,
        batch_size: int,
        stop_event: threading.Event,
        key: tuple
    ) -> None:
        """Run the pillow fight for a connection and table."""
        # Log that we're starting the pillow fight
        logger.info(f"Starting pillow fight for connection {connection.id} and table {table.table_name}")
        logger.info(f"Using operation types: {operation_types}")
        logger.info(f"Table config: {table.__dict__}")
        
        # Create database engine outside the loop to avoid recreating it for each operation
        engine = None
        
        while not stop_event.is_set():
            try:
                # Only create the engine if it doesn't exist or if there was an error
                if engine is None:
                    logger.info(f"Creating database engine for connection {connection.id}")
                    # For JDBC connections (AS400 and MS SQL Server), create a DatabaseConnector directly
                    if connection.db_type in [DatabaseType.AS400, DatabaseType.MSSQL] or \
                       (isinstance(connection.db_type, str) and connection.db_type.upper() in ['AS400', 'MSSQL']):
                        # Import here to avoid circular imports
                        from utils.db_connector import DatabaseConnector
                        
                        # Convert string db_type to enum if needed
                        connector_db_type = connection.db_type
                        if isinstance(connection.db_type, str):
                            try:
                                connector_db_type = DatabaseType[connection.db_type.upper()]
                            except (KeyError, AttributeError):
                                logger.warning(f"Unknown database type string: {connection.db_type}")
                        
                        # Make sure we have a valid database name
                        # Use database field from the connection object
                        database_name = connection.database
                        logger.info(f"Creating JDBC DatabaseConnector with parameters: db_type={connector_db_type}, host={connection.host}, port={connection.port}, database={database_name}")
                        
                        # Log all connection attributes for debugging
                        logger.info(f"Connection object details: {connection.__dict__}")
                        
                        # Create the connector with the connection parameters
                        db_connector = DatabaseConnector(
                            db_type=connector_db_type,
                            host=connection.host,
                            port=connection.port,
                            database=database_name,
                            username=connection.username,
                            password=connection.password
                        )
                        
                        # Connect to the database
                        logger.info("Connecting to database...")
                        db_connector.connect()
                        
                        # Verify the connection is valid
                        if not db_connector.connection or not hasattr(db_connector.connection, 'cursor'):
                            logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                            raise Exception(f"Failed to establish a valid connection to {connection.db_type} database")
                        
                        # Use the connector as our engine
                        engine = db_connector
                        logger.info(f"Created direct JDBC connection for {connection.db_type} database")
                    else:
                        # For other database types, use the engine from DatabaseService
                        logger.info(f"Using DatabaseService._get_engine for connection {connection.id}")
                        engine = self.db_service._get_engine(connection)
                        logger.info(f"Using engine from DatabaseService for {connection.db_type} database")
                    
                    # Update status to running
                    self.status[key]["status"] = "running"
                    logger.info(f"Updated status to running for pillow fight {key}")
                
                # Perform a batch of operations
                for _ in range(batch_size):
                    if stop_event.is_set():
                        logger.info(f"Stop event set, breaking out of batch loop")
                        break
                        
                    # Randomly select an operation type
                    op_type = random.choice(operation_types)
                    logger.info(f"Selected operation type: {op_type}")
                    
                    try:
                        # Perform the operation - normalize to uppercase for comparison
                        op_type_upper = op_type.upper()
                        logger.info(f"Attempting to perform {op_type_upper} operation on {table.table_name}")
                        
                        if op_type_upper == "INSERT":
                            logger.info(f"Calling _perform_insert for {table.table_name}")
                            self._perform_insert(engine, connection, table)
                            self.status[key]["operations"]["insert"] += 1
                            logger.info(f"Successfully performed INSERT on {table.table_name}")
                        elif op_type_upper == "UPDATE":
                            logger.info(f"Calling _perform_update for {table.table_name}")
                            self._perform_update(engine, connection, table)
                            self.status[key]["operations"]["update"] += 1
                            logger.info(f"Successfully performed UPDATE on {table.table_name}")
                        elif op_type_upper == "DELETE":
                            logger.info(f"Calling _perform_delete for {table.table_name}")
                            self._perform_delete(engine, connection, table)
                            self.status[key]["operations"]["delete"] += 1
                            logger.info(f"Successfully performed DELETE on {table.table_name}")
                        
                        # Update the last operation time
                        self.status[key]["last_operation_time"] = datetime.now().isoformat()
                        logger.info(f"Updated last_operation_time for pillow fight {key}")
                        
                    except Exception as e:
                        logger.error(f"Error performing {op_type} on {table.table_name}: {str(e)}")
                        logger.error(f"Exception type: {type(e).__name__}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        self.status[key]["operations"]["errors"] += 1
                
                # Sleep for the specified delay
                logger.info(f"Sleeping for {operation_delay} seconds before next batch")
                time.sleep(operation_delay)
                
            except Exception as e:
                logger.error(f"Error in pillow fight thread for connection {connection.id} and table {table.id}: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.status[key]["status"] = "error"
                self.status[key]["error"] = str(e)
                
                # Reset the engine so it will be recreated on the next iteration
                logger.info("Resetting engine due to error")
                engine = None
                
                # Sleep before retrying to avoid tight error loops
                logger.info("Sleeping for 5 seconds before retrying")
                time.sleep(5)
        
        # Only update status to stopped when the stop_event is set
        self.status[key]["status"] = "stopped"
        self.status[key]["duration"] = (
            datetime.now() - datetime.fromisoformat(self.status[key]["start_time"])
        ).total_seconds()
        logger.info(f"Stopped pillow fight for connection {connection.id} and table {table.id}")
    
    def _perform_insert(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform an insert operation on a table."""
        try:
            logger.info(f"Starting insert operation for table {table.table_name}")
            
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return
                
            # Get the table schema with caching
            logger.info(f"Getting table schema for connection ID {connection.id}, table {table.table_name}, schema {table.schema_name}")
            try:
                # Check if schema is in cache
                cache_key = (connection.id, table.table_name, table.schema_name)
                if cache_key in self._schema_cache:
                    logger.info(f"Using cached schema for {table.schema_name}.{table.table_name}")
                    schema_info = self._schema_cache[cache_key]
                else:
                    logger.info(f"Schema cache miss for {table.schema_name}.{table.table_name}, retrieving from database")
                    schema_info = self.db_service.get_table_schema(connection.id, table.table_name, table.schema_name)
                    # Cache the schema
                    self._schema_cache[cache_key] = schema_info
                
                logger.info(f"Schema info received: {schema_info}")
                # Access columns and primary_keys as attributes of the TableSchemaResponse object
                columns_dict = schema_info.columns
                primary_keys = schema_info.primary_keys
                
                logger.info(f"Found {len(columns_dict)} columns and {len(primary_keys)} primary keys")
            except Exception as e:
                logger.error(f"Error getting table schema for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # Generate random data for each column
            data = {}
            for col_name, col_info in columns_dict.items():
                # Skip auto-increment columns or primary keys
                if col_name in primary_keys or col_info.get("primary_key", False):
                    logger.info(f"Skipping primary key column: {col_name}")
                    # For MSSQL, we need to generate a unique value for primary keys
                    # instead of skipping them, as they might not be auto-increment
                    if connection.db_type.lower() == 'mssql':
                        import random
                        
                        # Get the max ID from the table to ensure we generate a unique ID
                        table_name = table.table_name
                        if table.schema_name:
                            table_name = f"{table.schema_name}.{table_name}"
                        
                        try:
                            # Query to get the max ID
                            max_id_query = f"SELECT MAX({col_name}) as max_id FROM {table_name}"
                            max_id_result = engine.execute_query(max_id_query)
                            
                            # Extract the max ID
                            max_id = 0
                            if max_id_result and len(max_id_result) > 0 and max_id_result[0].get('max_id') is not None:
                                max_id = int(max_id_result[0].get('max_id', 0))
                                
                            # Generate a unique ID that's higher than the max ID
                            new_id = max_id + random.randint(1, 100)
                            logger.info(f"Generated unique ID {new_id} for primary key {col_name} (max existing ID: {max_id})")
                            data[col_name] = new_id
                        except Exception as e:
                            logger.warning(f"Error getting max ID for {col_name}: {str(e)}")
                            # Fallback to a large random number if we can't get the max ID
                            data[col_name] = random.randint(10000, 99999)
                    continue
                
                # Generate random data based on column type and name
                column_type = col_info["type"]
                # Add column name as an attribute to the column_type if it's an object
                if hasattr(column_type, '__dict__'):
                    column_type._col_name = col_name
                data[col_name] = self._generate_random_data(column_type)
            
            logger.info(f"Generated data for insert: {data}")
            
            # If no data to insert (all columns are primary keys), return
            if not data:
                logger.info(f"No columns to insert data for in {table.table_name}")
                return
            
            # Build the fully qualified table name
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # For MS SQL Server, we need to handle the parameter placeholders differently
            is_mssql = connection.db_type.lower() == 'mssql'
            
            # Both JDBC implementations use ? for parameter placeholders
            placeholders = ', '.join(['?' for _ in range(len(data))])
            
            # Build the insert statement
            stmt = f"INSERT INTO {table_name} ({', '.join(data.keys())}) VALUES ({placeholders})"
            
            logger.info(f"Prepared insert statement: {stmt}")
            logger.info(f"With values: {list(data.values())}")
            
            # Check if we're using a JDBC engine (has connection attribute) or SQLAlchemy engine
            if hasattr(engine, 'connection') and engine.connection:
                # For JDBC engine
                logger.info(f"Using JDBC engine for insert operation")
                engine.execute_query(stmt, list(data.values()))
            else:
                # For SQLAlchemy engine
                logger.info(f"Using SQLAlchemy engine for insert operation")
                with engine.connect() as conn:
                    conn.execute(stmt, list(data.values()))
            
            logger.info(f"Successfully inserted record into {table.table_name}")
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error performing insert on {table.table_name}: {error_message}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Check for foreign key constraint violations
            if any(keyword in error_message.lower() for keyword in ["foreign key constraint", "constraint", "reference", "fk"]):
                # Extract table and column information from the error message if possible
                import re
                table_match = re.search(r"table \"([^\"]+)\"", error_message) or re.search(r"table ([^,]+),", error_message)
                column_match = re.search(r"column \"([^\"]+)\"", error_message) or re.search(r"column '([^']+)'", error_message)
                
                referenced_table = table_match.group(1) if table_match else "referenced table"
                referenced_column = column_match.group(1) if column_match else "referenced column"
                
                # Provide helpful guidance about enabling cascade deletes
                logger.warning(f"Foreign key constraint violation detected on {table.table_name}")
                logger.warning(f"The operation failed because a foreign key constraint prevents the action.")
                logger.warning(f"Referenced table: {referenced_table}, Column: {referenced_column}")
                logger.warning(f"To fix this issue, you can:")
                logger.warning(f"1. Enable cascade_delete for the {table.table_name} table in your configuration")
                logger.warning(f"2. Ensure the referenced records in {referenced_table} exist before inserting into {table.table_name}")
                logger.warning(f"3. Use the update_cascade_delete.py script to update your configuration")
                
                # If we have a table_id, we can provide more specific guidance
                if hasattr(table, 'id'):
                    logger.warning(f"You can run: python update_cascade_delete.py --table_id {table.id} --enable True")
            
            # Continue despite errors - we've logged the issue and provided guidance
            pass
    
    def _perform_update(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform an update operation on a table."""
        try:
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return
                
            # Get the table schema with caching
            try:
                # Check if schema is in cache
                cache_key = (connection.id, table.table_name, table.schema_name)
                if cache_key in self._schema_cache:
                    logger.info(f"Using cached schema for {table.schema_name}.{table.table_name}")
                    schema_info = self._schema_cache[cache_key]
                else:
                    logger.info(f"Schema cache miss for {table.schema_name}.{table.table_name}, retrieving from database")
                    schema_info = self.db_service.get_table_schema(connection.id, table.table_name, table.schema_name)
                    # Cache the schema
                    self._schema_cache[cache_key] = schema_info
                
                # Access columns and primary_keys as attributes of the TableSchemaResponse object
                columns_dict = schema_info.columns
                primary_keys = schema_info.primary_keys
            except Exception as e:
                logger.error(f"Error getting table schema for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # First, get a random existing record
            try:
                existing_record = self._get_random_record(engine, table)
                
                if not existing_record:
                    logger.info(f"No records found in {table.table_name} for update")
                    return
            except Exception as e:
                logger.error(f"Error getting random record for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # Generate random data for each column, excluding primary keys
            data = {}
            for col_name, col_info in columns_dict.items():
                if col_name not in primary_keys:
                    # Generate random data based on column type and name
                    column_type = col_info["type"]
                    # Add column name as an attribute to the column_type if it's an object
                    if hasattr(column_type, '__dict__'):
                        column_type._col_name = col_name
                    data[col_name] = self._generate_random_data(column_type)
            
            # If no data to update (all columns are primary keys), return
            if not data:
                logger.info(f"No columns to update in {table.table_name}")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_values = []
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = ?")
                    where_values.append(existing_record[pk])
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table.table_name}")
                return
            
            # Build the update statement
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # For MS SQL Server, we need to handle the parameter placeholders differently
            is_mssql = connection.db_type.lower() == 'mssql'
            
            set_clauses = [f"{col} = ?" for col in data.keys()]
            
            stmt = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
            
            logger.info(f"Prepared update statement: {stmt}")
            logger.info(f"With set values: {list(data.values())} and where values: {where_values}")
            
            # Check if we're using a JDBC engine (has connection attribute) or SQLAlchemy engine
            if hasattr(engine, 'connection') and engine.connection:
                # For JDBC engine
                logger.debug(f"Executing JDBC update: {stmt}")
                engine.execute_query(stmt, list(data.values()) + where_values)
            else:
                # For SQLAlchemy engine
                with engine.connect() as conn:
                    conn.execute(stmt, list(data.values()) + where_values)
            
            logger.info(f"Updated record in {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing update on {table.table_name}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue despite errors
            pass
    
    def _perform_delete(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform a delete operation on a table."""
        try:
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return
                
            # Get the table schema with caching
            try:
                # Check if schema is in cache
                cache_key = (connection.id, table.table_name, table.schema_name)
                if cache_key in self._schema_cache:
                    logger.info(f"Using cached schema for {table.schema_name}.{table.table_name}")
                    schema_info = self._schema_cache[cache_key]
                else:
                    logger.info(f"Schema cache miss for {table.schema_name}.{table.table_name}, retrieving from database")
                    schema_info = self.db_service.get_table_schema(connection.id, table.table_name, table.schema_name)
                    # Cache the schema
                    self._schema_cache[cache_key] = schema_info
                
                # Access primary_keys as an attribute of the TableSchemaResponse object
                primary_keys = schema_info.primary_keys
            except Exception as e:
                logger.error(f"Error getting table schema for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # First, get a random existing record
            try:
                existing_record = self._get_random_record(engine, table)
                
                if not existing_record:
                    logger.info(f"No records found in {table.table_name} for delete")
                    return
            except Exception as e:
                logger.error(f"Error getting random record for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_values = []
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = ?")
                    where_values.append(existing_record[pk])
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table.table_name}")
                return
            
            # Build the delete statement
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # For MS SQL Server, we need to handle the parameter placeholders differently
            is_mssql = connection.db_type.lower() == 'mssql'
            
            # Check if cascade_delete is enabled
            cascade_option = ""
            if hasattr(table, 'cascade_delete') and table.cascade_delete:
                logger.info(f"Cascade delete enabled for {table_name}")
                # For MS SQL Server, we need to use a different approach for cascade deletes
                if is_mssql:
                    # We'll need to disable foreign key constraints temporarily
                    # or use a different approach like using a stored procedure
                    # For now, we'll log that cascade delete is enabled but not fully implemented for MS SQL
                    logger.warning(f"Cascade delete for MS SQL Server is handled through special SQL statements")
                    
                    # For MS SQL Server, we need to use a transaction with multiple statements
                    # First, get all foreign key constraints that reference this table
                    try:
                        # This is a simplified approach - in a real implementation, we would need to
                        # recursively find all related tables and delete from them in the correct order
                        logger.info(f"Using cascade delete approach for MS SQL Server")
                    except Exception as e:
                        logger.error(f"Error setting up cascade delete for MS SQL Server: {str(e)}")
            
            stmt = f"DELETE FROM {table_name} WHERE {' AND '.join(where_clauses)}"
            
            logger.info(f"Prepared delete statement: {stmt}")
            logger.info(f"With where values: {where_values}")
            
            # Check if we're using a JDBC engine (has connection attribute) or SQLAlchemy engine
            if hasattr(engine, 'connection') and engine.connection:
                # For JDBC engine
                logger.debug(f"Executing JDBC delete: {stmt}")
                
                # If cascade_delete is enabled and we're using MS SQL Server, we need a different approach
                if hasattr(table, 'cascade_delete') and table.cascade_delete and is_mssql:
                    try:
                        # For MS SQL Server with cascade delete, we need to use a transaction with multiple statements
                        # 1. Temporarily disable foreign key constraints
                        # 2. Perform the delete
                        # 3. Re-enable foreign key constraints
                        
                        # Start a transaction
                        engine.execute_query("BEGIN TRANSACTION", [])
                        
                        # Disable foreign key constraints
                        engine.execute_query("EXEC sp_MSforeachtable @command1='ALTER TABLE ? NOCHECK CONSTRAINT ALL'", [])
                        
                        # Execute the delete
                        engine.execute_query(stmt, where_values)
                        
                        # Re-enable foreign key constraints
                        engine.execute_query("EXEC sp_MSforeachtable @command1='ALTER TABLE ? CHECK CONSTRAINT ALL'", [])
                        
                        # Commit the transaction
                        engine.execute_query("COMMIT TRANSACTION", [])
                        
                        logger.info(f"Executed cascade delete for {table_name}")
                    except Exception as e:
                        # Rollback the transaction if there's an error
                        try:
                            engine.execute_query("ROLLBACK TRANSACTION", [])
                        except:
                            pass
                        logger.error(f"Error executing cascade delete for {table_name}: {str(e)}")
                        raise
                else:
                    # Standard delete without cascade
                    try:
                        engine.execute_query(stmt, where_values)
                    except Exception as e:
                        # Check if it's a foreign key constraint error
                        error_str = str(e).lower()
                        if 'foreign key' in error_str or 'reference constraint' in error_str or 'constraint' in error_str:
                            logger.warning(f"Foreign key constraint error detected for {table_name}. Consider enabling cascade_delete for this table.")
                            # Try to continue with the operation despite the error
                            # This allows the pillow fight to continue even if some deletes fail
                            return
                        else:
                            # Re-raise if it's not a foreign key constraint error
                            raise
            else:
                # For SQLAlchemy engine
                with engine.connect() as conn:
                    conn.execute(stmt, where_values)
            
            logger.info(f"Deleted record from {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing delete on {table.table_name}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue despite errors
            pass
    
    def _get_random_record(self, engine, table: TableConfig) -> Optional[Dict[str, Any]]:
        """Get a random record from a table."""
        try:
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return None
                
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # Check if we're using JDBC engine (has execute_query method)
            is_jdbc = hasattr(engine, 'execute_query')
            logger.debug(f"Using JDBC engine: {is_jdbc} for table {table_name}")
            
            # Handle differently based on engine type
            if is_jdbc:
                try:
                    # For JDBC engines, use execute_query method
                    # First, count the total number of records
                    count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
                    logger.debug(f"Executing count query: {count_stmt}")
                    
                    # Make sure we have a connection
                    if not engine.connection:
                        logger.info(f"No active connection, attempting to connect for {table_name}")
                        engine.connect()
                        
                    if not engine.connection:
                        logger.error(f"Failed to establish connection for {table_name}")
                        return None
                    
                    # Execute count query using execute_query method
                    count_result = engine.execute_query(count_stmt)
                except Exception as e:
                    logger.error(f"Error executing count query for {table_name}: {str(e)}")
                    return None
                if count_result:
                    # For JDBC, count_result is already a list of dictionaries
                    if len(count_result) > 0:
                        # Extract count value from the first row
                        count_value = count_result[0].get('cnt', 0)
                        
                        if count_value == 0:
                            logger.info(f"No records found in {table_name}")
                            return None
                        
                        # Get a random record - MS SQL Server uses TOP instead of LIMIT
                        if hasattr(engine, 'db_type') and engine.db_type == DatabaseType.MSSQL:
                            select_stmt = f"SELECT TOP 1 * FROM {table_name} ORDER BY NEWID()"
                        else:
                            # For other databases
                            offset = random.randint(0, count_value - 1)
                            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                        
                        logger.debug(f"Executing select query: {select_stmt}")
                        result = engine.execute_query(select_stmt)
                        
                        if result and len(result) > 0:
                            # Result is already a list of dictionaries
                            return result[0]
                    else:
                        logger.info(f"No records found in {table_name}")
                        return None
                
                return None
            else:
                # For JDBC engines with execute method (no db_connector attribute)
                # Check if engine has execute method directly
                try:
                    # Check if we have a db_connector object (JDBC connection)
                    if hasattr(engine, 'db_connector') and engine.db_connector:
                        # Use db_connector directly for JDBC connections
                        db_connector = engine.db_connector
                        logger.debug(f"Using db_connector directly for {table_name}")
                        
                        # Make sure we have a connection
                        if not db_connector.connection:
                            logger.info(f"No active connection, attempting to connect for {table_name}")
                            db_connector.connect()
                            
                        if not db_connector.connection:
                            logger.error(f"Failed to establish connection for {table_name}")
                            return None
                        
                        # First, count the total number of records
                        count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
                        
                        try:
                            cursor = db_connector.connection.cursor()
                            cursor.execute(count_stmt)
                            row = cursor.fetchone()
                            count_value = row[0] if row else 0
                            cursor.close()
                        except Exception as e:
                            logger.error(f"Error executing count query for {table_name}: {str(e)}")
                            return None
                        
                        if count_value == 0:
                            logger.info(f"No records found in {table_name}")
                            return None
                        
                        # Get a random record - MS SQL Server uses TOP instead of LIMIT
                        if db_connector.db_type == DatabaseType.MSSQL:
                            # For MS SQL Server
                            select_stmt = f"SELECT TOP 1 * FROM {table_name} ORDER BY NEWID()"
                        else:
                            # For other databases
                            offset = random.randint(0, count_value - 1)
                            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                        
                        try:
                            cursor = db_connector.connection.cursor()
                            cursor.execute(select_stmt)
                            row = cursor.fetchone()
                            
                            if row:
                                # Get column names
                                column_names = [column[0] for column in cursor.description]
                                # Convert row to dict
                                result_dict = {column_names[i]: value for i, value in enumerate(row)}
                                cursor.close()
                                return result_dict
                            cursor.close()
                        except Exception as e:
                            logger.error(f"Error executing select query for {table_name}: {str(e)}")
                            return None
                    
                    # Fallback to engine.execute if available
                    elif hasattr(engine, 'execute') and callable(engine.execute):
                        # Engine has direct execute method
                        logger.debug(f"Using engine with execute method for {table_name}")
                        
                        # First, count the total number of records
                        count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
                        
                        try:
                            count_result = engine.execute(count_stmt)
                        except Exception as e:
                            logger.error(f"Error executing count query for {table_name}: {str(e)}")
                            return None
                        
                        if count_result:
                            row = count_result.fetchone()
                            if row:
                                # Extract count value - might be at index 0 or might have a name 'cnt'
                                count_value = row[0] if isinstance(row, (list, tuple)) else row.get('cnt', 0)
                                
                                if count_value == 0:
                                    logger.info(f"No records found in {table_name}")
                                    return None
                                
                                # Get a random offset - MS SQL Server uses TOP instead of LIMIT
                                offset = random.randint(0, count_value - 1)
                                
                                # Query a random record based on database type
                                if hasattr(engine, 'db_connector') and engine.db_connector.db_type == DatabaseType.MSSQL:
                                    # For MS SQL Server
                                    select_stmt = f"SELECT TOP 1 * FROM {table_name} ORDER BY NEWID()"
                                else:
                                    # For other databases
                                    select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                                
                                try:
                                    result = engine.execute(select_stmt)
                                    if result:
                                        row = result.fetchone()
                                        if row:
                                            # Convert row to dict
                                            try:
                                                return {k: v for k, v in zip(result.keys(), row)}
                                            except Exception:
                                                # Fallback if keys() method is not available
                                                return {f"col_{i}": v for i, v in enumerate(row)}
                                except Exception as e:
                                    logger.error(f"Error executing select query for {table_name}: {str(e)}")
                                    return None
                    else:
                        logger.error(f"Engine does not have execute method or db_connector for {table_name}")
                        return None
                except Exception as e:
                    logger.error(f"Error in JDBC execution for {table_name}: {str(e)}")
                    return None
                
                return None
        
        except Exception as e:
            logger.error(f"Error getting random record from {table.table_name}: {str(e)}")
            return None
    
    def _generate_random_data(self, column_type: Any) -> Any:
        """Generate random data based on column type using Faker for more realistic data."""
        # Initialize Faker if not already done
        if not hasattr(self, '_faker'):
            from faker import Faker
            self._faker = Faker()
            logger.info("Initialized Faker for generating realistic test data")
        
        # Convert Java String to Python string if needed
        try:
            # Check if it's a Java String or other Java object
            if hasattr(column_type, 'toString'):
                column_type = str(column_type)
            # Check if it's some other non-string type
            elif not isinstance(column_type, str):
                column_type = str(column_type)
                
            # Now we should have a Python string
            column_type = column_type.lower()
        except Exception as e:
            # If anything goes wrong, log it and default to a string type
            logger.error(f"Error converting column type {type(column_type)}: {str(e)}")
            column_type = 'varchar'
        
        # Generate data based on column type
        if 'int' in column_type:
            return random.randint(1, 1000)
        elif 'float' in column_type or 'double' in column_type or 'real' in column_type:
            return round(random.uniform(1, 1000), 2)
        elif 'bool' in column_type:
            return random.choice([True, False])
        elif 'date' in column_type:
            # Use Faker for realistic dates in the last 3 years
            return self._faker.date_between(start_date='-3y', end_date='today').strftime('%Y-%m-%d')
        elif 'time' in column_type and 'timestamp' not in column_type:
            # Use Faker for realistic time
            return self._faker.time()
        elif 'timestamp' in column_type or 'datetime' in column_type:
            # Use Faker for realistic datetime in the last 3 years
            return self._faker.date_time_between(start_date='-3y', end_date='now').isoformat()
        elif 'char' in column_type or 'text' in column_type or 'string' in column_type:
            # Determine max length for the string
            length = 100
            if 'varchar' in column_type or 'character varying' in column_type:
                # Extract length from varchar(N)
                import re
                match = re.search(r'\((\d+)\)', column_type)
                if match:
                    length = min(int(match.group(1)), 100)  # Cap at 100 chars
            
            # Use different Faker providers based on column name hints (if available)
            col_name = getattr(column_type, '_col_name', '').lower() if hasattr(column_type, '_col_name') else ''
            
            # If we don't have column name info, use a generic approach
            if not col_name:
                # Generate different types of realistic data based on length
                if length < 10:
                    return self._faker.lexify('?' * min(length, 5))
                elif length < 20:
                    return self._faker.word()[:length]
                elif length < 50:
                    return self._faker.sentence(nb_words=5)[:length]
                else:
                    return self._faker.paragraph(nb_sentences=3)[:length]
            
            # Use column name hints to generate appropriate data
            if any(name in col_name for name in ['name', 'customer', 'person', 'user']):
                return self._faker.name()[:length]
            elif any(name in col_name for name in ['email', 'mail']):
                return self._faker.email()[:length]
            elif any(name in col_name for name in ['phone', 'tel', 'mobile']):
                return self._faker.phone_number()[:length]
            elif any(name in col_name for name in ['address', 'addr', 'street']):
                return self._faker.address()[:length]
            elif any(name in col_name for name in ['city', 'town']):
                return self._faker.city()[:length]
            elif any(name in col_name for name in ['country']):
                return self._faker.country()[:length]
            elif any(name in col_name for name in ['company', 'business', 'org']):
                return self._faker.company()[:length]
            elif any(name in col_name for name in ['job', 'position', 'title', 'role']):
                return self._faker.job()[:length]
            elif any(name in col_name for name in ['desc', 'description', 'comment', 'note']):
                return self._faker.text(max_nb_chars=length)
            elif any(name in col_name for name in ['id', 'code', 'number', 'num']):
                return self._faker.bothify('#' * min(8, length))[:length]
            else:
                # Default to a sentence or paragraph based on length
                if length < 30:
                    return self._faker.sentence(nb_words=3)[:length]
                else:
                    return self._faker.paragraph(nb_sentences=2)[:length]
        else:
            # Default to a word for unknown types
            return self._faker.word()[:30]
