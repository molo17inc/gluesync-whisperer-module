#!/usr/bin/env python3

import logging
from typing import List, Dict, Any, Optional

from models import DatabaseConnection
from schemas import TableSchemaResponse
from services.database_service_base import DatabaseServiceBase
from utils.db_connector import DatabaseConnector, DatabaseType
from utils.sql.factory import get_sql_statements

logger = logging.getLogger(__name__)


class MySQLDatabaseService(DatabaseServiceBase):
    """MySQL database service implementation."""

    def __init__(self, db):
        super().__init__(db)
        self.sql_statements = get_sql_statements(DatabaseType.MYSQL)

    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        return f"jdbc:mysql://{connection.host}:{connection.port}/{connection.database}"

    def _get_engine(self, connection: DatabaseConnection) -> Any:
        connection_id = connection.id
        if connection_id in self.engines:
            return self.engines[connection_id]

        logger.info(f"Creating MySQL connector for connection: {connection.name}")
        connector = DatabaseConnector(
            db_type=DatabaseType.MYSQL,
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

        logger.info(f"MySQL: Getting schemas for connection {connection_id} ({connection.name})")
        connector = DatabaseConnector(
            db_type=DatabaseType.MYSQL,
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
                raise RuntimeError(f"Failed to connect to MySQL database: {connection.name}")
            
            # Get the database connection
            conn = connector.connection
            cursor = conn.cursor()
            
            # Execute the query
            sql = self.sql_statements.get_schemas_statement()
            cursor.execute(sql)
            
            # Process the results
            result = cursor.fetchall()
            schemas = [str(row[0]) for row in result if row[0] is not None]
            
            logger.info(f"MySQL: Retrieved {len(schemas)} schemas: {schemas}")
            
            # Ensure we return a proper list of strings
            return list(map(str, schemas))
            
        except Exception as e:
            logger.error(f"Error getting schemas: {str(e)}")
            raise
        finally:
            # Ensure the connection is closed
            if 'connector' in locals():
                try:
                    cursor.close()
                except:
                    pass
                connector.disconnect()

    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        logger.info(f"MySQL: Getting tables for connection {connection_id} ({connection.name}), schema: {schema}")
        connector = DatabaseConnector(
            db_type=DatabaseType.MYSQL,
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
                raise RuntimeError(f"Failed to connect to MySQL database: {connection.name}")
            
            # Get the database connection
            conn = connector.connection
            cursor = conn.cursor()
            
            # Execute the query with schema already included in the SQL string
            sql = self.sql_statements.get_tables_statement(schema)
            cursor.execute(sql)
            
            # Process the results
            result = cursor.fetchall()
            tables = [{"name": str(row[0]), "schema_name": schema or ""} for row in result if row[0] is not None]
            
            logger.info(f"MySQL: Retrieved {len(tables)} tables for schema '{schema}': {tables}")
            return tables
            
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            raise
        finally:
            # Ensure the connection is closed
            if 'connector' in locals():
                connector.disconnect()

    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
            
        logger.info(f"MySQL: Getting schema for table '{table_name}' in schema '{schema_name}' for connection {connection_id} ({connection.name})")
        
        connector = DatabaseConnector(
            db_type=DatabaseType.MYSQL,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        
        # Determine which schema to query against. If the caller didn't pass one,
        # fall back to the connection default so the parameterized statements
        # still receive the expected arguments.
        target_schema = schema_name or connection.database or getattr(connection, "database_name", None)
        if not target_schema:
            raise ValueError("Schema name is required for MySQL table schema inspection.")
        
        try:
            # Connect to the database
            success = connector.connect()
            if not success:
                raise RuntimeError(f"Failed to connect to MySQL database: {connection.name}")
            
            # Get the database connection
            conn = connector.connection
            cursor = conn.cursor()
            
            # Get columns information
            columns_sql = self.sql_statements.get_columns_statement(target_schema, table_name)
            
            cursor.execute(columns_sql, (target_schema, table_name))
            
            # Process columns
            columns_dict = {}
            column_rows = cursor.fetchall()
            logger.debug(f"MySQL schema raw column rows count: {len(column_rows)}")
            for row in column_rows:
                column_name = str(row[0])
                columns_dict[column_name] = {
                    'name': column_name,
                    'type': row[3],
                    'nullable': row[13] == 'YES' if len(row) > 13 else True,
                    'primary_key': row[12] == 1 if len(row) > 12 else False,
                }
            
            # Get primary keys
            pk_sql = self.sql_statements.get_primary_keys_statement(target_schema, table_name)
            cursor.execute(pk_sql, (target_schema, table_name))
                
            primary_key_rows = cursor.fetchall()
            logger.debug(f"MySQL schema raw PK rows: {primary_key_rows}")
            primary_keys = [str(row[0]) for row in primary_key_rows if row and row[0] is not None]
            
            # Create the response
            schema_response = TableSchemaResponse(
                table_name=table_name,
                schema_name=target_schema,
                columns=columns_dict,
                primary_keys=primary_keys,
                foreign_keys=[]
            )
            
            logger.info(f"MySQL: Retrieved schema for {schema_name or 'default'}.{table_name}: {len(columns_dict)} columns, {len(primary_keys)} primary keys")
            return schema_response
            
        except Exception as e:
            logger.error(f"Error getting table schema: {str(e)}")
            raise
            
        finally:
            # Ensure the connection is closed
            if 'connector' in locals():
                connector.disconnect()