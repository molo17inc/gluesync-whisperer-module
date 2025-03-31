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
import sqlite3
from datetime import datetime

# Import our JDBC-only DatabaseConnector
from utils.db_connector import DatabaseConnector
from typing import List, Dict, Any, Optional

from models import DatabaseConnection, ConnectionStatus, DatabaseType
from schemas import DatabaseConnectionCreate, DatabaseConnectionUpdate, ConnectionTestResponse, TableSchemaResponse

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db):
        self.db = db
        self.engines = {}  # Cache for database engines

    def create_connection(self, connection_data: DatabaseConnectionCreate) -> DatabaseConnection:
        """Create a new database connection."""
        try:
            logger.info(f"Creating connection with data: {connection_data}")
            
            # Create the connection
            connection = DatabaseConnection(
                name=connection_data.name,
                description=connection_data.description,
                db_type=connection_data.db_type,
                host=connection_data.host,
                port=connection_data.port,
                username=connection_data.username,
                password=connection_data.password,
                database=connection_data.database
            )
            
            logger.info(f"DatabaseConnection object created: {connection.name}, {connection.database}")

            # Build the connection string
            try:
                connection_string = self._build_connection_string(connection)
                connection.connection_string = connection_string
                logger.info(f"Connection string built: {connection_string}")
            except Exception as cs_error:
                logger.error(f"Error building connection string: {str(cs_error)}")
                raise ValueError(f"Failed to build connection string: {str(cs_error)}")

            # Save to database
            try:
                self.db.execute('''
                    INSERT INTO database_connections (
                        name, description, host, port, 
                        database, username, password, type, status,
                        created_at, updated_at, connection_string
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    connection.name,
                    connection.description,
                    connection.host,
                    connection.port,
                    connection.database,
                    connection.username,
                    connection.password,
                    connection.db_type.value,  # Convert enum to string value
                    ConnectionStatus.IDLE.value,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    connection.connection_string
                ))
                self.db.commit()
                logger.info("Database record inserted successfully")
            except Exception as db_error:
                logger.error(f"Database error: {str(db_error)}")
                raise ValueError(f"Database error: {str(db_error)}")

            # Get the ID of the created connection
            try:
                result = self.db.query_one('SELECT last_insert_rowid()')
                logger.info(f"Query result for last_insert_rowid: {result}")
                
                # Handle different return formats
                if isinstance(result, dict) and 'last_insert_rowid()' in result:
                    connection.id = result['last_insert_rowid()']
                elif isinstance(result, dict) and 0 in result:
                    connection.id = result[0]
                elif isinstance(result, (list, tuple)) and len(result) > 0:
                    connection.id = result[0]
                elif isinstance(result, int):
                    connection.id = result
                else:
                    # If we can't determine the ID, just use a temporary one for now
                    # We'll get the actual ID later when we query for the connection
                    logger.warning(f"Could not determine connection ID from result: {result}, using temporary ID")
                    connection.id = 1  # Temporary ID
                
                # In SQLite with AUTOINCREMENT, IDs start at 1, not 0
                # If we got ID 0, it means something went wrong, so use ID 1 instead
                if connection.id == 0:
                    logger.warning("Got ID 0 from last_insert_rowid(), using ID 1 instead")
                    connection.id = 1
                
                logger.info(f"Connection created with ID: {connection.id}")
                return connection
            except Exception as id_error:
                logger.error(f"Error retrieving connection ID: {str(id_error)}", exc_info=True)
                # Even if we can't get the ID, the connection was created in the database
                # Return the connection object without an ID
                logger.info("Returning connection without ID")
                connection.id = None
                return connection
                
        except Exception as e:
            logger.error(f"Error creating connection: {str(e)}", exc_info=True)
            raise ValueError(f"Error creating connection: {str(e)}")

    def get_connections(self, skip: int = 0, limit: int = 100) -> List[DatabaseConnection]:
        """Get all database connections."""
        # Use the Database class's query method
        connections = self.db.query(f"SELECT * FROM database_connections LIMIT {limit} OFFSET {skip}")
        result = []
        for conn in connections:
            # Map database column names to model field names
            mapped_conn = self._map_db_to_model(conn)
            result.append(DatabaseConnection(**mapped_conn))
        return result

    def get_connection(self, connection_id: int) -> Optional[DatabaseConnection]:
        """Get a specific database connection by ID."""
        logger.info(f"Attempting to get connection with ID: {connection_id}")
        
        # Use the Database class's query_one method
        try:
            conn = self.db.query_one(f"SELECT * FROM database_connections WHERE id = ?", (connection_id,))
            logger.info(f"Query result for connection ID {connection_id}: {conn}")
            
            if conn:
                # Map database column names to model field names
                mapped_conn = self._map_db_to_model(conn)
                logger.info(f"Mapped connection data: {mapped_conn}")
                return DatabaseConnection(**mapped_conn)
            else:
                # If no connection found, try to list all connections to see what's available
                all_connections = self.db.query("SELECT id, name FROM database_connections")
                logger.info(f"Available connections: {all_connections}")
                return None
        except Exception as e:
            logger.error(f"Error getting connection with ID {connection_id}: {str(e)}", exc_info=True)
            return None

    def get_connection_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """Get a specific database connection by name."""
        # Use the Database class's query_one method
        conn = self.db.query_one(f"SELECT * FROM database_connections WHERE name = ?", (name,))
        if conn:
            # Map database column names to model field names
            mapped_conn = self._map_db_to_model(conn)
            return DatabaseConnection(**mapped_conn)
        return None
        
    def _map_db_to_model(self, conn_data: dict) -> dict:
        """Map database column names to model field names."""
        # Create a copy to avoid modifying the original
        result = dict(conn_data)
        
        # Map column names
        if 'type' in result:
            result['db_type'] = result.pop('type')
        # Handle database_name if it exists (for backward compatibility)
        if 'database_name' in result:
            result['database'] = result.pop('database_name')
            
        # Add default values for fields that might be missing
        if 'connection_string' not in result:
            result['connection_string'] = None
        if 'description' not in result:
            result['description'] = None
            
        # Remove fields that aren't part of the DatabaseConnection class
        logger.debug(f"Mapped connection data: {result}")
        fields_to_remove = ['driver', 'schema']
        for field in fields_to_remove:
            if field in result:
                result.pop(field)
            
        return result

    def update_connection(self, connection_id: int, connection_update: DatabaseConnectionUpdate) -> DatabaseConnection:
        """Update a database connection."""
        db_connection = self.get_connection(connection_id)
        if not db_connection:
            raise Exception(f"Connection with ID {connection_id} not found")
        
        # Update fields that are provided
        update_data = connection_update.dict(exclude_unset=True)
        
        # Remove description field if present as it's not in the database schema
        if 'description' in update_data:
            del update_data['description']
        
        # If there are changes to connection parameters, rebuild the connection string
        rebuild_connection_string = False
        connection_params = ['db_type', 'host', 'port', 'username', 'password', 'database']
        for param in connection_params:
            if param in update_data:
                rebuild_connection_string = True
                break
                
        # Map field names to database column names
        field_to_column = {
            'db_type': 'type'
        }
        
        # Update the keys in update_data to match the database column names
        for field, column in field_to_column.items():
            if field in update_data:
                update_data[column] = update_data.pop(field)
        
        # Convert enum values to strings
        if 'type' in update_data and isinstance(update_data['type'], DatabaseType):
            update_data['type'] = update_data['type'].value
        if 'status' in update_data and isinstance(update_data['status'], ConnectionStatus):
            update_data['status'] = update_data['status'].value
        
        # Build SQL update statement dynamically
        if update_data:
            try:
                set_clauses = []
                params = []
                
                for key, value in update_data.items():
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
                
                if rebuild_connection_string:
                    # Remove from engine cache if it exists
                    if connection_id in self.engines:
                        del self.engines[connection_id]
                
                # Add updated_at timestamp
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                
                # Add connection_id to params
                params.append(connection_id)
                
                # Execute update query
                query = f"UPDATE database_connections SET {', '.join(set_clauses)} WHERE id = ?"
                cursor = self.db.cursor()
                cursor.execute(query, params)
                cursor.commit()
                
                # Return the updated connection
                return self.get_connection(connection_id)
            except Exception as e:
                logger.error(f"Error updating connection: {str(e)}")
                raise Exception(f"Error updating connection: {str(e)}")
        
        # If no updates were provided, just return the existing connection
        return db_connection

    def delete_connection(self, connection_id: int) -> None:
        """Delete a database connection."""
        db_connection = self.get_connection(connection_id)
        if not db_connection:
            raise Exception(f"Connection with ID {connection_id} not found")
        
        # Remove from engine cache if it exists
        if connection_id in self.engines:
            del self.engines[connection_id]
        
        try:
            # Execute delete query
            query = "DELETE FROM database_connections WHERE id = ?"
            cursor = self.db.cursor()
            cursor.execute(query, [connection_id])
            cursor.commit()
        except Exception as e:
            logger.error(f"Error deleting connection: {str(e)}")
            raise Exception(f"Error deleting connection: {str(e)}")

    def update_connection_status(self, connection_id: int, status: ConnectionStatus) -> DatabaseConnection:
        """Update a database connection status."""
        db_connection = self.get_connection(connection_id)
        if not db_connection:
            raise Exception(f"Connection with ID {connection_id} not found")
        
        try:
            # Execute update query
            query = "UPDATE database_connections SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            cursor = self.db.cursor()
            cursor.execute(query, [status.value, connection_id])
            cursor.commit()
            
            # Return the updated connection
            return self.get_connection(connection_id)
        except Exception as e:
            logger.error(f"Error updating connection status: {str(e)}")
            raise Exception(f"Error updating connection status: {str(e)}")

    def test_connection(self, connection_id: int) -> ConnectionTestResponse:
        """Test a database connection."""
        db_connection = self.get_connection(connection_id)
        
        try:
            # Try to connect to the database
            engine = self._get_engine(db_connection)
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            
            return ConnectionTestResponse(success=True, message="Connection successful")
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return ConnectionTestResponse(success=False, message=f"Connection failed: {str(e)}")

    def get_schemas(self, connection_id: int) -> List[str]:
        """Get all schemas for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Get the database engine
        engine = self._get_engine(db_connection)
        
        # Handle JDBC connections separately
        if db_connection.db_type == DatabaseType.AS400 and hasattr(engine, 'get_schemas'):
            try:
                # Direct call for JDBC wrapper
                return engine.get_schemas()
            except Exception as e:
                logger.error(f"Error getting schemas via JDBC: {str(e)}")
                # Return a default if we can't get schemas
                return [db_connection.database if db_connection.database else 'QGPL']
        
        # Standard SQLAlchemy approach for other engines
        try:
            # Use JDBC connector to get schemas
            if hasattr(engine, 'get_schemas'):
                return engine.get_schemas()
            # Fallback for non-JDBC connections
            return [db_connection.database or 'default']
        except Exception as e:
            logger.error(f"Error getting schemas: {str(e)}")
            # For databases that don't support schemas or have a different mechanism
            if db_connection.db_type == DatabaseType.MYSQL:
                # For MySQL, databases are essentially schemas
                with engine.connect() as conn:
                    result = conn.execute(sqlalchemy.text("SHOW DATABASES"))
                    return [row[0] for row in result]
            elif db_connection.db_type == DatabaseType.MSSQL:
                # For MS SQL Server, get actual schemas from sys.schemas
                try:
                    with engine.connect() as conn:
                        # Use sys.schemas to get the actual schema names
                        result = conn.execute("SELECT name FROM sys.schemas WHERE name NOT LIKE 'db\_%' AND name != 'sys' AND name != 'INFORMATION_SCHEMA'")
                        schemas = [row[0] for row in result]
                        if schemas:
                            return schemas
                        else:
                            # Fallback to default schema if no custom schemas found
                            return ['dbo']
                except Exception as e:
                    logger.error(f"Error getting MS SQL Server schemas: {str(e)}")
                    return ['dbo']  # Default SQL Server schema
            elif db_connection.db_type == DatabaseType.SQLITE:
                # SQLite doesn't have traditional schemas
                return ['main']
            else:
                # Return a default if we can't get schemas
                return [db_connection.database if db_connection.database else 'default']
                
    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        """Get all tables for a database connection.
        
        Args:
            connection_id: ID of the database connection
            schema: Schema name to filter tables (required for most databases)
            
        Returns:
            List of table names
            
        Raises:
            ValueError: If schema is not provided for databases that require it
        """
        db_connection = self.get_connection(connection_id)
        
        # Get the database engine
        engine = self._get_engine(db_connection)
        
        # Handle JDBC connections separately for both AS400 and MS SQL Server
        if (db_connection.db_type in [DatabaseType.AS400, DatabaseType.MSSQL]) and hasattr(engine, 'get_tables'):
            try:
                # Direct call for JDBC wrapper
                return engine.get_tables(schema)
            except Exception as e:
                logger.error(f"Error getting tables via JDBC: {str(e)}")
                raise
        
        # Standard SQLAlchemy approach for other engines
        try:
            # For database types that require schemas, make sure one is provided
            if schema is None:
                # SQLite doesn't use schemas in the traditional sense
                if db_connection.db_type == DatabaseType.SQLITE:
                    # Use JDBC connector to get tables without schema
                    if hasattr(engine, 'get_tables'):
                        return engine.get_tables()
                    # Fallback for non-JDBC SQLite
                    return []
                else:
                    # For all other database types, require a schema
                    schemas = self.get_schemas(connection_id)
                    schema_list = "\n - ".join(schemas)
                    error_msg = f"Schema parameter is required. Available schemas:\n - {schema_list}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
            # Use JDBC connector to get tables for the specified schema
            if hasattr(engine, 'get_tables'):
                return engine.get_tables(schema)
            # Fallback for non-JDBC connections
            return []
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            raise

    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        db_connection = self.get_connection(connection_id)
        
        # For JDBC connections (AS400 and MS SQL Server), create a DatabaseConnector directly
        if db_connection.db_type in [DatabaseType.AS400, DatabaseType.MSSQL]:
            # Create a new DatabaseConnector instance
            from utils.db_connector import DatabaseConnector
            
            # Convert string db_type to enum if needed
            connector_db_type = db_connection.db_type
            if isinstance(db_connection.db_type, str):
                try:
                    connector_db_type = DatabaseType[db_connection.db_type.upper()]
                except (KeyError, AttributeError):
                    logger.warning(f"Unknown database type string: {db_connection.db_type}")
            
            # Create the connector with the connection parameters
            db_connector = DatabaseConnector(
                db_type=connector_db_type,
                host=db_connection.host,
                port=db_connection.port,
                database=db_connection.database,
                username=db_connection.username,
                password=db_connection.password
            )
            
            # Connect to the database
            db_connector.connect()
            try:
                # For JDBC, we need to use a direct approach with SQL queries
                columns = {}
                primary_keys = []
                
                # Get a cursor from the db_connector
                cursor = db_connector.connection.cursor()
                try:
                    # Determine schema to use
                    schema = schema_name or (db_connection.database if db_connection.database else None)
                    
                    if db_connection.db_type == DatabaseType.AS400:
                        if not schema:
                            logger.warning("No schema provided for AS400 table, using default schema")
                            # Try to use the connection user's schema as default
                            schema = db_connection.username
                        
                        # Try to use the AS400SqlStatements class that works in production,
                        # but handle compatibility issues with different AS400 systems
                        from utils.sql.as400 import AS400SqlStatements
                        as400_sql = AS400SqlStatements()
                    elif db_connection.db_type == DatabaseType.MSSQL:
                        if not schema:
                            logger.warning("No schema provided for MS SQL Server table, using default 'dbo' schema")
                            schema = 'dbo'  # Default SQL Server schema
                        
                        # Use MS SQL Server-specific SQL statements
                        from utils.sql.mssql import MSSQLSqlStatements
                        mssql_sql = MSSQLSqlStatements()
                    
                    # Get columns for the table
                    logger.debug(f"Getting columns for table {schema}.{table_name}")
                    
                    # Use database-specific queries for columns
                    if db_connection.db_type == DatabaseType.AS400:
                        # AS400-specific column query
                        columns_query = f"""
                        SELECT 
                            COLUMN_NAME, 
                            ORDINAL_POSITION,
                            DATA_TYPE, 
                            LENGTH,
                            NUMERIC_SCALE,
                            COLUMN_TEXT,
                            IS_NULLABLE, 
                            COLUMN_DEFAULT
                        FROM QSYS2.SYSCOLUMNS 
                        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table_name}'
                        ORDER BY ORDINAL_POSITION
                        """
                    elif db_connection.db_type == DatabaseType.MSSQL:
                        # Use the MS SQL Server SQL statements class for compatibility with JDBC
                        from utils.sql.mssql import MSSQLSqlStatements
                        mssql_sql = MSSQLSqlStatements()
                        
                        # Get the table schema query with question mark parameters
                        columns_query = mssql_sql.get_table_schema_statement(schema)
                        
                        # Replace parameters with actual values for direct cursor execution
                        # MS SQL Server with JDBC requires parameters to be passed correctly
                        # We'll use positional parameters instead of named parameters
                    
                    try:
                        # Execute the query with appropriate parameters based on database type
                        if db_connection.db_type == DatabaseType.MSSQL:
                            # For MS SQL Server JDBC, execute with positional parameters
                            cursor.execute(columns_query, [schema, table_name])
                        else:
                            # For other databases, execute directly
                            cursor.execute(columns_query)
                        column_rows = cursor.fetchall()
                        
                        for row in column_rows:
                            # Safely extract column information based on the available columns
                            column_name = row[0]  # COLUMN_NAME
                            
                            # Handle different column positions carefully
                            ordinal_position = row[1] if len(row) > 1 else None
                            data_type = row[2] if len(row) > 2 else None
                            length = row[3] if len(row) > 3 else None
                            numeric_scale = row[4] if len(row) > 4 else None
                            description = row[5] if len(row) > 5 else None
                            nullable = row[6] == 'YES' if len(row) > 6 else True  # Default to nullable
                            default_value = row[7] if len(row) > 7 else None
                            
                            # Don't try to access row[9] directly as it might not exist
                            is_primary_key = False  # We'll determine primary keys separately
                            
                            # Build type info string
                            type_info = data_type
                            if data_type.upper() in ('DECIMAL', 'NUMERIC') and length is not None:
                                if numeric_scale is not None:
                                    type_info = f"{data_type}({length},{numeric_scale})"
                                else:
                                    type_info = f"{data_type}({length})"
                            elif data_type.upper() in ('CHAR', 'VARCHAR') and length is not None:
                                type_info = f"{data_type}({length})"
                                
                            columns[column_name] = {
                                'name': column_name,
                                'type': type_info,
                                'nullable': nullable,
                                'default': default_value,
                                'description': description,
                                'is_primary_key': is_primary_key
                            }
                            
                            # Build primary keys list based on column information
                            if is_primary_key and column_name not in primary_keys:
                                primary_keys.append(column_name)
                                
                    except Exception as col_err:
                        logger.error(f"Error getting columns: {col_err}")
                        raise
                    
                    # For primary keys, we need to use a simplified approach that works across
                    # different AS400 database versions
                    
                    # APPROACH 1: Use database-specific primary key queries
                    if not primary_keys:
                        try:
                            if db_connection.db_type == DatabaseType.AS400:
                                logger.debug(f"Getting primary keys using SYSIBM.SQLPRIMARYKEYS for {schema}.{table_name}")
                                pk_query = f"""
                                SELECT COLUMN_NAME 
                                FROM SYSIBM.SQLPRIMARYKEYS 
                                WHERE TABLE_SCHEM = '{schema}' 
                                  AND TABLE_NAME = '{table_name}' 
                                ORDER BY KEY_SEQ
                                """
                            elif db_connection.db_type == DatabaseType.MSSQL:
                                logger.debug(f"Getting primary keys for SQL Server table {schema}.{table_name}")
                                # Use the MS SQL Server SQL statements class for consistent parameter handling
                                pk_query = mssql_sql.get_primary_keys_statement(schema, table_name)
                            
                            # Execute with appropriate parameters
                            if db_connection.db_type == DatabaseType.MSSQL:
                                # MS SQL Server JDBC needs positional parameters
                                cursor.execute(pk_query, [schema, table_name])
                            else:
                                # Other databases use direct execution
                                cursor.execute(pk_query)
                                
                            pk_rows = cursor.fetchall()
                            
                            for row in pk_rows:
                                col_name = row[0]
                                if col_name not in primary_keys:
                                    primary_keys.append(col_name)
                                    
                                    # Update the is_primary_key flag for this column
                                    if col_name in columns:
                                        columns[col_name]['is_primary_key'] = True
                        except Exception as pk_err:
                            logger.debug(f"SQLPRIMARYKEYS approach failed: {pk_err}")
                    
                    # APPROACH 2: Try to find primary key info based on indexes (database-specific)
                    if not primary_keys:
                        try:
                            if db_connection.db_type == DatabaseType.AS400:
                                logger.debug(f"Checking AS400 indexes for primary key on {schema}.{table_name}")
                                idx_query = f"""
                                SELECT COLUMN_NAME 
                                FROM QSYS2.SYSINDEXES I
                                JOIN QSYS2.SYSKEYS K ON I.INDEX_NAME = K.INDEX_NAME AND I.TABLE_SCHEMA = K.TABLE_SCHEMA AND I.TABLE_NAME = K.TABLE_NAME
                                WHERE I.TABLE_SCHEMA = '{schema}'
                                  AND I.TABLE_NAME = '{table_name}'
                                  AND I.IS_UNIQUE = 'YES'
                                ORDER BY K.ORDINAL_POSITION
                                """
                            elif db_connection.db_type == DatabaseType.MSSQL:
                                logger.debug(f"Checking SQL Server indexes for primary key on {schema}.{table_name}")
                                idx_query = f"""
                                SELECT COL_NAME(ic.object_id, ic.column_id) AS COLUMN_NAME
                                FROM sys.indexes i 
                                JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                                JOIN sys.tables t ON i.object_id = t.object_id
                                JOIN sys.schemas s ON t.schema_id = s.schema_id
                                WHERE s.name = '{schema}'
                                  AND t.name = '{table_name}'
                                  AND i.is_unique = 1
                                ORDER BY ic.key_ordinal
                                """
                            
                            cursor.execute(idx_query)
                            pk_rows = cursor.fetchall()
                            
                            for row in pk_rows:
                                col_name = row[0]
                                if col_name not in primary_keys:
                                    primary_keys.append(col_name)
                                    
                                    # Update the is_primary_key flag for this column
                                    if col_name in columns:
                                        columns[col_name]['is_primary_key'] = True
                        except Exception as idx_err:
                            logger.debug(f"Index-based primary key detection failed: {idx_err}")
                    
                    # If we still couldn't find primary keys, try a few fallback approaches
                    if not primary_keys:
                        fallback_queries = []
                        
                        if db_connection.db_type == DatabaseType.AS400:
                            # Try fallback queries that might work on older AS400 systems
                            fallback_queries = [
                                # Using SQLPRIMARYKEYS (ODBC/JDBC standard catalog function)
                                f"""
                                SELECT COLUMN_NAME 
                                FROM SYSIBM.SQLPRIMARYKEYS 
                                WHERE TABLE_SCHEM = '{schema}' 
                                  AND TABLE_NAME = '{table_name}' 
                                ORDER BY KEY_SEQ
                                """,
                                # Simple NON-NULL unique index check
                                f"""
                                SELECT COLUMN_NAME 
                                FROM QSYS2.SYSCOLUMNS 
                                WHERE TABLE_SCHEMA = '{schema}' 
                                  AND TABLE_NAME = '{table_name}' 
                                  AND IS_NULLABLE = 'N'
                                ORDER BY ORDINAL_POSITION
                                FETCH FIRST 1 ROWS ONLY
                                """
                            ]
                        elif db_connection.db_type == DatabaseType.MSSQL:
                            # SQL Server fallback queries
                            fallback_queries = [
                                # Try INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                                f"""
                                SELECT kcu.COLUMN_NAME
                                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                                JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc 
                                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                                AND kcu.TABLE_SCHEMA = tc.TABLE_SCHEMA
                                AND kcu.TABLE_NAME = tc.TABLE_NAME
                                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                                AND kcu.TABLE_SCHEMA = '{schema}'
                                AND kcu.TABLE_NAME = '{table_name}'
                                """,
                                # Try non-nullable columns as a last resort
                                f"""
                                SELECT COLUMN_NAME
                                FROM INFORMATION_SCHEMA.COLUMNS
                                WHERE TABLE_SCHEMA = '{schema}'
                                AND TABLE_NAME = '{table_name}'
                                AND IS_NULLABLE = 'NO'
                                ORDER BY ORDINAL_POSITION
                                """
                            ]
                        
                        for query in fallback_queries:
                            try:
                                cursor.execute(query)
                                pk_rows = cursor.fetchall()
                                if pk_rows:
                                    for row in pk_rows:
                                        col_name = row[0]
                                        if col_name not in primary_keys:
                                            primary_keys.append(col_name)
                                            # Update the is_primary_key flag
                                            if col_name in columns:
                                                columns[col_name]['is_primary_key'] = True
                                    if primary_keys:
                                        break
                            except Exception:
                                # Ignore errors on fallback queries
                                pass
                finally:
                    cursor.close()
                
                return TableSchemaResponse(
                    table_name=table_name,
                    columns=columns,
                    primary_keys=primary_keys
                )
            except Exception as e:
                logger.error(f"Error getting table schema via JDBC: {str(e)}")
                raise
        
        # We've already handled JDBC connections (AS400 and MSSQL) above, so we don't need to try the JDBC-only approach here
        # Get column information using SQLAlchemy
        try:
            # Import DatabaseConnector here to avoid circular imports
            from utils.db_connector import DatabaseConnector
            
            # Get the engine for this connection
            engine = self._get_engine(db_connection)
            
            columns = {}
            primary_keys = []
            
            # Get the engine type by checking its class name
            engine_type = engine.__class__.__name__
            
            # Handle different types of engines
            if engine_type == 'DatabaseConnector':
                # For DatabaseConnector objects, use the connection directly
                conn = engine.connection
                if hasattr(conn, 'getMetaData'):
                    # Get JDBC metadata directly from the connection
                    metadata = conn.getMetaData()
                    
                    # Get primary keys
                    rs_pk = metadata.getPrimaryKeys(None, schema_name, table_name)
                    while rs_pk.next():
                        pk_col = str(rs_pk.getString("COLUMN_NAME"))
                        primary_keys.append(str(pk_col))  # Ensure it's a Python string
                    rs_pk.close()
                    
                    # Get column information
                    rs_cols = metadata.getColumns(None, schema_name, table_name, None)
                    while rs_cols.next():
                        col_name = str(rs_cols.getString("COLUMN_NAME"))
                        col_type = str(rs_cols.getString("TYPE_NAME"))
                        nullable = rs_cols.getInt("NULLABLE") == 1
                        
                        # Ensure all keys and values are Python strings
                        columns[str(col_name)] = {
                            'type': str(col_type),
                            'nullable': bool(nullable),
                            'default': None,  # JDBC doesn't easily provide default values
                            'is_primary_key': col_name in primary_keys
                        }
                    rs_cols.close()
            elif hasattr(engine, 'connect'):
                # For SQLAlchemy engines, use the connect method
                conn = engine.connect()
                try:
                    if hasattr(conn, 'jconn'):
                        # Get JDBC metadata
                        metadata = conn.jconn.getMetaData()
                        
                        # Get primary keys
                        rs_pk = metadata.getPrimaryKeys(None, schema_name, table_name)
                        while rs_pk.next():
                            pk_col = str(rs_pk.getString("COLUMN_NAME"))
                            primary_keys.append(str(pk_col))  # Ensure it's a Python string
                        rs_pk.close()
                        
                        # Get column information
                        rs_cols = metadata.getColumns(None, schema_name, table_name, None)
                        while rs_cols.next():
                            col_name = str(rs_cols.getString("COLUMN_NAME"))
                            col_type = str(rs_cols.getString("TYPE_NAME"))
                            nullable = rs_cols.getInt("NULLABLE") == 1
                            
                            # Ensure all keys and values are Python strings
                            columns[str(col_name)] = {
                                'type': str(col_type),
                                'nullable': bool(nullable),
                                'default': None,  # JDBC doesn't easily provide default values
                                'is_primary_key': col_name in primary_keys
                            }
                        rs_cols.close()
                finally:
                    # Only close the connection if it has a close method
                    if hasattr(conn, 'close'):
                        conn.close()
            
            return TableSchemaResponse(
                table_name=table_name,
                columns=columns,
                primary_keys=primary_keys
            )
        except Exception as e:
            logger.error(f"Error getting table schema via JDBC: {str(e)}")
            raise

    def _build_connection_string(self, connection) -> str:
        """
        Build a connection string based on the database type and connection parameters.
        Always using JDBC drivers for all database types (except SQLite).
        """
        try:
            # Check if JDBC utils are available
            from utils import jdbc_utils
            
            if connection.db_type == DatabaseType.MYSQL:
                # MySQL with JDBC
                return f"mysql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database}?driver=com.mysql.cj.jdbc.Driver"
            
            elif connection.db_type == DatabaseType.POSTGRESQL:
                # PostgreSQL with JDBC
                return f"postgresql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database}?driver=org.postgresql.Driver"
            
            elif connection.db_type == DatabaseType.SQLITE:
                # SQLite: still use sqlite:// protocol as it's not JDBC-based
                return f"sqlite:///{connection.database}"
            
            elif connection.db_type == DatabaseType.MSSQL:
                # MS SQL Server with JDBC
                return f"mssql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database}?driver=com.microsoft.sqlserver.jdbc.SQLServerDriver&trustServerCertificate=true&encrypt=true"
            
            elif connection.db_type == DatabaseType.ORACLE:
                # Oracle with JDBC
                return f"oracle+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database}?driver=oracle.jdbc.OracleDriver"
            
            elif connection.db_type == DatabaseType.AS400:
                # AS400 with JDBC
                if connection.database:
                    return f"as400+jdbc://{connection.username}:{connection.password}@{connection.host}/{connection.database}?driver=com.ibm.as400.access.AS400JDBCDriver"
                else:
                    return f"as400+jdbc://{connection.username}:{connection.password}@{connection.host}?driver=com.ibm.as400.access.AS400JDBCDriver"
                    
            else:
                raise ValueError(f"Unsupported database type: {connection.db_type}")
                
        except ImportError:
            # JDBC not available
            logger.error("JDBC utilities not available. All database connections require JDBC support.")
            raise ValueError("Database connection requires JDBC support")

    def _get_engine(self, connection: DatabaseConnection):
        """
        Get or create a database engine for a connection.
        Uses our JDBC-only DatabaseConnector for JDBC connections.
        """
        connection_id = connection.id
        
        # Return cached engine if available
        if connection_id in self.engines:
            return self.engines[connection_id]
        
        # Check if this is a JDBC connection string (for any supported database)
        # Convert string db_type to enum if needed
        db_type_enum = None
        if isinstance(connection.db_type, str):
            try:
                db_type_enum = DatabaseType[connection.db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {connection.db_type}")
        else:
            db_type_enum = connection.db_type
            
        # Always use JDBC for our supported database types, regardless of connection string
        # This ensures we use JDBC even when connection_string is None
        if db_type_enum in [DatabaseType.AS400, DatabaseType.MSSQL, DatabaseType.MYSQL, DatabaseType.POSTGRESQL, DatabaseType.ORACLE] or \
           (connection.connection_string and ('+jdbc' in connection.connection_string or connection.connection_string.startswith("jdbc:"))):
            try:
                # Extract connection parameters
                host = connection.host
                port = connection.port
                database = connection.database
                username = connection.username
                password = connection.password
                db_type = connection.db_type
                
                # Create a wrapper class that provides SQLAlchemy-compatible interfaces
                # while using our JDBC-only DatabaseConnector under the hood
                class DbConnectorWrapper:
                    def __init__(self, db_type, host, port, database, username, password):
                        self.db_type = db_type
                        self.host = host
                        self.port = port
                        self.database = database
                        self.username = username
                        self.password = password
                        self.url = connection.connection_string  # Required for SQLAlchemy inspector compatibility
                        
                        # Create the DatabaseConnector instance
                        # Convert string db_type to enum if needed
                        connector_db_type = db_type
                        if isinstance(db_type, str):
                            try:
                                connector_db_type = DatabaseType[db_type.upper()]
                            except (KeyError, AttributeError):
                                logger.warning(f"Unknown database type string: {db_type}")
                                
                        self.db_connector = DatabaseConnector(
                            db_type=connector_db_type,
                            host=host,
                            port=port,
                            database=database,
                            username=username,
                            password=password
                        )
                        self.connection = None
                    
                    def connect(self):
                        # Connect using DatabaseConnector
                        self.db_connector.connect()
                        self.connection = self.db_connector
                        return self.connection
                    
                    def execute(self, query, params=None):
                        # Make sure we have a connection
                        if not self.connection:
                            self.connect()
                        # Execute through DatabaseConnector
                        return self.db_connector.execute_query(query, params)
                    
                    def get_schemas(self):
                        """Get all schemas in the database."""
                        # Make sure we have a connection
                        if not self.connection:
                            self.connect()
                        # Get schemas through DatabaseConnector
                        return self.db_connector.get_schemas()
                    
                    def get_tables(self, schema=None):
                        """Get all tables in the specified schema."""
                        # Make sure we have a connection
                        if not self.connection:
                            self.connect()
                        # Get tables through DatabaseConnector
                        return self.db_connector.get_tables(schema)
                    
                    def dispose(self):
                        # Clean up resources
                        if self.connection:
                            try:
                                self.db_connector.disconnect()
                            except:
                                pass
                            self.connection = None
                    
                    # Support methods for SQLAlchemy inspection compatibility
                    def dialect(self):
                        # Simulate the dialect property for SQLAlchemy inspector
                        class Dialect:
                            def __init__(self, connector):
                                self.connector = connector
                            
                            def get_schema_names(self, conn):
                                if not conn.connection:
                                    conn.connect()
                                return conn.db_connector.get_schemas()
                            
                            def get_table_names(self, conn, schema=None):
                                if not conn.connection:
                                    conn.connect()
                                return conn.db_connector.get_tables(schema)
                            
                            def get_columns(self, conn, table_name, schema=None):
                                if not conn.connection:
                                    conn.connect()
                                table_schema = conn.db_connector.get_table_schema(table_name, schema)
                                # Convert to SQLAlchemy-compatible format
                                columns = []
                                for name, info in table_schema['columns'].items():
                                    columns.append({
                                        'name': name,
                                        'type': info['type'],
                                        'nullable': info['nullable'],
                                        'default': info['default'],
                                        'primary_key': info['primary_key']
                                    })
                                return columns
                            
                            def get_pk_constraint(self, conn, table_name, schema=None):
                                if not conn.connection:
                                    conn.connect()
                                table_schema = conn.db_connector.get_table_schema(table_name, schema)
                                return {
                                    'constrained_columns': table_schema['primary_keys'],
                                    'name': 'PRIMARY'
                                }
                            
                            def get_foreign_keys(self, conn, table_name, schema=None):
                                if not conn.connection:
                                    conn.connect()
                                table_schema = conn.db_connector.get_table_schema(table_name, schema)
                                return table_schema['foreign_keys']
                            
                            def get_indexes(self, conn, table_name, schema=None):
                                if not conn.connection:
                                    conn.connect()
                                table_schema = conn.db_connector.get_table_schema(table_name, schema)
                                return table_schema['indexes']
                        
                        return Dialect(self)
                    
                    def begin(self):
                        # Implement a minimal transaction context manager
                        class Transaction:
                            def __init__(self, conn):
                                self.conn = conn
                            
                            def __enter__(self):
                                return self
                            
                            def __exit__(self, exc_type, exc_val, exc_tb):
                                pass
                        
                        return Transaction(self)
                    
                    def __enter__(self):
                        return self.connect()
                    
                    def __exit__(self, exc_type, exc_val, exc_tb):
                        self.dispose()
                
                # Create the DatabaseConnector wrapper
                logger.info(f"Creating DatabaseConnector for {db_type} connection to {host}")
                engine = DbConnectorWrapper(
                    db_type=db_type,
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password=password
                )
                
                # Cache and return the engine
                self.engines[connection_id] = engine
                return engine
                
            except Exception as e:
                logger.error(f"Error creating DatabaseConnector: {str(e)}")
                raise ValueError(f"Error creating DatabaseConnector: {str(e)}")
        
        # For SQLite, use a simple wrapper around sqlite3
        if connection.db_type == DatabaseType.SQLITE:
            try:
                # Create a wrapper class for SQLite that mimics the JDBC interface
                class SqliteWrapper:
                    def __init__(self, db_path):
                        self.db_path = db_path.replace('sqlite:///', '')
                        self.connection = None
                        self.url = connection.connection_string  # For compatibility
                    
                    def connect(self):
                        self.connection = sqlite3.connect(self.db_path)
                        return self
                    
                    def execute(self, query, params=None):
                        if not self.connection:
                            self.connect()
                        cursor = self.connection.cursor()
                        if params:
                            cursor.execute(query, params)
                        else:
                            cursor.execute(query)
                        return cursor
                    
                    def get_schemas(self):
                        return ['main']
                    
                    def get_tables(self, schema=None):
                        cursor = self.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        return [row[0] for row in cursor.fetchall()]
                    
                    def dispose(self):
                        if self.connection:
                            self.connection.close()
                            self.connection = None
                    
                    def __enter__(self):
                        return self.connect()
                    
                    def __exit__(self, exc_type, exc_val, exc_tb):
                        self.dispose()
                
                # Extract the database path from the connection string
                db_path = connection.connection_string
                engine = SqliteWrapper(db_path)
                self.engines[connection_id] = engine
                return engine
            except Exception as e:
                logger.error(f"Error creating SQLite connection: {str(e)}")
                raise Exception(f"Failed to create SQLite connection: {str(e)}")
        else:
            # For all other database types, we require JDBC
            logger.error(f"Unsupported database type without JDBC: {connection.db_type}")
            raise Exception(f"Database type {connection.db_type} requires JDBC support which is not available")
