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

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

from models import OperationType, DatabaseType, ConnectionStatus


# Pydantic schemas for DatabaseConnection
class DatabaseConnectionBase(BaseModel):
    name: str
    description: Optional[str] = None
    db_type: DatabaseType
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: str


class DatabaseConnectionCreate(DatabaseConnectionBase):
    pass


class DatabaseConnectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    db_type: Optional[DatabaseType] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None
    status: Optional[ConnectionStatus] = None


class DatabaseConnectionResponse(DatabaseConnectionBase):
    id: int
    connection_string: str
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime
    last_operation_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# Pydantic schemas for TableConfig
class TableConfigBase(BaseModel):
    table_name: str
    schema_name: Optional[str] = None
    operation_type: OperationType = OperationType.ALL
    operation_delay: float = Field(default=1.0, ge=0.1)  # Minimum 0.1 seconds delay
    batch_size: int = Field(default=1, ge=1)  # Minimum batch size of 1
    enabled: bool = True


class TableConfigCreate(TableConfigBase):
    connection_id: int


class TableConfigUpdate(BaseModel):
    table_name: Optional[str] = None
    schema_name: Optional[str] = None
    operation_type: Optional[OperationType] = None
    operation_delay: Optional[float] = Field(default=None, ge=0.1)
    batch_size: Optional[int] = Field(default=None, ge=1)
    enabled: Optional[bool] = None


class TableConfigResponse(TableConfigBase):
    id: int
    connection_id: int
    column_definitions: Optional[Dict[str, Any]] = None
    primary_keys: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# Pydantic schemas for OperationLog
class OperationLogBase(BaseModel):
    operation_type: OperationType
    record_id: Optional[str] = None
    operation_data: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None


class OperationLogCreate(OperationLogBase):
    table_config_id: int


class OperationLogResponse(OperationLogBase):
    id: int
    table_config_id: int
    created_at: datetime

    class Config:
        orm_mode = True


# Additional schemas for specific operations
class ConnectionStatusUpdate(BaseModel):
    status: ConnectionStatus


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class TableListResponse(BaseModel):
    tables: List[str]


class TableSchemaResponse(BaseModel):
    table_name: str
    columns: Dict[str, Any]
    primary_keys: List[str]


class TableOperationRequest(BaseModel):
    connection_id: int
    table_names: List[str]
    operation_type: OperationType = OperationType.ALL
    operation_delay: float = 1.0
    batch_size: int = 1
