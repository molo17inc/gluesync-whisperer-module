#!/usr/bin/env python3

import logging
from typing import List, Dict, Any, Optional

from models import DatabaseConnection
from schemas import TableSchemaResponse
from services.database_service_base import DatabaseServiceBase
from utils.db_connector import DatabaseConnector, DatabaseType
from utils.sql.factory import get_sql_statements

logger = logging.getLogger(__name__)


class OracleDatabaseService(DatabaseServiceBase):
    """Oracle database service implementation."""

    def __init__(self, db):
        super().__init__(db)
        self.sql_statements = get_sql_statements(DatabaseType.ORACLE)

    def _build_connection_string(self, connection: DatabaseConnection) -> str:
        return f"jdbc:oracle:thin:@{connection.host}:{connection.port}/{connection.database}"

    def _get_engine(self, connection: DatabaseConnection) -> Any:
        connection_id = connection.id
        if connection_id in self.engines:
            return self.engines[connection_id]

        logger.info(f"Creating Oracle connector for connection: {connection.name}")
        connector = DatabaseConnector(
            db_type=DatabaseType.ORACLE,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password,
        )

        success = connector.connect()
        if not success:
            raise RuntimeError(f"Failed to connect to Oracle database for connection {connection.name}")

        self.engines[connection_id] = connector
        return connector

    @staticmethod
    def _get_row_value(row: Dict[str, Any], *keys: str) -> Optional[Any]:
        if not row:
            return None
        lower_map = {k.lower(): k for k in row}
        for key in keys:
            actual = lower_map.get(key.lower())
            if actual is not None:
                return row[actual]
        # Fallback to first value
        return next(iter(row.values())) if row else None

    def _get_connected_connector(self, connection: DatabaseConnection) -> DatabaseConnector:
        connector = self._get_engine(connection)
        if not connector.is_connected():
            success = connector.connect()
            if not success:
                raise RuntimeError(f"Failed to reconnect to Oracle database for connection {connection.name}")
        return connector

    def get_schemas(self, connection_id: int) -> List[str]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        connector = self._get_connected_connector(connection)
        sql = self.sql_statements.get_schemas_statement()

        try:
            result = connector.execute_query(sql)
            schemas = []
            for row in result:
                schema = self._get_row_value(row, "schema_name", "username")
                if schema:
                    schemas.append(str(schema))
            return schemas
        except Exception as exc:
            logger.error(f"Error getting Oracle schemas: {exc}")
            raise

    def get_tables(self, connection_id: int, schema: str = None) -> List[Dict[str, str]]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        connector = self._get_connected_connector(connection)
        sql = self.sql_statements.get_tables_statement(schema)
        params = {"schema": schema} if schema else None

        try:
            result = connector.execute_query(sql, params=params)
            tables: List[Dict[str, str]] = []
            schema_value = schema or connection.database or connection.username or ""
            for row in result:
                table_name = self._get_row_value(row, "table_name")
                if table_name:
                    tables.append({
                        "name": str(table_name),
                        "schema_name": str(schema_value)
                    })
            return tables
        except Exception as exc:
            logger.error(f"Error getting Oracle tables: {exc}")
            raise

    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        connector = self._get_connected_connector(connection)
        sql = self.sql_statements.get_columns_statement(schema_name, table_name)
        column_params = {"table": table_name}
        if schema_name:
            column_params["schema"] = schema_name

        try:
            column_rows = connector.execute_query(sql, params=column_params)
        except Exception as exc:
            logger.error(f"Error getting Oracle columns: {exc}")
            raise

        columns: List[Dict[str, Any]] = []
        for row in column_rows:
            row_lower = {k.lower(): v for k, v in row.items()}
            name = row_lower.get('column_name')
            if not name:
                continue

            data_type = row_lower.get('data_type')
            nullable_flag = str(row_lower.get('is_nullable', '')).upper()
            is_nullable = nullable_flag in ('YES', 'Y', 'TRUE', '1')
            pk_flag = str(row_lower.get('is_primary_key', '0')).upper()
            is_primary = pk_flag in ('1', 'TRUE', 'YES', 'Y')

            columns.append({
                'name': str(name),
                'type': str(data_type) if data_type is not None else '',
                'nullable': is_nullable,
                'primary_key': is_primary,
            })

        pk_sql = self.sql_statements.get_primary_keys_statement(schema_name, table_name)
        pk_params = {"table": table_name}
        if schema_name:
            pk_params["schema"] = schema_name

        try:
            pk_rows = connector.execute_query(pk_sql, params=pk_params)
        except Exception as exc:
            logger.error(f"Error getting Oracle primary keys: {exc}")
            raise

        primary_keys = []
        for row in pk_rows:
            pk_name = self._get_row_value(row, 'column_name')
            if pk_name:
                primary_keys.append(str(pk_name))

        pk_set = set(primary_keys)
        if pk_set:
            for column in columns:
                if column['name'] in pk_set:
                    column['primary_key'] = True

        schema_response = TableSchemaResponse(
            table_name=table_name,
            schema_name=schema_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=[]
        )

        return schema_response
