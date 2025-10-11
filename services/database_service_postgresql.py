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
            
            # Process the results
            result = cursor.fetchall()
            schemas = [row[0] for row in result if row[0] is not None]
            
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
            
            # Execute the query
            sql = self.sql_statements.get_tables_statement(schema)
            if schema:
                cursor.execute(sql, (schema,))
            else:
                cursor.execute(sql)
            
            # Process the results
            result = cursor.fetchall()
            tables = [row[0] for row in result if row[0] is not None]
            
            logger.info(f"PostgreSQL: Retrieved {len(tables)} tables for schema '{schema}': {tables}")
            
            # Ensure we return a proper list of strings
            return list(map(str, tables))
            
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
            
        logger.info(f"PostgreSQL: Getting schema for table '{table_name}' in schema '{schema_name}' for connection {connection_id} ({connection.name})")
        
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
            
            # Get columns information
            columns_sql = self.sql_statements.get_columns_statement(schema_name, table_name)
            
            if schema_name:
                cursor.execute(columns_sql, (schema_name, table_name))
            else:
                cursor.execute(columns_sql, (table_name,))
            
            # Process columns
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    'name': row[0],
                    'type': row[2],
                    'nullable': row[8] == 'YES',
                    'primary_key': row[9] == 1,
                })
            
            # Get primary keys
            pk_sql = self.sql_statements.get_primary_keys_statement(schema_name, table_name)
            if schema_name:
                cursor.execute(pk_sql, (schema_name, table_name))
            else:
                cursor.execute(pk_sql, (table_name,))
                
            primary_keys = [row[0] for row in cursor.fetchall()]
            
            # Create the response
            schema_response = TableSchemaResponse(
                table_name=table_name,
                schema_name=schema_name,
                columns=columns,
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
