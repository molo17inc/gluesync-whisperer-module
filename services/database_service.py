#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is dual-licensed under the following licenses:
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
import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from typing import List, Dict, Any, Optional

from models import DatabaseConnection, ConnectionStatus, DatabaseType
from schemas import DatabaseConnectionCreate, DatabaseConnectionUpdate, ConnectionTestResponse, TableSchemaResponse

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db: Session):
        self.db = db
        self.engines = {}  # Cache for database engines

    def create_connection(self, connection: DatabaseConnectionCreate) -> DatabaseConnection:
        """Create a new database connection."""
        # Build the connection string based on the database type
        connection_string = self._build_connection_string(connection)
        
        # Create the database connection record
        db_connection = DatabaseConnection(
            name=connection.name,
            description=connection.description,
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            database_name=connection.database_name,
            connection_string=connection_string,
            status=ConnectionStatus.IDLE
        )
        
        self.db.add(db_connection)
        self.db.commit()
        self.db.refresh(db_connection)
        
        return db_connection

    def get_connections(self, skip: int = 0, limit: int = 100) -> List[DatabaseConnection]:
        """Get all database connections."""
        return self.db.query(DatabaseConnection).offset(skip).limit(limit).all()

    def get_connection(self, connection_id: int) -> Optional[DatabaseConnection]:
        """Get a specific database connection by ID."""
        return self.db.query(DatabaseConnection).filter(DatabaseConnection.id == connection_id).first()

    def get_connection_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """Get a specific database connection by name."""
        return self.db.query(DatabaseConnection).filter(DatabaseConnection.name == name).first()

    def update_connection(self, connection_id: int, connection_update: DatabaseConnectionUpdate) -> DatabaseConnection:
        """Update a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Update fields that are provided
        update_data = connection_update.dict(exclude_unset=True)
        
        # If there are changes to connection parameters, rebuild the connection string
        rebuild_connection_string = False
        connection_params = ['db_type', 'host', 'port', 'username', 'password', 'database_name']
        for param in connection_params:
            if param in update_data:
                rebuild_connection_string = True
                break
        
        for key, value in update_data.items():
            setattr(db_connection, key, value)
        
        if rebuild_connection_string:
            connection_string = self._build_connection_string(db_connection)
            db_connection.connection_string = connection_string
            
            # Remove from engine cache if it exists
            if connection_id in self.engines:
                del self.engines[connection_id]
        
        self.db.commit()
        self.db.refresh(db_connection)
        
        return db_connection

    def delete_connection(self, connection_id: int) -> None:
        """Delete a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Remove from engine cache if it exists
        if connection_id in self.engines:
            del self.engines[connection_id]
        
        self.db.delete(db_connection)
        self.db.commit()

    def update_connection_status(self, connection_id: int, status: ConnectionStatus) -> DatabaseConnection:
        """Update a database connection status."""
        db_connection = self.get_connection(connection_id)
        db_connection.status = status
        
        self.db.commit()
        self.db.refresh(db_connection)
        
        return db_connection

    def test_connection(self, connection_id: int) -> ConnectionTestResponse:
        """Test a database connection."""
        db_connection = self.get_connection(connection_id)
        
        try:
            # Try to connect to the database
            engine = self._get_engine(db_connection)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            
            return ConnectionTestResponse(success=True, message="Connection successful")
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return ConnectionTestResponse(success=False, message=f"Connection failed: {str(e)}")

    def get_tables(self, connection_id: int) -> List[str]:
        """Get all tables for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Get the database engine
        engine = self._get_engine(db_connection)
        
        # Get all tables
        inspector = inspect(engine)
        # For some databases like PostgreSQL, we should specify the schema
        if db_connection.db_type == DatabaseType.POSTGRESQL:
            return inspector.get_table_names(schema='public')
        else:
            return inspector.get_table_names()

    def get_table_schema(self, connection_id: int, table_name: str) -> TableSchemaResponse:
        """Get the schema of a table."""
        db_connection = self.get_connection(connection_id)
        
        # Get the database engine
        engine = self._get_engine(db_connection)
        
        # Get table schema
        inspector = inspect(engine)
        
        # Get column information
        columns = {}
        primary_keys = []
        
        # For PostgreSQL, we might need to specify the schema
        schema = None
        if db_connection.db_type == DatabaseType.POSTGRESQL:
            schema = 'public'
        
        # Get primary key columns
        pk_constraint = inspector.get_pk_constraint(table_name, schema=schema)
        if pk_constraint and 'constrained_columns' in pk_constraint:
            primary_keys = pk_constraint['constrained_columns']
        
        # Get column details
        for column in inspector.get_columns(table_name, schema=schema):
            col_name = column['name']
            col_type = str(column['type'])
            columns[col_name] = {
                'type': col_type,
                'nullable': column.get('nullable', True),
                'default': str(column.get('default', None)) if column.get('default') else None,
                'is_primary_key': col_name in primary_keys
            }
        
        return TableSchemaResponse(
            table_name=table_name,
            columns=columns,
            primary_keys=primary_keys
        )

    def _build_connection_string(self, connection) -> str:
        """
        Build a connection string based on the database type and connection parameters.
        """
        if connection.db_type == DatabaseType.MYSQL:
            # MySQL: mysql+pymysql://username:password@host:port/database
            return f"mysql+pymysql://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
        
        elif connection.db_type == DatabaseType.POSTGRESQL:
            # PostgreSQL: postgresql://username:password@host:port/database
            return f"postgresql://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
        
        elif connection.db_type == DatabaseType.SQLITE:
            # SQLite: sqlite:///path/to/database.db
            return f"sqlite:///{connection.database_name}"
        
        elif connection.db_type == DatabaseType.MSSQL:
            # MSSQL: mssql+pyodbc://username:password@host:port/database?driver=ODBC+Driver+17+for+SQL+Server
            driver = "ODBC+Driver+17+for+SQL+Server"
            return f"mssql+pyodbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver={driver}"
        
        elif connection.db_type == DatabaseType.ORACLE:
            # Oracle: oracle+cx_oracle://username:password@host:port/service_name
            return f"oracle+cx_oracle://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
        
        else:
            raise ValueError(f"Unsupported database type: {connection.db_type}")

    def _get_engine(self, connection: DatabaseConnection):
        """
        Get or create a database engine for a connection.
        """
        connection_id = connection.id
        
        # Return cached engine if available
        if connection_id in self.engines:
            return self.engines[connection_id]
        
        # Create a new engine
        try:
            # Use NullPool to avoid leaving connections open
            engine = create_engine(connection.connection_string, poolclass=NullPool)
            self.engines[connection_id] = engine
            return engine
        except Exception as e:
            logger.error(f"Error creating database engine: {str(e)}")
            raise Exception(f"Failed to create database engine: {str(e)}")
