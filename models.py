#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Database Automator is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Database Automator.  If not, see <http://www.gnu.org/licenses/>.
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP

from database import Base


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


class DatabaseType(enum.Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MSSQL = "mssql"
    ORACLE = "oracle"


class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    db_type = Column(Enum(DatabaseType), nullable=False)
    host = Column(String, nullable=True)  # Null for SQLite
    port = Column(Integer, nullable=True)  # Null for SQLite
    username = Column(String, nullable=True)  # Null for SQLite
    password = Column(String, nullable=True)  # Null for SQLite
    database_name = Column(String, nullable=False)
    connection_string = Column(String, nullable=False)
    status = Column(Enum(ConnectionStatus), default=ConnectionStatus.IDLE)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    last_operation_at = Column(DateTime, nullable=True)
    
    # Relationship with TableConfig
    tables = relationship("TableConfig", back_populates="connection", cascade="all, delete-orphan")


class TableConfig(Base):
    __tablename__ = "table_configs"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False)
    table_name = Column(String, nullable=False)
    schema_name = Column(String, nullable=True)  # For databases that support schemas
    operation_type = Column(Enum(OperationType), nullable=False, default=OperationType.ALL)
    operation_delay = Column(Float, nullable=False, default=1.0)  # Delay in seconds between operations
    batch_size = Column(Integer, nullable=False, default=1)  # How many operations to perform in a batch
    enabled = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))
    
    # Store the table schema information
    column_definitions = Column(JSON, nullable=True)
    primary_keys = Column(JSON, nullable=True)
    
    # Relationship with DatabaseConnection
    connection = relationship("DatabaseConnection", back_populates="tables")
    
    # Relationship with OperationLog
    operations = relationship("OperationLog", back_populates="table_config", cascade="all, delete-orphan")
    
    # Define a unique constraint on connection_id and table_name
    __table_args__ = (
        # SQLAlchemy doesn't support direct unique constraints in the Column definition
        # So we define it here
        {'sqlite_autoincrement': True},
    )


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    table_config_id = Column(Integer, ForeignKey("table_configs.id", ondelete="CASCADE"), nullable=False)
    operation_type = Column(Enum(OperationType), nullable=False)
    record_id = Column(String, nullable=True)  # ID of the record affected, if available
    operation_data = Column(JSON, nullable=True)  # The data used in the operation
    status = Column(String, nullable=False)  # SUCCESS, FAILED
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    
    # Relationship with TableConfig
    table_config = relationship("TableConfig", back_populates="operations")
