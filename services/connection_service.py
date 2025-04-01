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
from typing import List, Optional, Dict, Any
from datetime import datetime

from models import DatabaseConnection, ConnectionStatus
from schemas import TableSchemaResponse

# Configure logging
logger = logging.getLogger(__name__)

class ConnectionService:
    """Service to manage database connections."""
    
    def __init__(self, db):
        """Initialize the connection service."""
        self.db = db
    
    def get_connections(self) -> List[DatabaseConnection]:
        """Get all database connections."""
        connections_data = self.db.query("SELECT * FROM database_connections")
        return [DatabaseConnection(**conn) for conn in connections_data]
    
    def get_connection(self, connection_id: int) -> Optional[DatabaseConnection]:
        """Get a database connection by ID."""
        connection_data = self.db.query_one("SELECT * FROM database_connections WHERE id = ?", (connection_id,))
        if connection_data:
            return DatabaseConnection(**connection_data)
        return None
    
    def create_connection(self, connection_data: dict) -> DatabaseConnection:
        """Create a new database connection."""
        try:
            # Ensure we have the required fields
            required_fields = ['name', 'db_type', 'host', 'port', 'username', 'password', 'database']
            for field in required_fields:
                if field not in connection_data:
                    raise ValueError(f"Missing required field: {field}")

            # Create the connection
            connection = DatabaseConnection(
                name=connection_data['name'],
                description=connection_data.get('description'),
                db_type=connection_data['db_type'],
                host=connection_data['host'],
                port=connection_data['port'],
                username=connection_data['username'],
                password=connection_data['password'],
                database=connection_data['database']
            )

            # Save to database
            self.db.execute('''
                INSERT INTO database_connections (
                    name, description, type, host, port, 
                    username, password, database, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                connection.name,
                connection.description,
                connection.db_type,
                connection.host,
                connection.port,
                connection.username,
                connection.password,
                connection.database,
                ConnectionStatus.IDLE.value,
                datetime.now(),
                datetime.now()
            ))
            self.db.commit()

            # Get the ID of the created connection
            connection.id = self.db.query_one('SELECT last_insert_rowid()')[0]
            return connection
        except Exception as e:
            logger.error(f"Error creating connection: {str(e)}")
            raise
    
    def update_connection(self, connection_id: int, connection: DatabaseConnection) -> Optional[DatabaseConnection]:
        """Update a database connection."""
        # Check if connection exists
        existing_connection = self.get_connection(connection_id)
        if not existing_connection:
            return None
        
        # Update the connection
        connection.updated_at = datetime.now()
        
        query = """
        UPDATE database_connections 
        SET name = ?, host = ?, port = ?, database = ?, username = ?, password = ?, 
            type = ?, driver = ?, schema = ?, status = ?, updated_at = ?, last_operation_at = ?
        WHERE id = ?
        """
        params = (
            connection.name,
            connection.host,
            connection.port,
            connection.database,
            connection.username,
            connection.password,
            connection.db_type.value if connection.db_type else None,
            connection.driver,
            connection.schema,
            connection.status.value if connection.status else None,
            connection.updated_at.isoformat() if connection.updated_at else None,
            connection.last_operation_at.isoformat() if connection.last_operation_at else None,
            connection_id
        )
        
        self.db.execute(query, params)
        self.db.commit()
        
        # Get the updated connection
        return self.get_connection(connection_id)
    
    def delete_connection(self, connection_id: int) -> bool:
        """Delete a database connection."""
        # Check if connection exists
        existing_connection = self.get_connection(connection_id)
        if not existing_connection:
            return False
        
        # Delete the connection
        self.db.execute("DELETE FROM database_connections WHERE id = ?", (connection_id,))
        self.db.commit()
        
        return True
    
    def get_tables(self, connection_id: int, schema: str) -> List[str]:
        """Get all tables for a connection with the specified schema."""
        # Get the connection
        connection = self.get_connection(connection_id)
        if not connection:
            return []
        
        # Get the database service
        from services.database_service import DatabaseService
        db_service = DatabaseService(self.db)
        
        # Get the tables
        return db_service.get_tables_for_schema(connection, schema)
    
    def get_table_schema(self, connection_id: int, table_name: str) -> TableSchemaResponse:
        """Get schema for a specific table."""
        # Get the connection
        connection = self.get_connection(connection_id)
        if not connection:
            return TableSchemaResponse(
                connection_id=connection_id,
                table_name=table_name,
                columns=[],
                primary_keys=[]
            )
        
        # Get the database service
        from services.database_service import DatabaseService
        db_service = DatabaseService(self.db)
        
        # Get the table schema
        schema_info = db_service.get_table_schema(connection, table_name)
        
        return TableSchemaResponse(
            connection_id=connection_id,
            table_name=table_name,
            columns=schema_info.get("columns", []),
            primary_keys=schema_info.get("primary_keys", [])
        )
    
    def table_exists(self, connection_id: int, table_name: str) -> bool:
        """Check if a table exists for a connection."""
        # Get the connection
        connection = self.get_connection(connection_id)
        if not connection:
            return False
        
        # Get the database service
        from services.database_service import DatabaseService
        db_service = DatabaseService(self.db)
        
        # Check if the table exists
        return db_service.table_exists(connection, table_name)
