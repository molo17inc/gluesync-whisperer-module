#!/usr/bin/env python3

import logging
from typing import List, Dict, Any, Optional

from models import DatabaseConnection
from schemas import TableSchemaResponse
from services.database_service_base import DatabaseServiceBase
from utils.db_connector import DatabaseConnector, DatabaseType
from utils.sql.factory import get_sql_statements

logger = logging.getLogger(__name__)


class PostgreSQLDatabaseService(DatabaseServiceBase):
    """PostgreSQL database service implementation."""

    def __init__(self, db):
        super().__init__(db)
        self.sql_statements = get_sql_statements(DatabaseType.POSTGRESQL)

    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        return f"jdbc:postgresql://{connection.host}:{connection.port}/{connection.database}"

    def _get_engine(self, connection: DatabaseConnection) -> Any:
        connection_id = connection.id
        if connection_id in self.engines:
            return self.engines[connection_id]

        logger.info(f"Creating PostgreSQL connector for connection: {connection.name}")
        connector = DatabaseConnector(
            db_type=DatabaseType.POSTGRESQL,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        # Store the connector in the engines dict
        self.engines[connection_id] = connector
        return connector

    def get_schemas(self, connection_id: int) -> List[str]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        logger.info(f"PostgreSQL: Getting schemas for connection {connection_id} ({connection.name})")
        connector = DatabaseConnector(
            db_type=DatabaseType.POSTGRESQL,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        try:
            # Connect to the database
            success = connector.connect()
            if not success:
                raise RuntimeError(f"Failed to connect to PostgreSQL database: {connection.name}")
            
            # Get the database connection - jaydebeapi connection object itself is the connection
            conn = connector.connection
            cursor = conn.cursor()
            
            # Execute the query
            sql = self.sql_statements.get_schemas_statement()
            cursor.execute(sql)
            
            # Process the results - return a list of schema names as strings
            result = cursor.fetchall()
            schemas = [str(row[0]) for row in result if row[0] is not None and str(row[0]) not in ['pg_toast', 'pg_catalog', 'information_schema']]
            
            logger.info(f"PostgreSQL: Retrieved {len(schemas)} schemas: {schemas}")
            return schemas
            
        except Exception as e:
            logger.error(f"Error getting schemas: {str(e)}")
            raise
        finally:
            # Ensure the connection is closed
            if 'connector' in locals():
                connector.disconnect()

    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        logger.info(f"PostgreSQL: Getting tables for connection {connection_id} ({connection.name}), schema: {schema}")
        connector = DatabaseConnector(
            db_type=DatabaseType.POSTGRESQL,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        try:
            # Connect to the database
            success = connector.connect()
            if not success:
                raise RuntimeError(f"Failed to connect to PostgreSQL database: {connection.name}")
            
            # Get the database connection - jaydebeapi connection object itself is the connection
            conn = connector.connection
            cursor = conn.cursor()
            
            # Execute the query - SQL is already formatted with the schema
            sql = self.sql_statements.get_tables_statement(schema)
            cursor.execute(sql)
            
            # Process the results
            result = cursor.fetchall()
            tables = [{"name": str(row[0]), "schema_name": schema or ""} for row in result if row[0] is not None]
            
            logger.info(f"PostgreSQL: Retrieved {len(tables)} tables for schema '{schema}': {tables}")
            return tables
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error getting tables: {str(e)}\nFull traceback:\n{error_details}")
            # Log the SQL query that caused the error
            logger.error(f"SQL query that caused the error: {sql}")
            logger.error(f"Parameters used: { {'schema': schema} if schema else 'No parameters' }")
            raise
        finally:
            # Ensure the connection is closed
            if 'connector' in locals():
                connector.disconnect()
    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
            
        logger.info(f"PostgreSQL: Getting schema for table '{table_name}' in schema '{schema_name}' for connection {connection_id} ({connection.name})")
        
        connector = DatabaseConnector(
            db_type=DatabaseType.POSTGRESQL,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        # PostgreSQL statements always expect a schema parameter, so fall back to a
        # sensible default (connection database or standard 'public') when none is provided.
        target_schema = schema_name or connection.database or getattr(connection, "database_name", None) or "public"
        
        try:
            # Connect to the database
            success = connector.connect()
            if not success:
                raise RuntimeError(f"Failed to connect to PostgreSQL database: {connection.name}")
            
            # Helper to access row keys case-insensitively
            def _row_value(row: Dict[str, Any], *candidates: str) -> Optional[Any]:
                for key in candidates:
                    if key in row and row[key] is not None:
                        return row[key]
                    upper = key.upper()
                    if upper in row and row[upper] is not None:
                        return row[upper]
                return None
            
            params = {"schema": target_schema, "table": table_name}
            
            # Get columns information using DatabaseConnector helper (handles named params)
            columns_sql = self.sql_statements.get_columns_statement(schema_name, table_name)
            column_rows = connector.execute_query(columns_sql, params=params)
            
            if not column_rows:
                raise ValueError(f"No column metadata returned for {target_schema}.{table_name}")
            
            columns_dict: Dict[str, Dict[str, Any]] = {}
            for row in column_rows:
                column_name = str(_row_value(row, "column_name"))
                data_type = _row_value(row, "data_type", "udt_name")
                is_nullable = (_row_value(row, "is_nullable") or "").upper() == "YES"
                is_pk_flag = _row_value(row, "is_primary_key", "primary_key", "pk", "pk_flag")
                columns_dict[column_name] = {
                    "name": column_name,
                    "type": data_type,
                    "nullable": is_nullable,
                    "primary_key": bool(is_pk_flag),
                }
            
            # Get primary keys
            pk_sql = self.sql_statements.get_primary_keys_statement(schema_name, table_name)
            pk_rows = connector.execute_query(pk_sql, params=params)
            primary_keys = [
                str(_row_value(row, "column_name"))
                for row in (pk_rows or [])
                if _row_value(row, "column_name") is not None
            ]
            
            # Create the response
            schema_response = TableSchemaResponse(
                table_name=table_name,
                schema_name=target_schema,
                columns=columns_dict,
                primary_keys=primary_keys,
                foreign_keys=[]
            )
            
            logger.info(f"PostgreSQL: Retrieved schema for table '{table_name}' with {len(columns)} columns and {len(primary_keys)} primary keys")
            return schema_response
            
        except Exception as e:
            logger.error(f"Error getting table schema: {str(e)}")
            raise
            
        finally:
            # Ensure the connection is closed
            if 'connector' in locals():
                connector.disconnect()
