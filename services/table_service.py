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

from models import TableConfig, OperationType
from schemas import TableConfigCreate, TableConfigUpdate, TableOperationRequest
from services.whisperer_service import WhispererService

# Configure logging
logger = logging.getLogger(__name__)


class TableService:
    def __init__(self, db):
        self.db = db
        self.whisperer_service = WhispererService(db)

    def create_table(
        self, 
        table: TableConfigCreate, 
        column_definitions: Dict[str, Any], 
        primary_keys: List[str]
    ) -> TableConfig:
        """Create a new table configuration for automation."""
        # Create a new table configuration using direct SQL
        # Convert column_definitions and primary_keys to JSON strings for storage
        import json
        column_defs_json = json.dumps(column_definitions)
        primary_keys_json = json.dumps(primary_keys)
        
        logger.info(f"Creating table configuration for {table.schema_name}.{table.table_name}")
        logger.info(f"Connection ID: {table.connection_id}")
        logger.info(f"Column definitions: {column_defs_json[:100]}...")
        logger.info(f"Primary keys: {primary_keys_json}")
        
        # Build the SQL INSERT statement
        query = """
        INSERT INTO table_configs 
        (connection_id, table_name, schema_name, operation_type, operation_delay, 
         batch_size, enabled, column_definitions, primary_keys, created_at, updated_at) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        
        # Execute the query with parameters
        try:
            cursor = self.db.cursor()
            params = [
                table.connection_id,
                table.table_name,
                table.schema_name,
                table.operation_type.value if hasattr(table.operation_type, 'value') else table.operation_type,
                table.operation_delay,
                table.batch_size,
                1 if table.enabled else 0,  # SQLite uses 1/0 for boolean
                column_defs_json,
                primary_keys_json
            ]
            logger.info(f"Executing query with parameters: {params}")
            cursor.execute(query, params)
            
            # Get the ID of the inserted row
            table_id = cursor.lastrowid
            logger.info(f"Inserted table configuration with ID: {table_id}")
            cursor.commit()  # Use the cursor's commit method
            logger.info("Committed transaction")
            
            # Verify the table was created
            verify_query = "SELECT id FROM table_configs WHERE id = ?"
            cursor.execute(verify_query, [table_id])
            result = cursor.fetchone()
            if result:
                logger.info(f"Verified table configuration with ID: {table_id} exists in database")
            else:
                logger.error(f"Failed to verify table configuration with ID: {table_id}")
        except Exception as e:
            logger.error(f"Error creating table configuration: {str(e)}")
            raise
        
        # Create a TableConfig object to return
        db_table = TableConfig(
            id=table_id,
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
        
        return db_table

    def get_tables(self, skip: int = 0, limit: int = 100) -> List[TableConfig]:
        """Get all table configurations."""
        query = f"SELECT * FROM table_configs LIMIT ? OFFSET ?"
        cursor = self.db.cursor()
        cursor.execute(query, [limit, skip])
        
        tables = []
        for row in cursor.fetchall():
            # Convert row to dict
            table_dict = {}
            for i, col in enumerate(cursor.description):
                col_name = col[0]
                table_dict[col_name] = row[i]
            
            # Parse JSON fields
            import json
            if 'column_definitions' in table_dict and table_dict['column_definitions']:
                table_dict['column_definitions'] = json.loads(table_dict['column_definitions'])
            if 'primary_keys' in table_dict and table_dict['primary_keys']:
                table_dict['primary_keys'] = json.loads(table_dict['primary_keys'])
            
            # Convert operation_type to enum if needed
            if 'operation_type' in table_dict:
                try:
                    table_dict['operation_type'] = OperationType(table_dict['operation_type'])
                except (ValueError, TypeError):
                    pass  # Keep as string if not a valid enum value
            
            tables.append(TableConfig(**table_dict))
        
        return tables

    def get_tables_by_connection(self, connection_id: int, skip: int = 0, limit: int = 100) -> List[TableConfig]:
        """Get all table configurations for a connection."""
        query = "SELECT * FROM table_configs WHERE connection_id = ? LIMIT ? OFFSET ?"
        cursor = self.db.cursor()
        cursor.execute(query, [connection_id, limit, skip])
        
        tables = []
        for row in cursor.fetchall():
            # Convert row to dict
            table_dict = {}
            for i, col in enumerate(cursor.description):
                col_name = col[0]
                table_dict[col_name] = row[i]
            
            # Parse JSON fields
            import json
            if 'column_definitions' in table_dict and table_dict['column_definitions']:
                table_dict['column_definitions'] = json.loads(table_dict['column_definitions'])
            if 'primary_keys' in table_dict and table_dict['primary_keys']:
                table_dict['primary_keys'] = json.loads(table_dict['primary_keys'])
            
            # Convert operation_type to enum if needed
            if 'operation_type' in table_dict:
                try:
                    table_dict['operation_type'] = OperationType(table_dict['operation_type'])
                except (ValueError, TypeError):
                    pass  # Keep as string if not a valid enum value
            
            tables.append(TableConfig(**table_dict))
        
        return tables

    def get_table(self, table_id: int) -> Optional[TableConfig]:
        """Get a specific table configuration by ID."""
        query = "SELECT * FROM table_configs WHERE id = ?"
        cursor = self.db.cursor()
        cursor.execute(query, [table_id])
        
        row = cursor.fetchone()
        if row:
            # Convert row to dict
            table_dict = {}
            for i, col in enumerate(cursor.description):
                col_name = col[0]
                table_dict[col_name] = row[i]
            
            # Parse JSON fields
            import json
            if 'column_definitions' in table_dict and table_dict['column_definitions']:
                table_dict['column_definitions'] = json.loads(table_dict['column_definitions'])
            if 'primary_keys' in table_dict and table_dict['primary_keys']:
                table_dict['primary_keys'] = json.loads(table_dict['primary_keys'])
            
            # Convert operation_type to enum if needed
            if 'operation_type' in table_dict:
                try:
                    table_dict['operation_type'] = OperationType(table_dict['operation_type'])
                except (ValueError, TypeError):
                    pass  # Keep as string if not a valid enum value
            
            return TableConfig(**table_dict)
        return None

    def get_table_by_name_and_connection(self, connection_id: int, table_name: str) -> Optional[TableConfig]:
        """Get a specific table configuration by connection ID and table name."""
        query = "SELECT * FROM table_configs WHERE connection_id = ? AND table_name = ?"
        cursor = self.db.cursor()
        cursor.execute(query, [connection_id, table_name])
        
        row = cursor.fetchone()
        if row:
            # Convert row to dict
            table_dict = {}
            for i, col in enumerate(cursor.description):
                col_name = col[0]
                table_dict[col_name] = row[i]
            
            # Parse JSON fields
            import json
            if 'column_definitions' in table_dict and table_dict['column_definitions']:
                table_dict['column_definitions'] = json.loads(table_dict['column_definitions'])
            if 'primary_keys' in table_dict and table_dict['primary_keys']:
                table_dict['primary_keys'] = json.loads(table_dict['primary_keys'])
            
            # Convert operation_type to enum if needed
            if 'operation_type' in table_dict:
                try:
                    table_dict['operation_type'] = OperationType(table_dict['operation_type'])
                except (ValueError, TypeError):
                    pass  # Keep as string if not a valid enum value
            
            return TableConfig(**table_dict)
        return None

    def update_table(self, table_id: int, table_update: TableConfigUpdate) -> TableConfig:
        """Update a table configuration."""
        # Get the current table data
        db_table = self.get_table(table_id)
        if not db_table:
            raise ValueError(f"Table configuration with ID {table_id} not found")
        
        # Update fields that are provided
        update_data = table_update.dict(exclude_unset=True)
        
        # Build SQL update statement dynamically
        if update_data:
            set_clauses = []
            params = []
            
            for key, value in update_data.items():
                # Special handling for JSON fields
                if key in ['column_definitions', 'primary_keys'] and value is not None:
                    import json
                    value = json.dumps(value)
                
                # Special handling for enum fields
                if key == 'operation_type' and hasattr(value, 'value'):
                    value = value.value
                
                # Add to SQL parameters
                set_clauses.append(f"{key} = ?")
                params.append(value)
            
            # Add updated_at timestamp
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            
            # Add table_id to params
            params.append(table_id)
            
            # Execute update query
            query = f"UPDATE table_configs SET {', '.join(set_clauses)} WHERE id = ?"
            cursor = self.db.cursor()
            cursor.execute(query, params)
            cursor.commit()  # Use the cursor's commit method
        
        # Return the updated table
        return self.get_table(table_id)

    def delete_table(self, table_id: int) -> None:
        """Delete a table configuration."""
        # Check if the table exists
        db_table = self.get_table(table_id)
        if not db_table:
            raise ValueError(f"Table configuration with ID {table_id} not found")
        
        # Execute delete query
        query = "DELETE FROM table_configs WHERE id = ?"
        cursor = self.db.cursor()
        cursor.execute(query, [table_id])
        cursor.commit()  # Use the cursor's commit method

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
