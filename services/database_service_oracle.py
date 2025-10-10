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

        logger.info(f"Creating Oracle engine for connection: {connection.name}")
        connector = DatabaseConnector(DatabaseType.ORACLE)
        engine = connector.get_engine(
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        self.engines[connection_id] = engine
        return engine

    def get_schemas(self, connection_id: int) -> List[str]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        engine = self._get_engine(connection)
        sql = self.sql_statements.get_schemas_statement()

        with engine.connect() as conn:
            result = conn.execute(sql)
            schemas = [row[0] for row in result if row[0] is not None]

        return schemas

    def get_tables(self, connection_id: int, schema: str = None) -> List[str]:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        engine = self._get_engine(connection)
        sql = self.sql_statements.get_tables_statement(schema)

        with engine.connect() as conn:
            if schema:
                result = conn.execute(sql, {"schema": schema})
            else:
                result = conn.execute(sql)

            tables = [row[0] for row in result if row[0] is not None]

        return tables

    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")

        engine = self._get_engine(connection)
        sql = self.sql_statements.get_columns_statement(schema_name, table_name)

        with engine.connect() as conn:
            if schema_name:
                result = conn.execute(sql, {"schema": schema_name, "table": table_name})
            else:
                result = conn.execute(sql, {"table": table_name})

            columns = []
            for row in result:
                columns.append({
                    'name': row[0],
                    'type': row[2],
                    'nullable': row[6] == 'YES',
                    'primary_key': row[9] == 1 if len(row) > 9 else False,
                })

            pk_sql = self.sql_statements.get_primary_keys_statement(schema_name, table_name)
            pk_result = conn.execute(pk_sql, {"schema": schema_name, "table": table_name} if schema_name else {"table": table_name})
            primary_keys = [row[0] for row in pk_result]

            schema_response = TableSchemaResponse(
                table_name=table_name,
                schema_name=schema_name,
                columns=columns,
                primary_keys=primary_keys,
                foreign_keys=[]
            )

        return schema_response
