#!/usr/bin/env python3
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
from schemas import TableSchemaResponse, TableMetadata
from utils.db_connector import DatabaseConnector, DatabaseType
from services.database_service_base import DatabaseServiceBase

logger = logging.getLogger(__name__)

def _normalize_column_name(value: Any) -> str:
    """Convert JDBC/JPype column identifiers into clean Python strings."""
    if value is None:
        return ""
    text = str(value)
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        text = text[1:-1]
    return text

class AS400DatabaseService(DatabaseServiceBase):
    """AS400 specific database service implementation"""
    
    def get_schemas(self, connection_id: int) -> List[str]:
        """Get all schemas for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Create a database connector
        engine = self._get_engine(db_connection)
        
        try:
            # Use JDBC connector to get schemas
            if hasattr(engine, 'get_schemas'):
                return engine.get_schemas()
            
            # Fallback for direct SQL query
            cursor = engine.execute("SELECT SCHEMA_NAME FROM QSYS2.SCHEMATA")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting schemas: {str(e)}")
            raise
    
    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        """Get all tables for a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Create a database connector
        engine = self._get_engine(db_connection)
        
        try:
            # For AS400, schema is required
            if not schema:
                # Get all schemas and return an error
                schemas = self.get_schemas(connection_id)
                schema_list = "\n - ".join(schemas)
                error_msg = f"Schema parameter is required for AS400. Available schemas:\n - {schema_list}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Use JDBC connector to get tables for the specified schema
            if hasattr(engine, 'get_tables'):
                tables_result = engine.get_tables(schema)
                # Convert string list to object format for consistency
                return [{"name": table, "schema_name": schema} for table in tables_result]
            
            # Fallback for direct SQL query
            cursor = engine.execute(
                "SELECT TABLE_NAME FROM QSYS2.SYSTABLES WHERE TABLE_SCHEMA = ?", 
                (schema,)
            )
            table_names = [row[0] for row in cursor.fetchall()]
            return [{"name": table, "schema_name": schema} for table in table_names]
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            raise

    def get_schema_objects(self, connection_id: int, schema: str = None):
        """Return metadata objects (tables/views) for a schema."""
        if not schema:
            schemas = self.get_schemas(connection_id)
            schema_list = "\n - ".join(schemas)
            error_msg = (
                f"Schema parameter is required for AS400 metadata browsing. "
                f"Available schemas:\n - {schema_list}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        table_entries = self.get_tables(connection_id, schema)
        objects = [
            {
                "name": entry["name"] if isinstance(entry, dict) else entry,
                "schema": entry.get("schema_name", schema) if isinstance(entry, dict) else schema,
                "type": "table",
                "has_children": True,
            }
            for entry in table_entries
        ]
        # NOTE: Additional object types (views, procedures) can be appended here when available.
        return objects
    
    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        logger.info(f"DATABASE_SERVICE: get_table_schema called for table {table_name} in connection {connection_id} with schema {schema_name}")
        db_connection = self.get_connection(connection_id)
        
        # For AS400, schema is required
        if not schema_name:
            schemas = self.get_schemas(connection_id)
            schema_list = "\n - ".join(schemas)
            error_msg = f"Schema parameter is required for AS400. Available schemas:\n - {schema_list}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Create a database connector
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
            connected = db_connector.connect()
            if not connected:
                raise RuntimeError("Failed to establish AS400 JDBC connection")
            
            jdbc_conn = getattr(db_connector, "connection", None)
            if not jdbc_conn:
                raise RuntimeError("DatabaseConnector did not expose an active connection")
            
            logger.info("Connected to AS400 database for schema retrieval")
            
            # Get JDBC metadata
            metadata_source = (
                getattr(jdbc_conn, "jconn", None)
                or getattr(db_connector, "jconn", None)
            )
            if metadata_source is None:
                raise RuntimeError("Active AS400 connection missing JDBC metadata handle (jconn)")
            metadata = metadata_source.getMetaData()
            
            columns = {}
            primary_keys = []
            
            # Get columns
            try:
                logger.info(f"Getting columns for {schema_name}.{table_name}")
                rs_columns = metadata.getColumns(None, schema_name, table_name, "%")
                column_count = 0
                
                while rs_columns.next():
                    column_count += 1
                    column_name = _normalize_column_name(
                        rs_columns.getString("COLUMN_NAME")
                    )
                    column_type = rs_columns.getString("TYPE_NAME")
                    nullable = rs_columns.getString("IS_NULLABLE").upper() == "YES"
                    
                    try:
                        column_size = rs_columns.getInt("COLUMN_SIZE")
                    except:
                        column_size = 0
                        
                    try:
                        decimal_digits = rs_columns.getInt("DECIMAL_DIGITS")
                    except:
                        decimal_digits = 0
                    
                    # Add to columns dictionary
                    columns[column_name] = {
                        "name": column_name,
                        "type": column_type,
                        "nullable": nullable,
                        "default": None,  # Will be updated if available
                        "primary_key": False  # Will be updated later
                    }
                    
                    # Try to get default value
                    try:
                        columns[column_name]["default"] = rs_columns.getString("COLUMN_DEF")
                    except:
                        pass
                    
                    logger.info(f"Found column: {column_name} ({column_type})")
                
                rs_columns.close()
                logger.info(f"Retrieved {column_count} columns for {schema_name}.{table_name}")
            except Exception as e:
                logger.error(f"Error getting columns: {str(e)}")
            
            # Get primary keys
            try:
                logger.info(f"Getting primary keys for {schema_name}.{table_name}")
                rs_pk = metadata.getPrimaryKeys(None, schema_name, table_name)
                pk_count = 0
                
                while rs_pk.next():
                    pk_count += 1
                    pk_name = _normalize_column_name(rs_pk.getString("COLUMN_NAME"))
                    primary_keys.append(pk_name)
                    
                    # Mark as primary key in columns dictionary
                    if pk_name in columns:
                        columns[pk_name]["primary_key"] = True
                    
                    logger.info(f"Found primary key: {pk_name}")
                
                rs_pk.close()
                logger.info(f"Retrieved {pk_count} primary keys for {schema_name}.{table_name}")
            except Exception as e:
                logger.error(f"Error getting primary keys: {str(e)}")
                
                # If JDBC metadata approach fails, try direct SQL query
                try:
                    logger.info("Falling back to direct SQL query for primary keys")
                    cursor = jdbc_conn.cursor()
                    pk_query = """
                    SELECT COLUMN_NAME
                    FROM QSYS2.SYSCST
                    WHERE CONSTRAINT_TYPE = 'PRIMARY KEY'
                    AND TABLE_SCHEMA = ?
                    AND TABLE_NAME = ?
                    """
                    cursor.execute(pk_query, [schema_name, table_name])
                    pk_rows = cursor.fetchall()
                    
                    for pk_row in pk_rows:
                        pk_name = _normalize_column_name(pk_row[0])
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
                    cursor = jdbc_conn.cursor()
                    columns_query = """
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        COLUMN_DEFAULT,
                        CASE WHEN CONSTRAINT_TYPE = 'PRIMARY KEY' THEN 1 ELSE 0 END AS IS_PRIMARY_KEY
                    FROM QSYS2.SYSCOLUMNS C
                    LEFT JOIN QSYS2.SYSCST K ON 
                        C.TABLE_SCHEMA = K.TABLE_SCHEMA AND
                        C.TABLE_NAME = K.TABLE_NAME AND
                        C.COLUMN_NAME = K.COLUMN_NAME AND
                        K.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    WHERE C.TABLE_SCHEMA = ?
                    AND C.TABLE_NAME = ?
                    ORDER BY C.ORDINAL_POSITION
                    """
                    cursor.execute(columns_query, [schema_name, table_name])
                    column_rows = cursor.fetchall()
                    
                    for column_row in column_rows:
                        column_name = _normalize_column_name(column_row[0])
                        data_type = column_row[1]
                        is_nullable = column_row[2] == 'Y'
                        default_value = column_row[3]
                        is_primary_key = column_row[4] == 1
                        
                        columns[column_name] = {
                            "name": column_name,
                            "type": data_type,
                            "nullable": is_nullable,
                            "default": default_value,
                            "primary_key": is_primary_key
                        }
                        
                        if is_primary_key and column_name not in primary_keys:
                            primary_keys.append(column_name)
                        
                        logger.info(f"Found column from SQL query: {column_name} ({data_type})")
                    
                    cursor.close()
                except Exception as e:
                    logger.error(f"Error getting columns via SQL: {str(e)}")
            
            normalized_columns: Dict[str, Any] = {}
            for key, definition in columns.items():
                column_key = _normalize_column_name(key)
                definition_dict = dict(definition or {})
                definition_dict["name"] = _normalize_column_name(
                    definition_dict.get("name", column_key)
                )
                normalized_columns[column_key] = definition_dict

            normalized_primary_keys = [str(pk) for pk in primary_keys if pk is not None]

            return TableSchemaResponse(
                table_name=table_name,
                columns=normalized_columns,
                primary_keys=normalized_primary_keys,
            )
        except Exception as e:
            logger.error(f"Error in JDBC metadata approach: {str(e)}")
            return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
        finally:
            try:
                db_connector.disconnect()
            except Exception as disconnect_err:
                logger.warning(f"Error disconnecting AS400 metadata connector: {disconnect_err}")
    
    def get_table_metadata(self, connection_id: int, table_name: str, schema_name: str = None) -> TableMetadata:
        """Return AS400 table metadata using the service-level schema retrieval."""
        schema_resp = self.get_table_schema(connection_id, table_name, schema_name)
        return TableMetadata(
            table_name=schema_resp.table_name,
            schema_name=schema_name or "",
            columns=schema_resp.columns,
            primary_keys=schema_resp.primary_keys,
            foreign_keys=getattr(schema_resp, "foreign_keys", []),
            indexes=getattr(schema_resp, "indexes", []),
        )
    
    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        """Build a connection string based on the database type and connection parameters."""
        if connection.db_type == DatabaseType.AS400:
            # Use JDBC for AS400
            connection_string = f"as400+jdbc://{connection.username}:{connection.password}@{connection.host}"
            if connection.port:
                connection_string += f":{connection.port}"
            connection_string += f"/{connection.database}?driver=com.ibm.as400.access.AS400JDBCDriver"
            return connection_string
        else:
            raise ValueError(f"Unsupported database type: {connection.db_type}")
    
    def _get_engine(self, connection: DatabaseConnection) -> Any:
        """Get or create a database engine for a connection."""
        connection_id = connection.id
        
        # Return cached engine if it exists
        if connection_id in self.engines:
            return self.engines[connection_id]
        
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
            engine = db_connector
            
            # Cache the engine
            self.engines[connection_id] = engine
            
            return engine
        except Exception as e:
            logger.error(f"Error creating engine for connection {connection_id}: {str(e)}")
            raise
