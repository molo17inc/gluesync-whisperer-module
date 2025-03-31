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
import random
import string
import time
import datetime
import threading
import uuid
import json
from typing import Dict, List, Any, Optional, Tuple

from models import DatabaseConnection, TableConfig, OperationLog, OperationType, ConnectionStatus
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global dictionary to track running whisperers
running_whisperers = {}


class WhispererService:
    def __init__(self, db):
        self.db = db
        self.stop_events = {}  # Connection ID -> threading.Event
        
    def start_whisperer(self, connection_id: int) -> None:
        """Start a whisperer for a connection."""
        # Check if the whisperer is already running
        global running_whisperers
        if connection_id in running_whisperers:
            logger.info(f"Whisperer for connection {connection_id} is already running")
            return
        
        # Create a stop event
        stop_event = threading.Event()
        self.stop_events[connection_id] = stop_event
        
        # Start the whisperer in a separate thread
        thread = threading.Thread(
            target=self._run_whisperer,
            args=(connection_id, stop_event),
            daemon=True
        )
        thread.start()
        
        # Add to tracking
        running_whisperers[connection_id] = {
            "thread": thread,
            "stop_event": stop_event,
            "started_at": datetime.datetime.now()
        }
        
        logger.info(f"Started whisperer for connection {connection_id}")
    
    def stop_whisperer(self, connection_id: int) -> None:
        """Stop a whisperer for a connection."""
        # Check if the whisperer is running
        global running_whisperers
        if connection_id not in running_whisperers:
            logger.info(f"Whisperer for connection {connection_id} is not running")
            return
        
        # Set the stop event
        stop_event = self.stop_events.get(connection_id)
        if stop_event:
            stop_event.set()
        
        # Remove from tracking
        if connection_id in running_whisperers:
            del running_whisperers[connection_id]
        
        # Remove from stop events
        if connection_id in self.stop_events:
            del self.stop_events[connection_id]
        
        logger.info(f"Stopped whisperer for connection {connection_id}")
    
    def pause_whisperer(self, connection_id: int) -> None:
        """Pause a whisperer for a connection."""
        # Check if the whisperer is running
        global running_whisperers
        if connection_id not in running_whisperers:
            logger.info(f"Whisperer for connection {connection_id} is not running")
            return
        
        # Get the connection
        db_connection = self.db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
        if not db_connection:
            logger.error(f"Connection with ID {connection_id} not found")
            return
        
        # Update the connection status to paused
        db_connection = DatabaseConnection(**db_connection)
        db_connection.status = ConnectionStatus.PAUSED
        self.db.execute("UPDATE database_connections SET status = ? WHERE id = ?", 
                        (ConnectionStatus.PAUSED.value, connection_id))
        self.db.commit()
        
        logger.info(f"Paused whisperer for connection {connection_id}")
    
    def resume_whisperer(self, connection_id: int) -> None:
        """Resume a paused whisperer for a connection."""
        # Check if the whisperer is running
        global running_whisperers
        if connection_id not in running_whisperers:
            logger.info(f"Whisperer for connection {connection_id} is not running")
            return
        
        # Get the connection
        db_connection = self.db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
        if not db_connection:
            logger.error(f"Connection with ID {connection_id} not found")
            return
        
        # Update the connection status to running
        db_connection = DatabaseConnection(**db_connection)
        db_connection.status = ConnectionStatus.RUNNING
        self.db.execute("UPDATE database_connections SET status = ? WHERE id = ?", 
                        (ConnectionStatus.RUNNING.value, connection_id))
        self.db.commit()
        
        logger.info(f"Resumed whisperer for connection {connection_id}")

    def _run_whisperer(self, connection_id: int, stop_event: threading.Event) -> None:
        """Run the whisperer for a connection."""
        try:
            # Create a new database connection for this thread
            from database import get_db
            db = get_db()
            
            # Get the connection
            db_connection_data = db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
            if not db_connection_data:
                logger.error(f"Connection with ID {connection_id} not found")
                return
            
            db_connection = DatabaseConnection(**db_connection_data)
            
            # Get the tables for this connection
            tables_data = db.query("SELECT * FROM table_configs WHERE connection_id = ? AND enabled = 1", (connection_id,))
            db_tables = [TableConfig(**table) for table in tables_data]
            
            if not db_tables:
                logger.error(f"No enabled tables found for connection {connection_id}")
                db.execute("UPDATE database_connections SET status = ? WHERE id = ?", 
                           (ConnectionStatus.IDLE.value, connection_id))
                db.commit()
                return
            
            # Get the database engine
            from services.database_service import DatabaseService
            db_service = DatabaseService(db)
            engine = db_service._get_engine(db_connection)
            
            # Main loop for the whisperer
            while not stop_event.is_set():
                # Refresh connection status from database
                db_connection_data = db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
                if db_connection_data:
                    db_connection = DatabaseConnection(**db_connection_data)
                
                # Check if the whisperer is paused
                if db_connection.status == ConnectionStatus.PAUSED:
                    time.sleep(1)
                    continue
                
                # Randomly select a table
                table = random.choice(db_tables)
                
                try:
                    # Perform the operation
                    self._perform_operation(engine, db, table)
                    
                    # Update the last operation time
                    db.execute("UPDATE database_connections SET last_operation_at = ? WHERE id = ?", 
                               (datetime.datetime.now().isoformat(), connection_id))
                    db.commit()
                    
                    # Sleep for the specified delay
                    time.sleep(table.operation_delay)
                except Exception as e:
                    logger.error(f"Error performing operation on table {table.table_name}: {str(e)}")
                    
                    # Log the operation failure
                    operation_log = {
                        "table_config_id": table.id,
                        "operation_type": OperationType.ALL.value,  # Default since the operation failed
                        "status": "FAILED",
                        "error_message": str(e),
                        "created_at": datetime.datetime.now().isoformat()
                    }
                    
                    db.execute(
                        "INSERT INTO operation_logs (table_config_id, operation_type, status, error_message, created_at) VALUES (?, ?, ?, ?, ?)",
                        (operation_log["table_config_id"], operation_log["operation_type"], 
                         operation_log["status"], operation_log["error_message"], operation_log["created_at"])
                    )
                    db.commit()
                    
                    # Sleep before retrying
                    time.sleep(5)
                    
        except Exception as e:
            logger.error(f"Error in whisperer thread for connection {connection_id}: {str(e)}")
        finally:
            # Update the connection status to idle
            try:
                db.execute("UPDATE database_connections SET status = ? WHERE id = ?", 
                           (ConnectionStatus.IDLE.value, connection_id))
                db.commit()
            except:
                pass
            
            # Remove from tracking
            global running_whisperers
            if connection_id in running_whisperers:
                del running_whisperers[connection_id]

    def _perform_operation(self, engine, db, table_config: TableConfig) -> None:
        """Perform a random operation on a table."""
        # Determine the operation type
        operation_type = table_config.operation_type
        
        # If ALL, randomly select an operation type based on configured weights
        if operation_type == OperationType.ALL:
            weights = [
                settings.INSERT_WEIGHT,
                settings.UPDATE_WEIGHT,
                settings.DELETE_WEIGHT
            ]
            operation_types = [
                OperationType.INSERT,
                OperationType.UPDATE,
                OperationType.DELETE
            ]
            operation_type = random.choices(operation_types, weights=weights, k=1)[0]
        
        # Get the table schema
        column_definitions = table_config.column_definitions
        primary_keys = table_config.primary_keys
        
        # Perform the selected operation
        if operation_type == OperationType.INSERT:
            self._perform_insert(engine, db, table_config, column_definitions, primary_keys)
        elif operation_type == OperationType.UPDATE:
            self._perform_update(engine, db, table_config, column_definitions, primary_keys)
        elif operation_type == OperationType.DELETE:
            self._perform_delete(engine, db, table_config, primary_keys)

    def _perform_insert(self, engine, db, table_config: TableConfig, column_definitions, primary_keys) -> None:
        """Perform an insert operation on a table."""
        try:
            # Generate random data for each column
            data = self._generate_random_data(column_definitions, primary_keys)
            
            # Build the fully qualified table name
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = f"{table_config.schema_name}.{table_name}"
                
            # Build the insert statement
            placeholders = ', '.join(['?' for _ in data.keys()])
            stmt = f"INSERT INTO {table_name} ({', '.join(data.keys())}) VALUES ({placeholders})"
            
            # Execute the insert
            with engine.connect() as conn:
                result = conn.execute(stmt, list(data.values()))
                inserted_id = result.lastrowid if hasattr(result, 'lastrowid') else None
            
            # Log the operation
            operation_log = {
                "table_config_id": table_config.id,
                "operation_type": OperationType.INSERT.value,
                "record_id": str(inserted_id) if inserted_id else None,
                "operation_data": json.dumps(data),
                "status": "SUCCESS",
                "created_at": datetime.datetime.now().isoformat()
            }
            
            db.execute(
                "INSERT INTO operation_logs (table_config_id, operation_type, record_id, operation_data, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (operation_log["table_config_id"], operation_log["operation_type"], 
                 operation_log["record_id"], operation_log["operation_data"], 
                 operation_log["status"], operation_log["created_at"])
            )
            db.commit()
            
            logger.info(f"Inserted record into {table_config.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing insert on {table_config.table_name}: {str(e)}")
            raise

    def _perform_update(self, engine, db, table_config: TableConfig, column_definitions, primary_keys) -> None:
        """Perform an update operation on a table."""
        try:
            # First, get a random existing record
            existing_record, record_id = self._get_random_record(engine, table_config, primary_keys)
            
            if not existing_record:
                logger.info(f"No records found in {table_config.table_name} for update")
                return
            
            # Generate random data for each column, excluding primary keys
            data = self._generate_random_data(
                column_definitions, 
                primary_keys, 
                exclude_primary_keys=True
            )
            
            # If no data to update (all columns are primary keys), return
            if not data:
                logger.info(f"No columns to update in {table_config.table_name}")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_values = []
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = ?")
                    where_values.append(existing_record[pk])
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table_config.table_name}")
                return
            
            # Build the update statement
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = f"{table_config.schema_name}.{table_name}"
                
            set_clauses = [f"{col} = ?" for col in data.keys()]
            
            stmt = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
            
            # Execute the update
            with engine.connect() as conn:
                conn.execute(stmt, list(data.values()) + where_values)
            
            # Log the operation
            operation_log = {
                "table_config_id": table_config.id,
                "operation_type": OperationType.UPDATE.value,
                "record_id": record_id,
                "operation_data": json.dumps({
                    "before": existing_record,
                    "after": data
                }),
                "status": "SUCCESS",
                "created_at": datetime.datetime.now().isoformat()
            }
            
            db.execute(
                "INSERT INTO operation_logs (table_config_id, operation_type, record_id, operation_data, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (operation_log["table_config_id"], operation_log["operation_type"], 
                 operation_log["record_id"], operation_log["operation_data"], 
                 operation_log["status"], operation_log["created_at"])
            )
            db.commit()
            
            logger.info(f"Updated record in {table_config.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing update on {table_config.table_name}: {str(e)}")
            raise

    def _perform_delete(self, engine, db, table_config: TableConfig, primary_keys) -> None:
        """Perform a delete operation on a table."""
        try:
            # First, get a random existing record
            existing_record, record_id = self._get_random_record(engine, table_config, primary_keys)
            
            if not existing_record:
                logger.info(f"No records found in {table_config.table_name} for delete")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_values = []
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = ?")
                    where_values.append(existing_record[pk])
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table_config.table_name}")
                return
            
            # Build the delete statement
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = f"{table_config.schema_name}.{table_name}"
                
            stmt = f"DELETE FROM {table_name} WHERE {' AND '.join(where_clauses)}"
            
            # Execute the delete
            with engine.connect() as conn:
                conn.execute(stmt, where_values)
            
            # Log the operation
            operation_log = {
                "table_config_id": table_config.id,
                "operation_type": OperationType.DELETE.value,
                "record_id": record_id,
                "operation_data": json.dumps(existing_record),
                "status": "SUCCESS",
                "created_at": datetime.datetime.now().isoformat()
            }
            
            db.execute(
                "INSERT INTO operation_logs (table_config_id, operation_type, record_id, operation_data, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (operation_log["table_config_id"], operation_log["operation_type"], 
                 operation_log["record_id"], operation_log["operation_data"], 
                 operation_log["status"], operation_log["created_at"])
            )
            db.commit()
            
            logger.info(f"Deleted record from {table_config.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing delete on {table_config.table_name}: {str(e)}")
            raise

    def _get_random_record(self, engine, table_config: TableConfig, primary_keys) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Get a random record from a table."""
        try:
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = f"{table_config.schema_name}.{table_name}"
            
            # First, count the total number of records
            count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
            
            with engine.connect() as conn:
                count_result = conn.execute(count_stmt).scalar()
            
            if not count_result or count_result == 0:
                return None, None
            
            # Get a random offset
            offset = random.randint(0, count_result - 1)
            
            # Query a random record
            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
            
            with engine.connect() as conn:
                result = conn.execute(select_stmt).mappings().first()
            
            if not result:
                return None, None
            
            # Convert to dictionary
            record = dict(result)
            
            # Determine record ID based on primary keys
            if primary_keys:
                record_id = "-".join([str(record[pk]) for pk in primary_keys if pk in record])
            else:
                record_id = str(uuid.uuid4())
            
            return record, record_id
        
        except Exception as e:
            logger.error(f"Error getting random record from {table_config.table_name}: {str(e)}")
            raise

    def _generate_random_data(
        self, 
        column_definitions, 
        primary_keys, 
        exclude_primary_keys=False
    ) -> Dict[str, Any]:
        """Generate random data for a table based on column definitions."""
        data = {}
        
        for column_name, column_info in column_definitions.items():
            # Skip primary keys in updates
            if exclude_primary_keys and column_name in primary_keys:
                continue
            
            # Skip generated columns (identity, computed, etc.)
            if column_info.get('default', '').lower().startswith(('nextval', 'uuid_generate')):
                continue
            
            # Skip columns with default values
            if 'default' in column_info and column_info['default'] is not None:
                continue
            
            # Generate random data based on column type
            column_type = column_info.get('type', '').lower()
            
            if 'int' in column_type:
                data[column_name] = random.randint(1, 1000)
            elif 'float' in column_type or 'double' in column_type or 'real' in column_type:
                data[column_name] = round(random.uniform(1, 1000), 2)
            elif 'bool' in column_type:
                data[column_name] = random.choice([True, False])
            elif 'date' in column_type:
                # Random date in the last 365 days
                days = random.randint(0, 365)
                data[column_name] = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
            elif 'time' in column_type and 'timestamp' not in column_type:
                # Random time
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                data[column_name] = f"{hour:02d}:{minute:02d}:{second:02d}"
            elif 'timestamp' in column_type or 'datetime' in column_type:
                # Random timestamp in the last 365 days
                days = random.randint(0, 365)
                hours = random.randint(0, 23)
                minutes = random.randint(0, 59)
                seconds = random.randint(0, 59)
                data[column_name] = (datetime.datetime.now() - datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)).isoformat()
            elif 'char' in column_type or 'text' in column_type or 'string' in column_type:
                # Random string
                length = min(10, int(column_info.get('length', 10)))
                data[column_name] = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            elif 'uuid' in column_type:
                data[column_name] = str(uuid.uuid4())
            else:
                # Default to string for unknown types
                data[column_name] = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        
        return data
