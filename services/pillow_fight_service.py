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

from models import DatabaseConnection, TableConfig, OperationType, ConnectionStatus
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
        
        # Ensure the database_name field is used correctly
        connection_data['database_name'] = connection_data.pop('database', None)
        connection = DatabaseConnection(**connection_data)
        
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
        try:
            # Get the database engine
            engine = self.db_service._get_engine(connection)
            
            # Main loop for the pillow fight
            while not stop_event.is_set():
                # Perform a batch of operations
                for _ in range(batch_size):
                    # Randomly select an operation type
                    op_type = random.choice(operation_types)
                    
                    try:
                        # Perform the operation
                        if op_type == "INSERT":
                            self._perform_insert(engine, connection, table)
                            self.status[key]["operations"]["insert"] += 1
                        elif op_type == "UPDATE":
                            self._perform_update(engine, connection, table)
                            self.status[key]["operations"]["update"] += 1
                        elif op_type == "DELETE":
                            self._perform_delete(engine, connection, table)
                            self.status[key]["operations"]["delete"] += 1
                        
                        # Update the last operation time
                        self.status[key]["last_operation_time"] = datetime.now().isoformat()
                        
                    except Exception as e:
                        logger.error(f"Error performing {op_type} on {table.table_name}: {str(e)}")
                        self.status[key]["operations"]["errors"] += 1
                
                # Sleep for the specified delay
                time.sleep(operation_delay)
                
        except Exception as e:
            logger.error(f"Error in pillow fight thread for connection {connection.id} and table {table.id}: {str(e)}")
            self.status[key]["status"] = "error"
            self.status[key]["error"] = str(e)
        finally:
            # Update the status
            self.status[key]["status"] = "stopped"
            self.status[key]["duration"] = (
                datetime.now() - datetime.fromisoformat(self.status[key]["start_time"])
            ).total_seconds()
    
    def _perform_insert(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform an insert operation on a table."""
        try:
            # Get the table schema
            schema_info = self.db_service.get_table_schema(connection, table.table_name)
            columns = schema_info.get("columns", [])
            primary_keys = schema_info.get("primary_keys", [])
            
            # Generate random data for each column
            data = {}
            for column in columns:
                # Skip auto-increment columns
                if column["name"] in primary_keys and column.get("auto_increment", False):
                    continue
                
                # Generate random data based on column type
                data[column["name"]] = self._generate_random_data(column["type"])
            
            # Build the fully qualified table name
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
                
            # Build the insert statement
            placeholders = ', '.join(['?' for _ in data.keys()])
            stmt = f"INSERT INTO {table_name} ({', '.join(data.keys())}) VALUES ({placeholders})"
            
            # Execute the insert
            with engine.connect() as conn:
                conn.execute(stmt, list(data.values()))
            
            logger.info(f"Inserted record into {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing insert on {table.table_name}: {str(e)}")
            raise
    
    def _perform_update(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform an update operation on a table."""
        try:
            # Get the table schema
            schema_info = self.db_service.get_table_schema(connection, table.table_name)
            columns = schema_info.get("columns", [])
            primary_keys = schema_info.get("primary_keys", [])
            
            # First, get a random existing record
            existing_record = self._get_random_record(engine, table)
            
            if not existing_record:
                logger.info(f"No records found in {table.table_name} for update")
                return
            
            # Generate random data for each column, excluding primary keys
            data = {}
            for column in columns:
                if column["name"] not in primary_keys:
                    data[column["name"]] = self._generate_random_data(column["type"])
            
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
                
            set_clauses = [f"{col} = ?" for col in data.keys()]
            
            stmt = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
            
            # Execute the update
            with engine.connect() as conn:
                conn.execute(stmt, list(data.values()) + where_values)
            
            logger.info(f"Updated record in {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing update on {table.table_name}: {str(e)}")
            raise
    
    def _perform_delete(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform a delete operation on a table."""
        try:
            # Get the table schema
            schema_info = self.db_service.get_table_schema(connection, table.table_name)
            primary_keys = schema_info.get("primary_keys", [])
            
            # First, get a random existing record
            existing_record = self._get_random_record(engine, table)
            
            if not existing_record:
                logger.info(f"No records found in {table.table_name} for delete")
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
                
            stmt = f"DELETE FROM {table_name} WHERE {' AND '.join(where_clauses)}"
            
            # Execute the delete
            with engine.connect() as conn:
                conn.execute(stmt, where_values)
            
            logger.info(f"Deleted record from {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing delete on {table.table_name}: {str(e)}")
            raise
    
    def _get_random_record(self, engine, table: TableConfig) -> Optional[Dict[str, Any]]:
        """Get a random record from a table."""
        try:
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # First, count the total number of records
            count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
            
            with engine.connect() as conn:
                count_result = conn.execute(count_stmt).scalar()
            
            if not count_result or count_result == 0:
                return None
            
            # Get a random offset
            offset = random.randint(0, count_result - 1)
            
            # Query a random record
            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
            
            with engine.connect() as conn:
                result = conn.execute(select_stmt).mappings().first()
            
            if not result:
                return None
            
            # Convert to dictionary
            return dict(result)
        
        except Exception as e:
            logger.error(f"Error getting random record from {table.table_name}: {str(e)}")
            raise
    
    def _generate_random_data(self, column_type: str) -> Any:
        """Generate random data based on column type."""
        column_type = column_type.lower()
        
        if 'int' in column_type:
            return random.randint(1, 1000)
        elif 'float' in column_type or 'double' in column_type or 'real' in column_type:
            return round(random.uniform(1, 1000), 2)
        elif 'bool' in column_type:
            return random.choice([True, False])
        elif 'date' in column_type:
            # Random date in the last 365 days
            days = random.randint(0, 365)
            return (datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        elif 'time' in column_type and 'timestamp' not in column_type:
            # Random time
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            return f"{hour:02d}:{minute:02d}:{second:02d}"
        elif 'timestamp' in column_type or 'datetime' in column_type:
            # Random timestamp in the last 365 days
            days = random.randint(0, 365)
            hours = random.randint(0, 23)
            minutes = random.randint(0, 59)
            seconds = random.randint(0, 59)
            return (datetime.now() - datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)).isoformat()
        elif 'char' in column_type or 'text' in column_type or 'string' in column_type:
            # Random string
            length = 10
            if 'varchar' in column_type or 'character varying' in column_type:
                # Extract length from varchar(N)
                import re
                match = re.search(r'\((\d+)\)', column_type)
                if match:
                    length = min(int(match.group(1)), 100)  # Cap at 100 chars
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        else:
            # Default to string for unknown types
            return ''.join(random.choices(string.ascii_letters + string.digits, k=10))
