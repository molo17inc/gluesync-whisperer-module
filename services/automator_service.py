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
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import text, insert, update, delete, select, MetaData, Table, Column
from sqlalchemy.orm import Session
from sqlalchemy.sql import quoted_name

from models import DatabaseConnection, TableConfig, OperationLog, OperationType, ConnectionStatus
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global dictionary to track running whisperers
running_whisperers = {}


class WhispererService:
    def __init__(self, db: Session):
        self.db = db
        self.stop_events = {}  # Connection ID -> threading.Event
        
    async def test_connection(self) -> Tuple[bool, str]:
        """Test a database connection"""
        try:
            # Use the DatabaseService to test the connection
            from services.database_service import DatabaseService
            db_service = DatabaseService(self.db)
            return True, "Connection successful"
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False, f"Connection failed: {str(e)}"
            
    async def list_tables(self, connection_id: int = None) -> List[str]:
        """List all tables for a connection"""
        try:
            # Use the DatabaseService to get the actual tables from the connection
            from services.database_service import DatabaseService
            db_service = DatabaseService(self.db)
            
            if connection_id is None:
                # If no connection ID is provided, get the first available connection
                connections = db_service.get_connections(limit=1)
                if not connections:
                    logger.error("No database connections found")
                    return []
                connection_id = connections[0].id
                
            # Get tables from the actual database connection
            return db_service.get_tables(connection_id)
        except Exception as e:
            logger.error(f"Failed to list tables: {str(e)}")
            return []

    def start_whisperer(self, connection_id: int) -> None:
        """Start the whisperer for a connection."""
        global running_whisperers
        
        # Get the connection
        db_connection = self.db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
        
        if not db_connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
        
        # Update the connection status
        db_connection.status = ConnectionStatus.RUNNING
        self.db.commit()
        
        # Create a stop event for this connection if it doesn't exist
        if connection_id not in self.stop_events:
            self.stop_events[connection_id] = threading.Event()
        else:
            # Reset the event if it exists
            self.stop_events[connection_id].clear()
        
        # Check if there's already an whisperer running for this connection
        if connection_id in running_whisperers:
            logger.info(f"Whisperer already running for connection {connection_id}")
            return
        
        # Start the whisperer in a new thread
        whisperer_thread = threading.Thread(
            target=self._run_whisperer,
            args=(connection_id, self.stop_events[connection_id]),
            daemon=True
        )
        whisperer_thread.start()
        
        # Track the running whisperer
        running_whisperers[connection_id] = whisperer_thread
        logger.info(f"Started whisperer for connection {connection_id}")

    def stop_whisperer(self, connection_id: int) -> None:
        """Stop the whisperer for a connection."""
        global running_whisperers
        
        # Get the connection
        db_connection = self.db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
        
        if not db_connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
        
        # Check if the whisperer is running
        if connection_id not in running_whisperers:
            logger.info(f"No whisperer running for connection {connection_id}")
            return
        
        # Signal the whisperer to stop
        if connection_id in self.stop_events:
            self.stop_events[connection_id].set()
        
        # Update the connection status
        db_connection.status = ConnectionStatus.IDLE
        self.db.commit()
        
        # Remove from tracking
        if connection_id in running_whisperers:
            del running_whisperers[connection_id]
        
        logger.info(f"Stopped whisperer for connection {connection_id}")

    def pause_whisperer(self, connection_id: int) -> None:
        """Pause the whisperer for a connection."""
        # Get the connection
        db_connection = self.db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
        
        if not db_connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
        
        # Check if the whisperer is running
        if connection_id not in running_whisperers:
            logger.info(f"No whisperer running for connection {connection_id}")
            return
        
        # Update the connection status to paused
        db_connection.status = ConnectionStatus.PAUSED
        self.db.commit()
        
        logger.info(f"Paused whisperer for connection {connection_id}")

    def resume_whisperer(self, connection_id: int) -> None:
        """Resume the whisperer for a connection."""
        # Get the connection
        db_connection = self.db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
        
        if not db_connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
        
        # Check if the whisperer is paused
        if db_connection.status != ConnectionStatus.PAUSED:
            logger.info(f"Whisperer for connection {connection_id} is not paused")
            return
        
        # Update the connection status to running
        db_connection.status = ConnectionStatus.RUNNING
        self.db.commit()
        
        logger.info(f"Resumed whisperer for connection {connection_id}")

    def _run_whisperer(self, connection_id: int, stop_event: threading.Event) -> None:
        """Run the whisperer for a connection."""
        try:
            # Create a new session for this thread
            from database import SessionLocal
            db = SessionLocal()
            
            # Get the connection
            db_connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id
            ).first()
            
            if not db_connection:
                logger.error(f"Connection with ID {connection_id} not found")
                return
            
            # Get the tables for this connection
            db_tables = db.query(TableConfig).filter(
                TableConfig.connection_id == connection_id,
                TableConfig.enabled == True
            ).all()
            
            if not db_tables:
                logger.error(f"No enabled tables found for connection {connection_id}")
                db_connection.status = ConnectionStatus.IDLE
                db.commit()
                return
            
            # Get the database engine
            from services.database_service import DatabaseService
            db_service = DatabaseService(db)
            engine = db_service._get_engine(db_connection)
            
            # Main loop for the whisperer
            while not stop_event.is_set():
                # Refresh connection status from database
                db.refresh(db_connection)
                
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
                    db_connection.last_operation_at = datetime.datetime.now()
                    db.commit()
                    
                    # Sleep for the specified delay
                    time.sleep(table.operation_delay)
                except Exception as e:
                    logger.error(f"Error performing operation on table {table.table_name}: {str(e)}")
                    
                    # Log the operation failure
                    operation_log = OperationLog(
                        table_config_id=table.id,
                        operation_type=OperationType.ALL,  # Default since the operation failed
                        status="FAILED",
                        error_message=str(e)
                    )
                    db.add(operation_log)
                    db.commit()
                    
                    # Sleep a bit before trying again
                    time.sleep(1)
        
        except Exception as e:
            logger.error(f"Error running whisperer for connection {connection_id}: {str(e)}")
            
            try:
                # Update the connection status to error
                db_connection = db.query(DatabaseConnection).filter(
                    DatabaseConnection.id == connection_id
                ).first()
                
                if db_connection:
                    db_connection.status = ConnectionStatus.ERROR
                    db.commit()
            except Exception as inner_e:
                logger.error(f"Error updating connection status: {str(inner_e)}")
        
        finally:
            # Clean up
            if 'db' in locals():
                db.close()
            
            # Remove from tracking
            global running_whisperers
            if connection_id in running_whisperers:
                del running_whisperers[connection_id]

    def _perform_operation(self, engine, db: Session, table_config: TableConfig) -> None:
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

    def _perform_insert(self, engine, db: Session, table_config: TableConfig, column_definitions, primary_keys) -> None:
        """Perform an insert operation on a table."""
        try:
            # Generate random data for each column
            data = self._generate_random_data(column_definitions, primary_keys)
            
            # Build the table object using SQLAlchemy core
            metadata = MetaData()
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = quoted_name(f"{table_config.schema_name}.{table_name}", True)
                
            # Build the insert statement
            stmt = text(f"INSERT INTO {table_name} ({', '.join(data.keys())}) VALUES ({', '.join([':' + k for k in data.keys()])})")
            
            # Execute the insert
            with engine.begin() as conn:
                result = conn.execute(stmt, data)
                inserted_id = result.lastrowid if result.lastrowid else None
            
            # Log the operation
            operation_log = OperationLog(
                table_config_id=table_config.id,
                operation_type=OperationType.INSERT,
                record_id=str(inserted_id) if inserted_id else None,
                operation_data=data,
                status="SUCCESS"
            )
            db.add(operation_log)
            db.commit()
            
            logger.info(f"Inserted record into {table_config.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing insert on {table_config.table_name}: {str(e)}")
            raise

    def _perform_update(self, engine, db: Session, table_config: TableConfig, column_definitions, primary_keys) -> None:
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
            where_data = {}
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = :where_{pk}")
                    where_data[f"where_{pk}"] = existing_record[pk]
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table_config.table_name}")
                return
            
            # Build the update statement
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = quoted_name(f"{table_config.schema_name}.{table_name}", True)
                
            set_clauses = [f"{col} = :set_{col}" for col in data.keys()]
            set_data = {f"set_{col}": value for col, value in data.items()}
            
            stmt = text(f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}")
            
            # Combine the set data and where data
            combined_data = {**set_data, **where_data}
            
            # Execute the update
            with engine.begin() as conn:
                result = conn.execute(stmt, combined_data)
            
            # Log the operation
            operation_log = OperationLog(
                table_config_id=table_config.id,
                operation_type=OperationType.UPDATE,
                record_id=record_id,
                operation_data={
                    "before": existing_record,
                    "after": data
                },
                status="SUCCESS"
            )
            db.add(operation_log)
            db.commit()
            
            logger.info(f"Updated record in {table_config.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing update on {table_config.table_name}: {str(e)}")
            raise

    def _perform_delete(self, engine, db: Session, table_config: TableConfig, primary_keys) -> None:
        """Perform a delete operation on a table."""
        try:
            # First, get a random existing record
            existing_record, record_id = self._get_random_record(engine, table_config, primary_keys)
            
            if not existing_record:
                logger.info(f"No records found in {table_config.table_name} for delete")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_data = {}
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = :where_{pk}")
                    where_data[f"where_{pk}"] = existing_record[pk]
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table_config.table_name}")
                return
            
            # Build the delete statement
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = quoted_name(f"{table_config.schema_name}.{table_name}", True)
                
            stmt = text(f"DELETE FROM {table_name} WHERE {' AND '.join(where_clauses)}")
            
            # Execute the delete
            with engine.begin() as conn:
                conn.execute(stmt, where_data)
            
            # Log the operation
            operation_log = OperationLog(
                table_config_id=table_config.id,
                operation_type=OperationType.DELETE,
                record_id=record_id,
                operation_data=existing_record,
                status="SUCCESS"
            )
            db.add(operation_log)
            db.commit()
            
            logger.info(f"Deleted record from {table_config.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing delete on {table_config.table_name}: {str(e)}")
            raise

    def _get_random_record(self, engine, table_config: TableConfig, primary_keys) -> Tuple[Dict[str, Any], str]:
        """Get a random record from a table."""
        try:
            table_name = table_config.table_name
            if table_config.schema_name:
                table_name = quoted_name(f"{table_config.schema_name}.{table_name}", True)
            
            # First, count the total number of records
            count_stmt = text(f"SELECT COUNT(*) as cnt FROM {table_name}")
            
            with engine.connect() as conn:
                count_result = conn.execute(count_stmt).scalar()
            
            if not count_result or count_result == 0:
                return None, None
            
            # Get a random offset
            offset = random.randint(0, count_result - 1)
            
            # Query a random record
            select_stmt = text(f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}")
            
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
            
            col_type = column_info.get('type', '').lower()
            nullable = column_info.get('nullable', True)
            
            # If column is nullable, sometimes set it to NULL
            if nullable and random.random() < 0.2:
                data[column_name] = None
                continue
            
            # Generate data based on column type
            data[column_name] = self._generate_value_for_type(col_type)
        
        return data

    def _generate_value_for_type(self, col_type: str) -> Any:
        """Generate a random value for a given SQL type."""
        # Integer types
        if any(t in col_type for t in ['int', 'serial', 'smallint', 'bigint']):
            return random.randint(1, 10000)
        
        # Decimal/numeric types
        elif any(t in col_type for t in ['decimal', 'numeric', 'real', 'double', 'float']):
            return round(random.uniform(1.0, 1000.0), 2)
        
        # Boolean type
        elif 'bool' in col_type:
            return random.choice([True, False])
        
        # Date type
        elif 'date' in col_type:
            days = random.randint(0, 365 * 5)  # Random date within past 5 years
            return (datetime.datetime.now() - datetime.timedelta(days=days)).date()
        
        # Time type
        elif 'time' in col_type and 'timestamp' not in col_type:
            hours = random.randint(0, 23)
            minutes = random.randint(0, 59)
            seconds = random.randint(0, 59)
            return datetime.time(hours, minutes, seconds)
        
        # Timestamp type
        elif 'timestamp' in col_type:
            days = random.randint(0, 365 * 5)  # Random date within past 5 years
            hours = random.randint(0, 23)
            minutes = random.randint(0, 59)
            seconds = random.randint(0, 59)
            return datetime.datetime.now() - datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        
        # UUID type
        elif 'uuid' in col_type:
            return str(uuid.uuid4())
        
        # Character types
        elif any(t in col_type for t in ['char', 'text', 'varchar']):
            # Get the max length if specified
            max_length = 50  # Default
            if '(' in col_type and ')' in col_type:
                length_str = col_type.split('(')[1].split(')')[0]
                try:
                    max_length = int(length_str)
                except ValueError:
                    pass
            
            # For very small char fields
            if max_length < 5:
                return ''.join(random.choices(string.ascii_letters, k=max_length))
            
            # Generate a random string
            length = random.randint(5, min(max_length, 50))
            return ''.join(random.choices(string.ascii_letters + string.digits + ' ', k=length))
        
        # JSON type
        elif 'json' in col_type:
            # Generate a simple JSON object
            keys = [''.join(random.choices(string.ascii_lowercase, k=5)) for _ in range(random.randint(1, 3))]
            values = [random.randint(1, 100) for _ in range(len(keys))]
            return dict(zip(keys, values))
        
        # Binary type
        elif any(t in col_type for t in ['blob', 'bytea', 'binary']):
            # Generate a small binary value
            return bytes([random.randint(0, 255) for _ in range(10)])
        
        # Default: return a string
        else:
            return ''.join(random.choices(string.ascii_letters, k=10))
