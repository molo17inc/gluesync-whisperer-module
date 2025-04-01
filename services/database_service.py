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
from typing import List, Dict, Any, Optional, Union

from models import DatabaseConnection
from schemas import TableSchemaResponse, ConnectionStatus, DatabaseConnectionCreate, DatabaseConnectionUpdate
from utils.db_connector import DatabaseType
from services.database_service_factory import DatabaseServiceFactory

logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Main database service that delegates to specific database type implementations.
    This class acts as a facade to the underlying database-specific services.
    """
    
    def __init__(self, db):
        """Initialize with database connection"""
        self.db = db
        self.services_cache = {}  # Cache for database services by connection ID
    
    def _get_service_for_connection_id(self, connection_id: int):
        """Get the appropriate database service for a connection ID"""
        # Return cached service if it exists
        if connection_id in self.services_cache:
            return self.services_cache[connection_id]
        
        # Get the connection
        connection = self._get_connection_direct(connection_id)
        
        # Create a service for this connection type
        service = DatabaseServiceFactory.get_service_for_connection(connection, self.db)
        
        # Cache the service
        self.services_cache[connection_id] = service
        
        return service
    
    def _get_connection_direct(self, connection_id: int) -> DatabaseConnection:
        """Get a connection directly from the database without using a service"""
        logger.info(f"Directly getting connection with ID: {connection_id}")
        query = "SELECT * FROM database_connections WHERE id = ?"
        result = self.db.query_one(query, (connection_id,))
        logger.info(f"Query result for connection ID {connection_id}: {result}")
        
        if not result:
            logger.error(f"Connection with ID {connection_id} not found")
            return None
        
        # Create a connection object
        connection = DatabaseConnection(
            id=result['id'],
            name=result['name'],
            description=result['description'],
            db_type=result['db_type'],
            host=result['host'],
            port=result['port'],
            database_name=result['database_name'],
            username=result['username'],
            password=result['password'],
            status=result['status'],
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            last_operation_at=result.get('last_operation_at'),
            connection_string=result['connection_string']
        )
        
        # Map database_name to database for compatibility
        connection.database = result['database_name']
        
        return connection
    
    # Public API methods that delegate to the appropriate service
    
    def create_connection(self, connection_data: DatabaseConnectionCreate) -> DatabaseConnection:
        """Create a new database connection."""
        # For creating a connection, we need to determine the service based on the db_type
        db_type = connection_data.db_type
        
        # Convert string db_type to enum if needed
        if isinstance(db_type, str):
            try:
                db_type = DatabaseType[db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {db_type}")
                raise ValueError(f"Unsupported database type: {db_type}")
        
        # Create a service for this database type
        service = DatabaseServiceFactory.create(db_type, self.db)
        
        # Use the service to create the connection
        return service.create_connection(connection_data)
    
    def get_connections(self, skip: int = 0, limit: int = 100) -> List[DatabaseConnection]:
        """Get all database connections."""
        # This doesn't need a specific service, so we'll use the base implementation
        query = "SELECT * FROM database_connections LIMIT ? OFFSET ?"
        rows = self.db.query(query, (limit, skip))
        
        connections = []
        for row in rows:
            connection = DatabaseConnection(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                db_type=row['db_type'],
                host=row['host'],
                port=row['port'],
                database_name=row['database_name'],
                username=row['username'],
                password=row['password'],
                status=row['status'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                last_operation_at=row.get('last_operation_at'),
                connection_string=row['connection_string']
            )
            connection.database = row['database_name']
            connections.append(connection)
        
        return connections
    
    def get_connection(self, connection_id: int) -> DatabaseConnection:
        """Get a specific database connection by ID."""
        # This doesn't need a specific service, so we'll use the base implementation
        return self._get_connection_direct(connection_id)
        
    def get_engine(self, connection: DatabaseConnection) -> Any:
        """Get a database engine for a connection.
        This method delegates to the appropriate service implementation.
        """
        logger.info(f"Getting engine for connection ID: {connection.id}")
        
        # Get the appropriate service
        service = self._get_service_for_connection_id(connection.id)
        
        if not service:
            logger.error(f"No service found for connection ID {connection.id}")
            return None
        
        # Get the engine from the service
        return service._get_engine(connection)
    
    def get_connection_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """Get a specific database connection by name."""
        # This doesn't need a specific service, so we'll use the base implementation
        query = "SELECT * FROM database_connections WHERE name = ?"
        result = self.db.query_one(query, (name,))
        if not result:
            return None
        
        connection = DatabaseConnection(
            id=result['id'],
            name=result['name'],
            description=result['description'],
            db_type=result['db_type'],
            host=result['host'],
            port=result['port'],
            database_name=result['database_name'],
            username=result['username'],
            password=result['password'],
            status=result['status'],
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            last_operation_at=result.get('last_operation_at'),
            connection_string=result['connection_string']
        )
        connection.database = result['database_name']
        
        return connection
    
    def update_connection(self, connection_id: int, connection_update: DatabaseConnectionUpdate) -> DatabaseConnection:
        """Update a database connection."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to update the connection
        return service.update_connection(connection_id, connection_update)
    
    def delete_connection(self, connection_id: int) -> None:
        """Delete a database connection."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to delete the connection
        service.delete_connection(connection_id)
        
        # Remove from cache if it exists
        if connection_id in self.services_cache:
            del self.services_cache[connection_id]
    
    def update_connection_status(self, connection_id: int, status: ConnectionStatus) -> DatabaseConnection:
        """Update a database connection status."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to update the connection status
        return service.update_connection_status(connection_id, status)
    
    def test_connection(self, connection_id: int) -> bool:
        """Test a database connection."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to test the connection
        return service.test_connection(connection_id)
    
    def get_schemas(self, connection_id: int) -> List[str]:
        """Get all schemas for a database connection."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to get schemas
        return service.get_schemas(connection_id)
    
    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        """Get all tables for a database connection."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to get tables
        return service.get_tables(connection_id, schema)
    
    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        # Get the service for this connection
        service = self._get_service_for_connection_id(connection_id)
        
        # Use the service to get table schema
        return service.get_table_schema(connection_id, table_name, schema_name)
