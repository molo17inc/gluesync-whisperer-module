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
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from models import DatabaseConnection
from schemas import TableSchemaResponse, ConnectionStatus, DatabaseConnectionCreate, DatabaseConnectionUpdate
from utils.db_connector import DatabaseConnector, DatabaseType

logger = logging.getLogger(__name__)

class DatabaseServiceBase(ABC):
    """Base class for database services"""
    
    def __init__(self, db):
        """Initialize with database connection"""
        self.db = db
        self.engines = {}  # Cache for database engines
    
    def create_connection(self, connection_data: DatabaseConnectionCreate) -> DatabaseConnection:
        """Create a new database connection."""
        logger.info(f"Creating connection with data: {connection_data}")
        
        # Check if connection with the same name already exists
        existing = self.get_connection_by_name(connection_data.name)
        if existing:
            logger.error(f"Connection with name '{connection_data.name}' already exists")
            raise ValueError(f"Connection with name '{connection_data.name}' already exists")
        
        # Create a new connection object
        connection = DatabaseConnection(
            name=connection_data.name,
            description=connection_data.description,
            db_type=connection_data.db_type,
            host=connection_data.host,
            port=connection_data.port,
            database=connection_data.database,  # Use database instead of database_name
            username=connection_data.username,
            password=connection_data.password,
            status=ConnectionStatus.IDLE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Build the connection string
        connection.connection_string = self._build_connection_string(connection)
        logger.info(f"Connection string built: {connection.connection_string}")
        
        # Insert into database
        query = """
        INSERT INTO database_connections 
        (name, description, host, port, database_name, username, password, db_type, status, created_at, updated_at, connection_string) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            connection.name, connection.description, connection.host, connection.port,
            connection.database, connection.username, connection.password,  # Use database instead of database_name
            connection.db_type.value if hasattr(connection.db_type, 'value') else connection.db_type,  # Convert enum to string
            connection.status.value if hasattr(connection.status, 'value') else connection.status,  # Convert enum to string
            connection.created_at,
            connection.updated_at, connection.connection_string
        )
        
        self.db.execute(query, params)
        logger.info("Database record inserted successfully")
        
        # Get the ID of the inserted record
        result = self.db.query_one("SELECT last_insert_rowid()")
        logger.info(f"Query result for last_insert_rowid: {result}")
        
        if result and 'last_insert_rowid()' in result:
            connection.id = result['last_insert_rowid()']
            if connection.id == 0:
                logger.warning("Got ID 0 from last_insert_rowid(), using ID 1 instead")
                connection.id = 1
        else:
            logger.warning("Failed to get ID from last_insert_rowid(), using ID 1")
            connection.id = 1
            
        logger.info(f"Connection created with ID: {connection.id}")
        return connection
    
    def get_connections(self, skip: int = 0, limit: int = 100) -> List[DatabaseConnection]:
        """Get all database connections."""
        query = "SELECT * FROM database_connections LIMIT ? OFFSET ?"
        rows = self.db.query(query, (limit, skip))
        return [self._map_db_to_model(row) for row in rows]
    
    def get_connection(self, connection_id: int) -> DatabaseConnection:
        """Get a specific database connection by ID."""
        logger.info(f"Attempting to get connection with ID: {connection_id}")
        query = "SELECT * FROM database_connections WHERE id = ?"
        result = self.db.query_one(query, (connection_id,))
        logger.info(f"Query result for connection ID {connection_id}: {result}")
        
        if not result:
            logger.error(f"Connection with ID {connection_id} not found")
            return None
            
        return self._map_db_to_model(result)
    
    def get_connection_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """Get a specific database connection by name."""
        query = "SELECT * FROM database_connections WHERE name = ?"
        result = self.db.query_one(query, (name,))
        if not result:
            return None
        return self._map_db_to_model(result)
    
    def _map_db_to_model(self, conn_data: dict) -> DatabaseConnection:
        """Map database column names to model field names."""
        # Create a connection object
        connection = DatabaseConnection(
            id=conn_data['id'],
            name=conn_data['name'],
            description=conn_data['description'],
            db_type=conn_data['db_type'],
            host=conn_data['host'],
            port=conn_data['port'],
            database=conn_data['database_name'],  # Use database instead of database_name
            username=conn_data['username'],
            password=conn_data['password'],
            status=conn_data['status'],
            created_at=conn_data['created_at'],
            updated_at=conn_data['updated_at'],
            last_operation_at=conn_data.get('last_operation_at'),
            connection_string=conn_data['connection_string']
        )
        
        return connection
    
    def update_connection(self, connection_id: int, connection_update: DatabaseConnectionUpdate) -> DatabaseConnection:
        """Update a database connection."""
        # Get the existing connection
        connection = self.get_connection(connection_id)
        
        # Update fields - handle enum fields specially to preserve enum types
        for field, value in connection_update.dict(exclude_unset=True).items():
            if field == 'db_type' and isinstance(value, str):
                # Handle db_type enum conversion
                if value.startswith('DatabaseType.'):
                    # Extract the enum name from "DatabaseType.MYSQL"
                    enum_name = value.split('.')[1]
                    value = DatabaseType[enum_name]
                else:
                    # Normal string conversion
                    value = DatabaseType[value.upper()]
            elif field == 'status' and isinstance(value, str):
                # Handle status enum conversion
                if value.startswith('ConnectionStatus.'):
                    # Extract the enum name from "ConnectionStatus.RUNNING"
                    enum_name = value.split('.')[1]
                    value = ConnectionStatus[enum_name]
                else:
                    # Normal string conversion
                    value = ConnectionStatus[value.upper()]
            setattr(connection, field, value)
        
        # Update the updated_at timestamp
        connection.updated_at = datetime.now()
        
        # Update the connection string if needed
        if any(field in connection_update.dict(exclude_unset=True) for field in ['host', 'port', 'database', 'username', 'password', 'db_type']):
            connection.connection_string = self._build_connection_string(connection)
        
        # Update in database
        query = """
        UPDATE database_connections 
        SET name = ?, description = ?, host = ?, port = ?, database_name = ?, 
            username = ?, password = ?, db_type = ?, status = ?, updated_at = ?, 
            connection_string = ?
        WHERE id = ?
        """
        params = (
            connection.name, connection.description, connection.host, connection.port,
            connection.database, connection.username, connection.password,  # Use database instead of database_name
            connection.db_type.value if hasattr(connection.db_type, 'value') else connection.db_type,  # Convert enum to string
            connection.status.value if hasattr(connection.status, 'value') else connection.status,  # Convert enum to string
            connection.updated_at,
            connection.connection_string, connection.id
        )
        
        self.db.execute(query, params)
        
        # Remove the engine from cache if it exists
        if connection_id in self.engines:
            del self.engines[connection_id]
        
        return connection
    
    def delete_connection(self, connection_id: int) -> None:
        """Delete a database connection."""
        # Check if connection exists
        self.get_connection(connection_id)
        
        # Delete from database
        query = "DELETE FROM database_connections WHERE id = ?"
        self.db.execute(query, (connection_id,))
        
        # Remove the engine from cache if it exists
        if connection_id in self.engines:
            del self.engines[connection_id]
    
    def update_connection_status(self, connection_id: int, status: ConnectionStatus) -> DatabaseConnection:
        """Update a database connection status."""
        # Get the existing connection
        connection = self.get_connection(connection_id)
        
        # Update status
        connection.status = status
        
        # Update the updated_at timestamp
        connection.updated_at = datetime.now()
        
        # If status is IDLE, update last_operation_at
        if status == ConnectionStatus.IDLE:
            connection.last_operation_at = datetime.now()
        
        # Update in database
        query = """
        UPDATE database_connections 
        SET status = ?, updated_at = ?, last_operation_at = ?
        WHERE id = ?
        """
        params = (
            connection.status.value if hasattr(connection.status, 'value') else connection.status,  # Convert enum to string
            connection.updated_at, connection.last_operation_at, connection.id
        )
        
        self.db.execute(query, params)
        
        return connection
    
    def test_connection(self, connection_id: int) -> bool:
        """Test a database connection."""
        # Get the connection
        connection = self.get_connection(connection_id)
        
        try:
            # Get the engine
            engine = self._get_engine(connection)
            
            # Try to connect
            if hasattr(engine, 'connect'):
                conn = engine.connect()
                if hasattr(conn, 'close'):
                    conn.close()
                return True
            return False
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return False
    
    @abstractmethod
    def get_schemas(self, connection_id: int) -> List[str]:
        """Get all schemas for a database connection."""
        pass
    
    @abstractmethod
    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        """Get all tables for a database connection."""
        pass
    
    @abstractmethod
    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        pass
    
    @abstractmethod
    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        """Build a connection string based on the database type and connection parameters."""
        pass
    
    @abstractmethod
    def _get_engine(self, connection: DatabaseConnection) -> Any:
        """Get or create a database engine for a connection."""
        pass
