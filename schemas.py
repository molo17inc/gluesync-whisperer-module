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
    database: str


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
    database: Optional[str] = None
    status: Optional[ConnectionStatus] = None


class DatabaseConnectionResponse(DatabaseConnectionBase):
    id: int
    connection_string: Optional[str] = None
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime
    last_operation_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # SQLAlchemy 2.0 / Pydantic V2 compatibility


# Pydantic schemas for TableConfig
class TableConfigBase(BaseModel):
    table_name: str
    schema_name: Optional[str] = None
    operation_type: OperationType = OperationType.ALL
    operation_delay: float = Field(default=1.0, ge=0.1)  # Minimum 0.1 seconds delay
    batch_size: int = Field(default=1, ge=1)  # Minimum batch size of 1
    enabled: bool = True
    cascade_delete: bool = False  # Whether to cascade deletes for foreign key constraints


class TableConfigCreate(TableConfigBase):
    connection_id: int


class TableConfigUpdate(BaseModel):
    table_name: Optional[str] = None
    schema_name: Optional[str] = None
    operation_type: Optional[OperationType] = None
    operation_delay: Optional[float] = Field(default=None, ge=0.1)
    batch_size: Optional[int] = Field(default=None, ge=1)
    enabled: Optional[bool] = None
    cascade_delete: Optional[bool] = None


class TableConfigResponse(TableConfigBase):
    id: int
    connection_id: int
    column_definitions: Optional[Dict[str, Any]] = None
    primary_keys: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy 2.0 / Pydantic V2 compatibility


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
        from_attributes = True  # SQLAlchemy 2.0 / Pydantic V2 compatibility


# Additional schemas for specific operations
class ConnectionStatusUpdate(BaseModel):
    status: ConnectionStatus


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class TableListResponse(BaseModel):
    tables: List[str]


class TableResponse(BaseModel):
    name: str
    schema_name: str


class TableSchemaResponse(BaseModel):
    table_name: str
    columns: Dict[str, Any]
    primary_keys: List[str]


class TableOperationRequest(BaseModel):
    connection_id: int
    table_ids: List[int]
    operation_type: OperationType = OperationType.ALL
    operation_types: Optional[List[OperationType]] = None
    operation_delay: float = 1.0
    batch_size: int = 1


class PillowFightJobRequest(BaseModel):
    connection_id: int
    table_ids: List[int]
    operation_type: OperationType = OperationType.ALL
    operation_types: Optional[List[OperationType]] = None
    operation_delay: float = 1.0
    batch_size: int = 1


class PillowFightJobTableStatus(BaseModel):
    job_id: str
    table_id: int
    table_name: Optional[str] = None
    schema_name: Optional[str] = None
    status: str
    insert_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    error_count: int = 0
    last_operation_at: Optional[str] = None
    resume_cursor: Optional[str] = None


class PillowFightJobStatus(BaseModel):
    job_id: str
    connection_id: int
    status: str
    operation_types: List[str]
    operation_delay: float
    batch_size: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    error_message: Optional[str] = None
    tables: List[PillowFightJobTableStatus]


class PillowFightJobStatusResponse(BaseModel):
    jobs: List[PillowFightJobStatus]


class SqlQueryRequest(BaseModel):
    query: str
    schema_name: Optional[str] = None
    params: Optional[List[Any]] = None
    max_rows: int = Field(default=100, ge=1)  # Maximum number of rows to return


class SqlQueryResponse(BaseModel):
    success: bool
    message: str
    results: Optional[List[Dict[str, Any]]] = None
    column_names: Optional[List[str]] = None
    row_count: Optional[int] = None
