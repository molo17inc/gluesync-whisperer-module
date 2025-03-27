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
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import TableConfig, OperationType
from schemas import TableConfigCreate, TableConfigUpdate, TableOperationRequest
from services.whisperer_service import WhispererService

# Configure logging
logger = logging.getLogger(__name__)


class TableService:
    def __init__(self, db: Session):
        self.db = db
        self.whisperer_service = WhispererService(db)

    def create_table(
        self, 
        table: TableConfigCreate, 
        column_definitions: Dict[str, Any], 
        primary_keys: List[str]
    ) -> TableConfig:
        """Create a new table configuration for automation."""
        db_table = TableConfig(
            connection_id=table.connection_id,
            table_name=table.table_name,
            schema_name=table.schema_name,
            operation_type=table.operation_type,
            operation_delay=table.operation_delay,
            batch_size=table.batch_size,
            enabled=table.enabled,
            column_definitions=column_definitions,
            primary_keys=primary_keys
        )
        
        self.db.add(db_table)
        self.db.commit()
        self.db.refresh(db_table)
        
        return db_table

    def get_tables(self, skip: int = 0, limit: int = 100) -> List[TableConfig]:
        """Get all table configurations."""
        stmt = select(TableConfig).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_tables_by_connection(self, connection_id: int, skip: int = 0, limit: int = 100) -> List[TableConfig]:
        """Get all table configurations for a connection."""
        stmt = (
            select(TableConfig)
            .where(TableConfig.connection_id == connection_id)
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_table(self, table_id: int) -> Optional[TableConfig]:
        """Get a specific table configuration by ID."""
        stmt = select(TableConfig).where(TableConfig.id == table_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_table_by_name_and_connection(self, connection_id: int, table_name: str) -> Optional[TableConfig]:
        """Get a specific table configuration by connection ID and table name."""
        stmt = (
            select(TableConfig)
            .where(
                TableConfig.connection_id == connection_id,
                TableConfig.table_name == table_name
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update_table(self, table_id: int, table_update: TableConfigUpdate) -> TableConfig:
        """Update a table configuration."""
        db_table = self.get_table(table_id)
        
        # Update fields that are provided
        update_data = table_update.dict(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(db_table, key, value)
        
        self.db.commit()
        self.db.refresh(db_table)
        
        return db_table

    def delete_table(self, table_id: int) -> None:
        """Delete a table configuration."""
        db_table = self.get_table(table_id)
        
        self.db.delete(db_table)
        self.db.commit()

    def start_operations(self, operation_request: TableOperationRequest) -> None:
        """Start automated operations on tables."""
        connection_id = operation_request.connection_id
        
        for table_name in operation_request.table_names:
            # Check if the table is already configured
            existing_table = self.get_table_by_name_and_connection(connection_id, table_name)
            
            if existing_table:
                # Update the existing table configuration
                self.update_table(
                    existing_table.id,
                    TableConfigUpdate(
                        operation_type=operation_request.operation_type,
                        operation_delay=operation_request.operation_delay,
                        batch_size=operation_request.batch_size,
                        enabled=True
                    )
                )
            else:
                # Get the table schema to create a new configuration
                from services.database_service import DatabaseService
                db_service = DatabaseService(self.db)
                schema = db_service.get_table_schema(connection_id, table_name)
                
                # Create a new table configuration
                self.create_table(
                    TableConfigCreate(
                        connection_id=connection_id,
                        table_name=table_name,
                        operation_type=operation_request.operation_type,
                        operation_delay=operation_request.operation_delay,
                        batch_size=operation_request.batch_size,
                        enabled=True
                    ),
                    column_definitions=schema.columns,
                    primary_keys=schema.primary_keys
                )
        
        # Start the whisperer for the connection
        self.whisperer_service.start_whisperer(connection_id)
