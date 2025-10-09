#!/usr/bin/env python3
"""
 * This file is part of Gluesync Whisperer.
 *
 * Gluesync Whisperer is dual-licensed under the following licenses:
 * - GNU Affero General Public License v3.0
 * - Gluesync Commercial License
 *
 * You can choose between one of them if you use this software.
 *
 * For more information about the Gluesync Commercial License
 * contact us at info@gluesync.com
 *
 * GNU Affero General Public License v3.0:
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
"""

import logging
import sqlite3
from typing import List, Dict, Any, Optional

from models import DatabaseConnection
from schemas import TableSchemaResponse
from utils.db_connector import DatabaseType
from services.database_service_base import DatabaseServiceBase

logger = logging.getLogger(__name__)

class SqliteWrapper:
    """Simple wrapper for SQLite connections to provide a consistent interface"""
    
    def __init__(self, db_path):
        self.db_path = db_path.replace('sqlite:///', '')
        self.connection = None
        
    def connect(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        return self
    
    def execute(self, query, params=None):
        if not self.connection:
            self.connect()
        return self.connection.execute(query, params or ())
    
    def get_schemas(self):
        # SQLite doesn't have schemas in the same way as other databases
        return ["main"]
    
    def get_tables(self, schema=None):
        cursor = self.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
    
    def dispose(self):
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

class SQLiteDatabaseService(DatabaseServiceBase):
    """SQLite specific database service implementation"""
    
    def get_schemas(self, connection_id: int) -> List[str]:
        """Get all schemas for a database connection."""
        # SQLite doesn't have schemas in the same way as other databases
        return ["main"]
    
    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        """Get all tables for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Create a database connector
        engine = self._get_engine(db_connection)
        
        try:
            # Use the engine to get tables
            if hasattr(engine, 'get_tables'):
                table_names = engine.get_tables(schema)
                # Convert string list to object format for consistency
                return [{"name": table, "schema": schema or "main"} for table in table_names]
            
            # Fallback for direct SQL query
            cursor = engine.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = [row[0] for row in cursor.fetchall()]
            return [{"name": table, "schema": "main"} for table in table_names]
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            raise
    
    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        logger.info(f"DATABASE_SERVICE: get_table_schema called for table {table_name} in connection {connection_id}")
        db_connection = self.get_connection(connection_id)
        
        # Create a database connector
        engine = self._get_engine(db_connection)
        
        try:
            # Check if table exists
            cursor = engine.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
                (table_name,)
            )
            if not cursor.fetchone():
                logger.error(f"Table {table_name} not found")
                return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
            
            # Get columns
            columns = {}
            cursor = engine.execute(f"PRAGMA table_info({table_name})")
            for row in cursor.fetchall():
                column_name = row['name']
                column_type = row['type']
                nullable = row['notnull'] == 0
                default = row['dflt_value']
                primary_key = row['pk'] == 1
                
                columns[column_name] = {
                    "name": column_name,
                    "type": column_type,
                    "nullable": nullable,
                    "default": default,
                    "primary_key": primary_key
                }
                
                logger.info(f"Found column: {column_name} ({column_type})")
            
            # Get primary keys
            primary_keys = []
            for column_name, column_info in columns.items():
                if column_info["primary_key"]:
                    primary_keys.append(column_name)
            
            logger.info(f"Retrieved {len(columns)} columns and {len(primary_keys)} primary keys for {table_name}")
            
            return TableSchemaResponse(table_name=table_name, columns=columns, primary_keys=primary_keys)
        except Exception as e:
            logger.error(f"Error getting table schema: {str(e)}")
            return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
    
    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        """Build a connection string based on the database type and connection parameters."""
        if connection.db_type == DatabaseType.SQLITE:
            # Use SQLite file path
            return f"sqlite:///{connection.database}"
        else:
            raise ValueError(f"Unsupported database type: {connection.db_type}")
    
    def _get_engine(self, connection: DatabaseConnection) -> Any:
        """Get or create a database engine for a connection."""
        connection_id = connection.id
        
        # Return cached engine if it exists
        if connection_id in self.engines:
            return self.engines[connection_id]
        
        try:
            # Extract the database path from the connection string
            db_path = connection.connection_string
            logger.info(f"Creating SQLite connection to {db_path}")
            engine = SqliteWrapper(db_path)
            self.engines[connection_id] = engine
            return engine
        except Exception as e:
            logger.error(f"Error creating SQLite connection: {str(e)}")
            raise Exception(f"Failed to create SQLite connection: {str(e)}")
