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
from typing import List, Dict, Any, Optional

from models import DatabaseConnection
from schemas import TableSchemaResponse
from utils.db_connector import DatabaseConnector, DatabaseType
from services.database_service_base import DatabaseServiceBase

logger = logging.getLogger(__name__)

class MSSQLDatabaseService(DatabaseServiceBase):
    """MS SQL Server specific database service implementation"""
    
    def __init__(self, db):
        """Initialize the MS SQL Server database service."""
        super().__init__(db)
        self._connection_pool = {}  # Dictionary to store active connections by connection_id
    
    def get_schemas(self, connection_id: int) -> List[str]:
        """Get all schemas for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Check if we have a valid connection in the pool
        if connection_id in self._connection_pool and self._connection_pool[connection_id].is_connected():
            logger.info(f"Using existing connection from pool for connection_id {connection_id}")
            engine = self._connection_pool[connection_id]
        else:
            # Create a new database connector
            connector_db_type = db_connection.db_type
            if isinstance(connector_db_type, str):
                try:
                    connector_db_type = DatabaseType[connector_db_type.upper()]
                except (KeyError, AttributeError):
                    logger.warning(f"Unknown database type string: {connector_db_type}")
            
            # Map database_name to database if needed
            database = getattr(db_connection, 'database', None)
            if not database and hasattr(db_connection, 'database_name'):
                database = db_connection.database_name
            
            db_connector = DatabaseConnector(
                db_type=connector_db_type,
                host=db_connection.host,
                port=db_connection.port,
                database=database,
                username=db_connection.username,
                password=db_connection.password
            )
            
            # Connect to the database
            try:
                db_connector.connect()
                self._connection_pool[connection_id] = db_connector
                engine = db_connector
            except Exception as e:
                logger.error(f"Error connecting to database: {str(e)}")
                return []
        
        try:
            # Get JDBC metadata
            if hasattr(engine, 'jconn') and engine.jconn:
                metadata = engine.jconn.getMetaData()
                rs = metadata.getSchemas()
                
                schemas = []
                while rs.next():
                    schema_name = rs.getString("TABLE_SCHEM")
                    schemas.append(schema_name)
                
                rs.close()
                return schemas
            else:
                logger.error("No JDBC connection available")
                return []
        except Exception as e:
            logger.error(f"Error getting schemas: {str(e)}")
            return []
    
    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        """Get all tables for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Check if we have a valid connection in the pool
        if connection_id in self._connection_pool and self._connection_pool[connection_id].is_connected():
            logger.info(f"Using existing connection from pool for connection_id {connection_id}")
            engine = self._connection_pool[connection_id]
        else:
            # Create a new database connector
            connector_db_type = db_connection.db_type
            if isinstance(connector_db_type, str):
                try:
                    connector_db_type = DatabaseType[connector_db_type.upper()]
                except (KeyError, AttributeError):
                    logger.warning(f"Unknown database type string: {connector_db_type}")
            
            # Map database_name to database if needed
            database = getattr(db_connection, 'database', None)
            if not database and hasattr(db_connection, 'database_name'):
                database = db_connection.database_name
            
            db_connector = DatabaseConnector(
                db_type=connector_db_type,
                host=db_connection.host,
                port=db_connection.port,
                database=database,
                username=db_connection.username,
                password=db_connection.password
            )
            
            # Connect to the database
            try:
                db_connector.connect()
                self._connection_pool[connection_id] = db_connector
                engine = db_connector
            except Exception as e:
                logger.error(f"Error connecting to database: {str(e)}")
                return []
        
        try:
            # Get JDBC metadata
            if hasattr(engine, 'jconn') and engine.jconn:
                metadata = engine.jconn.getMetaData()
                
                # Default schema to 'dbo' if not provided
                schema_to_use = schema or 'dbo'
                
                rs = metadata.getTables(None, schema_to_use, "%", ["TABLE"])
                
                tables = []
                while rs.next():
                    table_name = rs.getString("TABLE_NAME")
                    tables.append(table_name)
                
                rs.close()
                return tables
            else:
                logger.error("No JDBC connection available")
                return []
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            return []
    
    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        try:
            logger.info(f"DATABASE_SERVICE: get_table_schema called for table {table_name} in connection {connection_id} with schema {schema_name}")
            db_connection = self.get_connection(connection_id)
            
            # Default schema to 'dbo' if not provided
            schema = schema_name or 'dbo'
            logger.info(f"Using direct JDBC metadata approach for {schema}.{table_name}")
            
            # Check if we already have a connection for this connection_id in our pool
            connection_id = db_connection.id
            if connection_id in self._connection_pool and self._connection_pool[connection_id].is_connected():
                logger.info(f"Using existing connection from pool for connection_id {connection_id}")
                engine = self._connection_pool[connection_id]
            else:
                # Create a new database connector
                connector_db_type = db_connection.db_type
                if isinstance(connector_db_type, str):
                    try:
                        connector_db_type = DatabaseType[connector_db_type.upper()]
                    except (KeyError, AttributeError):
                        logger.warning(f"Unknown database type string: {connector_db_type}")
                
                # Map database field from database_name to database if needed
                database = getattr(db_connection, 'database', None)
                if not database and hasattr(db_connection, 'database_name'):
                    database = db_connection.database_name
                    logger.info(f"Using database_name field: {database}")
                
                db_connector = DatabaseConnector(
                    db_type=connector_db_type,
                    host=db_connection.host,
                    port=db_connection.port,
                    database=database,
                    username=db_connection.username,
                    password=db_connection.password
                )
                logger.info(f"Created DatabaseConnector for {connector_db_type} connection to {db_connection.host}:{db_connection.port}/{database}")
                
                # Connect to the database
                try:
                    # Create a new connection and store it in the pool
                    db_connector.connect()
                    self._connection_pool[connection_id] = db_connector
                    engine = db_connector
                    logger.info(f"Connected to MS SQL Server database for direct schema retrieval")
                except Exception as e:
                    logger.error(f"Error connecting to MS SQL Server database: {str(e)}")
                    return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
            
            # Ensure we have a valid JDBC connection
            if not hasattr(engine, 'jconn') or not engine.jconn:
                # Try to get the JDBC connection from the engine wrapper
                if hasattr(engine, 'engine') and hasattr(engine.engine, 'jconn'):
                    engine.jconn = engine.engine.jconn
                    logger.info("Retrieved JDBC connection from engine wrapper")
                else:
                    logger.error("No JDBC connection available")
                    return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
            
            # Get JDBC metadata
            metadata = engine.jconn.getMetaData()
            conn = engine  # Use the engine as the connection
            
            # Try different case variations for the table name
            columns = {}
            primary_keys = []
            
            # First, get all tables to check if our table exists
            all_tables = []
            try:
                logger.info(f"Getting tables for schema '{schema}' using JDBC metadata")
                rs_tables = metadata.getTables(None, schema, "%", ["TABLE"])
                while rs_tables.next():
                    table_schema = rs_tables.getString("TABLE_SCHEM")
                    table_name_found = rs_tables.getString("TABLE_NAME")
                    all_tables.append(f"{table_schema}.{table_name_found}")
                rs_tables.close()
                logger.info(f"Found {len(all_tables)} tables in database: {', '.join(all_tables)}")
            except Exception as e:
                logger.error(f"Error listing all tables: {str(e)}")
                
            # If no tables found with the provided schema, try with different case variations
            if not all_tables:
                try:
                    logger.info(f"No tables found with schema '{schema}', trying with uppercase: '{schema.upper()}'")
                    rs_tables = metadata.getTables(None, schema.upper(), "%", ["TABLE"])
                    while rs_tables.next():
                        table_schema = rs_tables.getString("TABLE_SCHEM")
                        table_name_found = rs_tables.getString("TABLE_NAME")
                        all_tables.append(f"{table_schema}.{table_name_found}")
                    rs_tables.close()
                    logger.info(f"Found {len(all_tables)} tables with uppercase schema: {', '.join(all_tables)}")
                except Exception as e:
                    logger.error(f"Error listing tables with uppercase schema: {str(e)}")
                    
            # If still no tables, try with lowercase schema
            if not all_tables:
                try:
                    logger.info(f"No tables found with uppercase schema, trying with lowercase: '{schema.lower()}'")
                    rs_tables = metadata.getTables(None, schema.lower(), "%", ["TABLE"])
                    while rs_tables.next():
                        table_schema = rs_tables.getString("TABLE_SCHEM")
                        table_name_found = rs_tables.getString("TABLE_NAME")
                        all_tables.append(f"{table_schema}.{table_name_found}")
                    rs_tables.close()
                    logger.info(f"Found {len(all_tables)} tables with lowercase schema: {', '.join(all_tables)}")
                except Exception as e:
                    logger.error(f"Error listing tables with lowercase schema: {str(e)}")
                    
            # If still no tables, try with null schema to get all tables
            if not all_tables:
                try:
                    logger.info("No tables found with any schema variation, trying with null schema to get all tables")
                    rs_tables = metadata.getTables(None, None, "%", ["TABLE"])
                    while rs_tables.next():
                        table_schema = rs_tables.getString("TABLE_SCHEM")
                        table_name_found = rs_tables.getString("TABLE_NAME")
                        all_tables.append(f"{table_schema}.{table_name_found}")
                    rs_tables.close()
                    logger.info(f"Found {len(all_tables)} tables with null schema: {', '.join(all_tables)}")
                except Exception as e:
                    logger.error(f"Error listing all tables with null schema: {str(e)}")
            
            # Try to find our table in the list
            found_table = None
            found_schema = None
            logger.info(f"Searching for table '{table_name}' in {len(all_tables)} tables")
            for table_entry in all_tables:
                parts = table_entry.split('.')
                if len(parts) == 2:
                    table_schema, table_name_found = parts
                    logger.info(f"Comparing '{table_name_found.upper()}' with '{table_name.upper()}'")
                    if table_name_found.upper() == table_name.upper():
                        found_table = table_name_found
                        found_schema = table_schema
                        logger.info(f"Found matching table: {found_schema}.{found_table}")
                        break
            
            # If we didn't find the table with the exact name, try with different case variations
            if not found_table:
                logger.info(f"Table '{table_name}' not found, trying with uppercase: '{table_name.upper()}'")
                for table_entry in all_tables:
                    parts = table_entry.split('.')
                    if len(parts) == 2:
                        table_schema, table_name_found = parts
                        if table_name_found == table_name.upper():
                            found_table = table_name_found
                            found_schema = table_schema
                            logger.info(f"Found matching table with uppercase: {found_schema}.{found_table}")
                            break
            
            # If still not found, try with lowercase
            if not found_table:
                logger.info(f"Table not found with uppercase, trying with lowercase: '{table_name.lower()}'")
                for table_entry in all_tables:
                    parts = table_entry.split('.')
                    if len(parts) == 2:
                        table_schema, table_name_found = parts
                        if table_name_found == table_name.lower():
                            found_table = table_name_found
                            found_schema = table_schema
                            logger.info(f"Found matching table with lowercase: {found_schema}.{found_table}")
                            break
            
            # If table found, use the exact case for further queries
            if found_table:
                # Get columns
                try:
                    logger.info(f"Getting columns for {found_schema}.{found_table}")
                    rs_columns = metadata.getColumns(None, found_schema, found_table, "%")
                    column_count = 0
                    
                    while rs_columns.next():
                        column_count += 1
                        column_name = rs_columns.getString("COLUMN_NAME")
                        column_type = rs_columns.getString("TYPE_NAME")
                        column_size = rs_columns.getInt("COLUMN_SIZE")
                        decimal_digits = rs_columns.getInt("DECIMAL_DIGITS")
                        nullable = rs_columns.getInt("NULLABLE") == 1
                        
                        columns[column_name] = {
                            "type": column_type,
                            "length": column_size,
                            "scale": decimal_digits,
                            "nullable": nullable,
                            "primary_key": False  # Will be updated later
                        }
                    
                    rs_columns.close()
                    logger.info(f"Retrieved {column_count} columns for {found_schema}.{found_table}")
                except Exception as e:
                    logger.error(f"Error getting columns: {str(e)}")
                
                # Get primary keys
                try:
                    logger.info(f"Getting primary keys for {found_schema}.{found_table}")
                    rs_pk = metadata.getPrimaryKeys(None, found_schema, found_table)
                    pk_count = 0
                    
                    while rs_pk.next():
                        pk_count += 1
                        pk_name = rs_pk.getString("COLUMN_NAME")
                        primary_keys.append(pk_name)
                        
                        # Mark as primary key in columns dictionary
                        if pk_name in columns:
                            columns[pk_name]["primary_key"] = True
                    
                    rs_pk.close()
                    logger.info(f"Retrieved {pk_count} primary keys for {found_schema}.{found_table}")
                except Exception as e:
                    logger.error(f"Error getting primary keys: {str(e)}")
                    
                    # If JDBC metadata approach fails, try direct SQL query
                    try:
                        logger.info("Falling back to direct SQL query for primary keys")
                        cursor = engine.cursor() if hasattr(engine, 'cursor') else None
                        if not cursor:
                            logger.error("Cannot create cursor for SQL query")
                            return TableSchemaResponse(table_name=table_name, columns=columns, primary_keys=primary_keys)
                            
                        pk_query = """
                        SELECT 
                            c.name AS column_name
                        FROM 
                            sys.indexes i
                        INNER JOIN 
                            sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                        INNER JOIN 
                            sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                        INNER JOIN 
                            sys.tables t ON i.object_id = t.object_id
                        INNER JOIN 
                            sys.schemas s ON t.schema_id = s.schema_id
                        WHERE 
                            i.is_primary_key = 1
                            AND t.name = ?
                            AND s.name = ?
                        ORDER BY 
                            ic.key_ordinal
                        """
                        cursor.execute(pk_query, [found_table, found_schema])
                        pk_rows = cursor.fetchall()
                        
                        for pk_row in pk_rows:
                            pk_name = pk_row[0]
                            
                            # Ensure we have a Python string
                            if pk_name is not None:
                                pk_name = str(pk_name)
                                primary_keys.append(pk_name)
                                
                                # Mark as primary key in columns dictionary
                                if pk_name in columns:
                                    columns[pk_name]["primary_key"] = True
                                
                                logger.info(f"Found primary key from SQL query: {pk_name}")
                        
                        cursor.close()
                    except Exception as e2:
                        logger.error(f"Error getting primary keys via SQL: {str(e2)}")
                
                # If still no columns, try direct SQL query
                if not columns:
                    try:
                        logger.info("No columns retrieved from JDBC metadata, trying direct SQL query")
                        
                        # Try different ways to get a cursor
                        cursor = None
                        if hasattr(engine, 'cursor'):
                            cursor = engine.cursor()
                        elif hasattr(engine, 'connection') and hasattr(engine.connection, 'cursor'):
                            cursor = engine.connection.cursor()
                        elif hasattr(engine, 'engine') and hasattr(engine.engine, 'cursor'):
                            cursor = engine.engine.cursor()
                            
                        if not cursor:
                            logger.error("Cannot create cursor for SQL query")
                            return TableSchemaResponse(table_name=table_name, columns=columns, primary_keys=primary_keys)
                            
                        columns_query = """
                        SELECT 
                            c.name AS column_name,
                            c.column_id AS ordinal_position,
                            t.name AS data_type,
                            c.max_length AS length,
                            c.scale AS numeric_scale,
                            c.is_nullable AS is_nullable,
                            d.definition AS default_value,
                            CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
                        FROM 
                            sys.columns c
                        INNER JOIN 
                            sys.types t ON c.user_type_id = t.user_type_id
                        INNER JOIN 
                            sys.tables tbl ON c.object_id = tbl.object_id
                        INNER JOIN 
                            sys.schemas s ON tbl.schema_id = s.schema_id
                        LEFT JOIN 
                            sys.default_constraints d ON c.default_object_id = d.object_id
                        LEFT JOIN (
                            SELECT 
                                ic.column_id,
                                ic.object_id
                            FROM 
                                sys.indexes i
                            INNER JOIN 
                                sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                            WHERE 
                                i.is_primary_key = 1
                        ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
                        WHERE 
                            tbl.name = ?
                            AND s.name = ?
                        ORDER BY 
                            c.column_id
                        """
                        cursor.execute(columns_query, [found_table, found_schema])
                        column_rows = cursor.fetchall()
                        
                        for column_row in column_rows:
                            column_name = column_row[0]
                            data_type = column_row[2]
                            length = column_row[3]
                            scale = column_row[4]
                            is_nullable = column_row[5]
                            is_primary_key = column_row[7] == 1
                            
                            # Ensure we have Python strings
                            if column_name is not None:
                                column_name = str(column_name)
                                
                            columns[column_name] = {
                                "type": str(data_type) if data_type is not None else "",
                                "length": length,
                                "scale": scale,
                                "nullable": is_nullable == 1,
                                "primary_key": is_primary_key
                            }
                            
                            if is_primary_key and column_name not in primary_keys:
                                primary_keys.append(column_name)
                        
                        cursor.close()
                        logger.info(f"Retrieved {len(columns)} columns via SQL query")
                    except Exception as e:
                        logger.error(f"Error getting columns via SQL: {str(e)}")
                
                # If still no columns, try listing all tables to help with debugging
                if not columns:
                    try:
                        logger.info("No columns retrieved, listing all tables for debugging")
                        all_tables_query = "SELECT SCHEMA_NAME(schema_id) as schema_name, name FROM sys.tables ORDER BY schema_name, name"
                        cursor = engine.cursor() if hasattr(engine, 'cursor') else None
                        if not cursor:
                            logger.error("Cannot create cursor for SQL query")
                            return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
                            
                        cursor.execute(all_tables_query)
                        all_tables_result = cursor.fetchall()
                        logger.info(f"All tables in database: {all_tables_result}")
                        cursor.close()
                    except Exception as e:
                        logger.error(f"Error listing all tables: {str(e)}")
            
            # Don't close the connection as it's managed by the engine and will be reused
            # The connection will be closed when the application shuts down or when the engine is explicitly closed
            
            # Ensure all dictionary keys are Python strings
            sanitized_columns = {}
            for key, value in columns.items():
                # Convert any Java String keys to Python strings
                python_key = str(key) if key is not None else ""
                sanitized_columns[python_key] = value
            
            # Ensure all primary keys are Python strings
            sanitized_primary_keys = [str(pk) if pk is not None else "" for pk in primary_keys]
            
            return TableSchemaResponse(table_name=table_name, columns=sanitized_columns, primary_keys=sanitized_primary_keys)
        except Exception as e:
            logger.error(f"Error in direct JDBC metadata approach: {str(e)}")
            return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
    
    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        """Build a connection string based on the database type and connection parameters."""
        if connection.db_type == DatabaseType.MSSQL:
            # Use JDBC for MS SQL Server
            connection_string = f"mssql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database}"
            connection_string += "?driver=com.microsoft.sqlserver.jdbc.SQLServerDriver&trustServerCertificate=true&encrypt=true"
            return connection_string
        else:
            raise ValueError(f"Unsupported database type: {connection.db_type}")
    
    def _get_engine(self, connection: DatabaseConnection) -> Any:
        """Get or create a database engine for a connection."""
        connection_id = connection.id
        
        # Check if we have a valid connection in the pool
        if connection_id in self._connection_pool and self._connection_pool[connection_id].is_connected():
            logger.info(f"Using existing connection from pool for connection_id {connection_id}")
            return self._connection_pool[connection_id]
        
        # Create a new DatabaseConnector instance
        connector_db_type = connection.db_type
        if isinstance(connector_db_type, str):
            try:
                connector_db_type = DatabaseType[connector_db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {connector_db_type}")
        
        # Map database_name to database if needed
        database = getattr(connection, 'database', None)
        if not database and hasattr(connection, 'database_name'):
            database = connection.database_name
        
        db_connector = DatabaseConnector(
            db_type=connector_db_type,
            host=connection.host,
            port=connection.port,
            database=database,
            username=connection.username,
            password=connection.password
        )
        
        # Create the engine and get the JDBC connection
        logger.info(f"Created DatabaseConnector for {connector_db_type} connection to {connection.host}:{connection.port}/{database}")
        
        try:
            # Connect to the database and get the JDBC connection
            db_connector.connect()
            
            # Store in connection pool
            self._connection_pool[connection_id] = db_connector
            
            # Ensure we have a valid JDBC connection
            if hasattr(db_connector, 'engine') and hasattr(db_connector.engine, 'jconn'):
                # Copy the JDBC connection to the connector for easier access
                db_connector.jconn = db_connector.engine.jconn
            
            return db_connector
        except Exception as e:
            logger.error(f"Error creating engine: {str(e)}")
            raise
