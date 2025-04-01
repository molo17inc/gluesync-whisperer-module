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

import enum
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


class OperationType(enum.Enum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    ALL = "all"


class ConnectionStatus(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"
    BUSY = "busy"
    CONNECTED = "connected"


class DatabaseType(enum.Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MSSQL = "mssql"
    ORACLE = "oracle"
    AS400 = "as400"


class DatabaseConnection:
    """Database connection information."""
    
    def __init__(self, id=None, name=None, description=None, db_type=None, host=None, port=None,
                 username=None, password=None, database=None, database_name=None, connection_string=None, 
                 status=ConnectionStatus.IDLE, created_at=None, updated_at=None, last_operation_at=None):
        self.id = id
        self.name = name 
        self.description = description
        self.db_type = db_type
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        # Use database_name if provided, otherwise use database
        self.database = database_name if database_name is not None else database
        self.connection_string = connection_string
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.last_operation_at = last_operation_at
        self.tables = []
    
    @classmethod
    def from_row(cls, row):
        """Create a DatabaseConnection instance from a database row."""
        conn = cls(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            db_type=DatabaseType(row['db_type']),
            host=row['host'],
            port=row['port'],
            username=row['username'],
            password=row['password'],
            database_name=row['database_name'],
            connection_string=row['connection_string'],
            status=ConnectionStatus(row['status']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_operation_at=row['last_operation_at']
        )
        return conn
    
    def to_dict(self):
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'db_type': self.db_type.value if self.db_type else None,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'database_name': self.database,
            'connection_string': self.connection_string,
            'status': self.status.value if self.status else 'idle',
            'last_operation_at': self.last_operation_at
        }


class TableConfig:
    """Table configuration for database operations."""
    
    def __init__(self, id=None, connection_id=None, table_name=None, schema_name=None,
                 operation_type=OperationType.ALL, operation_delay=1.0, batch_size=1, enabled=True,
                 created_at=None, updated_at=None, column_definitions=None, primary_keys=None):
        self.id = id
        self.connection_id = connection_id
        self.table_name = table_name
        self.schema_name = schema_name
        self.operation_type = operation_type
        self.operation_delay = operation_delay
        self.batch_size = batch_size
        self.enabled = enabled
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.column_definitions = column_definitions or {}
        self.primary_keys = primary_keys or []
        self.operations = []
        self.connection = None  # Will be populated by service layer
    
    @classmethod
    def from_row(cls, row):
        """Create a TableConfig instance from a database row."""
        # Parse JSON strings from SQLite
        column_defs = json.loads(row['column_definitions']) if row['column_definitions'] else {}
        primary_keys = json.loads(row['primary_keys']) if row['primary_keys'] else []
        
        config = cls(
            id=row['id'],
            connection_id=row['connection_id'],
            table_name=row['table_name'],
            schema_name=row['schema_name'],
            operation_type=OperationType(row['operation_type']),
            operation_delay=row['operation_delay'],
            batch_size=row['batch_size'],
            enabled=bool(row['enabled']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            column_definitions=column_defs,
            primary_keys=primary_keys
        )
        return config
    
    def to_dict(self):
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'connection_id': self.connection_id,
            'table_name': self.table_name,
            'schema_name': self.schema_name,
            'operation_type': self.operation_type.value if self.operation_type else OperationType.ALL.value,
            'operation_delay': self.operation_delay,
            'batch_size': self.batch_size,
            'enabled': self.enabled,
            'column_definitions': json.dumps(self.column_definitions) if self.column_definitions else None,
            'primary_keys': json.dumps(self.primary_keys) if self.primary_keys else None
        }


class OperationLog:
    """Log of operations performed on a table."""
    
    def __init__(self, id=None, table_config_id=None, operation_type=None, record_id=None,
                 operation_data=None, status=None, error_message=None, created_at=None):
        self.id = id
        self.table_config_id = table_config_id
        self.operation_type = operation_type
        self.record_id = record_id
        self.operation_data = operation_data or {}
        self.status = status  # SUCCESS, FAILED
        self.error_message = error_message
        self.created_at = created_at or datetime.now()
        self.table_config = None  # Will be populated by service layer
    
    @classmethod
    def from_row(cls, row):
        """Create an OperationLog instance from a database row."""
        # Parse JSON strings from SQLite
        operation_data = json.loads(row['operation_data']) if row['operation_data'] else {}
        
        log = cls(
            id=row['id'],
            table_config_id=row['table_config_id'],
            operation_type=OperationType(row['operation_type']),
            record_id=row['record_id'],
            operation_data=operation_data,
            status=row['status'],
            error_message=row['error_message'],
            created_at=row['created_at']
        )
        return log
    
    def to_dict(self):
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'table_config_id': self.table_config_id,
            'operation_type': self.operation_type.value if self.operation_type else None,
            'record_id': self.record_id,
            'operation_data': json.dumps(self.operation_data) if self.operation_data else None,
            'status': self.status,
            'error_message': self.error_message
        }
