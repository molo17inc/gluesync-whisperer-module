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

# Import the SQLAlchemy patch before any SQLAlchemy imports
# JDBC drivers are used for all database connections - no need for patching

import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from typing import List, Dict, Any, Optional

from models import DatabaseConnection, ConnectionStatus, DatabaseType
from schemas import DatabaseConnectionCreate, DatabaseConnectionUpdate, ConnectionTestResponse, TableSchemaResponse

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db: Session):
        self.db = db
        self.engines = {}  # Cache for database engines

    def create_connection(self, connection: DatabaseConnectionCreate) -> DatabaseConnection:
        """Create a new database connection."""
        # Build the connection string based on the database type
        connection_string = self._build_connection_string(connection)
        
        # Create the database connection record
        db_connection = DatabaseConnection(
            name=connection.name,
            description=connection.description,
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            database_name=connection.database_name,
            connection_string=connection_string,
            status=ConnectionStatus.IDLE
        )
        
        self.db.add(db_connection)
        self.db.commit()
        self.db.refresh(db_connection)
        
        return db_connection

    def get_connections(self, skip: int = 0, limit: int = 100) -> List[DatabaseConnection]:
        """Get all database connections."""
        # SQLAlchemy 2.0 syntax
        stmt = select(DatabaseConnection).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_connection(self, connection_id: int) -> Optional[DatabaseConnection]:
        """Get a specific database connection by ID."""
        # SQLAlchemy 2.0 syntax
        stmt = select(DatabaseConnection).where(DatabaseConnection.id == connection_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_connection_by_name(self, name: str) -> Optional[DatabaseConnection]:
        """Get a specific database connection by name."""
        # SQLAlchemy 2.0 syntax
        stmt = select(DatabaseConnection).where(DatabaseConnection.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def update_connection(self, connection_id: int, connection_update: DatabaseConnectionUpdate) -> DatabaseConnection:
        """Update a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Update fields that are provided
        update_data = connection_update.dict(exclude_unset=True)
        
        # If there are changes to connection parameters, rebuild the connection string
        rebuild_connection_string = False
        connection_params = ['db_type', 'host', 'port', 'username', 'password', 'database_name']
        for param in connection_params:
            if param in update_data:
                rebuild_connection_string = True
                break
        
        for key, value in update_data.items():
            setattr(db_connection, key, value)
        
        if rebuild_connection_string:
            connection_string = self._build_connection_string(db_connection)
            db_connection.connection_string = connection_string
            
            # Remove from engine cache if it exists
            if connection_id in self.engines:
                del self.engines[connection_id]
        
        self.db.commit()
        self.db.refresh(db_connection)
        
        return db_connection

    def delete_connection(self, connection_id: int) -> None:
        """Delete a database connection."""
        db_connection = self.get_connection(connection_id)
        
        # Remove from engine cache if it exists
        if connection_id in self.engines:
            del self.engines[connection_id]
        
        self.db.delete(db_connection)
        self.db.commit()

    def update_connection_status(self, connection_id: int, status: ConnectionStatus) -> DatabaseConnection:
        """Update a database connection status."""
        db_connection = self.get_connection(connection_id)
        db_connection.status = status
        
        self.db.commit()
        self.db.refresh(db_connection)
        
        return db_connection

    def test_connection(self, connection_id: int) -> ConnectionTestResponse:
        """Test a database connection."""
        db_connection = self.get_connection(connection_id)
        
        try:
            # Try to connect to the database
            engine = self._get_engine(db_connection)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            
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
                return [db_connection.database_name if db_connection.database_name else 'QGPL']
        
        # Standard SQLAlchemy approach for other engines
        try:
            # Get all schemas using SQLAlchemy inspector
            inspector = inspect(engine)
            schemas = inspector.get_schema_names()
            return schemas
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
                        result = conn.execute(sqlalchemy.text("SELECT name FROM sys.schemas WHERE name NOT LIKE 'db\_%' AND name != 'sys' AND name != 'INFORMATION_SCHEMA'"))
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
                return [db_connection.database_name if db_connection.database_name else 'default']
                
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
            # Get the inspector
            inspector = inspect(engine)
            
            # For database types that require schemas, make sure one is provided
            if schema is None:
                # SQLite doesn't use schemas in the traditional sense
                if db_connection.db_type == DatabaseType.SQLITE:
                    return inspector.get_table_names()
                else:
                    # For all other database types, require a schema
                    schemas = self.get_schemas(connection_id)
                    schema_list = "\n - ".join(schemas)
                    error_msg = f"Schema parameter is required. Available schemas:\n - {schema_list}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                    
            # Get tables for the specified schema
            return inspector.get_table_names(schema=schema)
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            raise

    def get_table_schema(self, connection_id: int, table_name: str, schema_name: str = None) -> TableSchemaResponse:
        """Get the schema of a table."""
        db_connection = self.get_connection(connection_id)
        
        # Get the database engine
        engine = self._get_engine(db_connection)
        
        # Handle JDBC connections separately for AS400 and MS SQL Server
        if db_connection.db_type in [DatabaseType.AS400, DatabaseType.MSSQL] and hasattr(engine, 'connection'):
            try:
                # For JDBC, we need to use a direct approach with SQL queries
                columns = {}
                primary_keys = []
                
                if not engine.connection:
                    engine.connect()
                
                cursor = engine.connection.cursor()
                try:
                    # Determine schema to use
                    schema = schema_name or (db_connection.database_name if db_connection.database_name else None)
                    
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
        
        # Standard SQLAlchemy approach for other engines
        try:
            # Get table schema
            inspector = inspect(engine)
            
            # Get column information
            columns = {}
            primary_keys = []
            
            # Determine schema
            schema = schema_name
            if not schema:
                if db_connection.db_type == DatabaseType.POSTGRESQL:
                    schema = 'public'
            
            # Get primary key columns
            pk_constraint = inspector.get_pk_constraint(table_name, schema=schema)
            if pk_constraint and 'constrained_columns' in pk_constraint:
                primary_keys = pk_constraint['constrained_columns']
            
            # Get column details
            for column in inspector.get_columns(table_name, schema=schema):
                col_name = column['name']
                col_type = str(column['type'])
                columns[col_name] = {
                    'type': col_type,
                    'nullable': column.get('nullable', True),
                    'default': str(column.get('default', None)) if column.get('default') else None,
                    'is_primary_key': col_name in primary_keys
                }
            
            return TableSchemaResponse(
                table_name=table_name,
                columns=columns,
                primary_keys=primary_keys
            )
        except Exception as e:
            logger.error(f"Error getting table schema via SQLAlchemy: {str(e)}")
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
                return f"mysql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver=com.mysql.cj.jdbc.Driver"
            
            elif connection.db_type == DatabaseType.POSTGRESQL:
                # PostgreSQL with JDBC
                return f"postgresql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver=org.postgresql.Driver"
            
            elif connection.db_type == DatabaseType.SQLITE:
                # SQLite: still use sqlite:// protocol as it's not JDBC-based
                return f"sqlite:///{connection.database_name}"
            
            elif connection.db_type == DatabaseType.MSSQL:
                # MS SQL Server with JDBC
                return f"mssql+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver=com.microsoft.sqlserver.jdbc.SQLServerDriver&trustServerCertificate=true&encrypt=true"
            
            elif connection.db_type == DatabaseType.ORACLE:
                # Oracle with JDBC
                return f"oracle+jdbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver=oracle.jdbc.OracleDriver"
            
            elif connection.db_type == DatabaseType.AS400:
                # AS400 with JDBC
                if connection.database_name:
                    return f"as400+jdbc://{connection.username}:{connection.password}@{connection.host}/{connection.database_name}?driver=com.ibm.as400.access.AS400JDBCDriver"
                else:
                    return f"as400+jdbc://{connection.username}:{connection.password}@{connection.host}?driver=com.ibm.as400.access.AS400JDBCDriver"
                    
            else:
                raise ValueError(f"Unsupported database type: {connection.db_type}")
                
        except ImportError:
            # JDBC not available
            logger.error("JDBC utilities not available. All database connections require JDBC support.")
            raise ValueError("Database connections require JDBC utilities.")

    def _get_engine(self, connection: DatabaseConnection):
        """
        Get or create a database engine for a connection.
        For AS400 connections on platforms without native driver support,
        this will use JDBC via the jdbc_utils module.
        """
        connection_id = connection.id
        
        # Return cached engine if available
        if connection_id in self.engines:
            return self.engines[connection_id]
        
        # Check if this is a JDBC connection string (for any supported database)
        if ('+jdbc' in connection.connection_string or connection.connection_string.startswith("jdbc:")):
            try:
                from utils import jdbc_utils
                
                # Get JDBC driver paths
                driver_paths = jdbc_utils.get_jdbc_drivers_path()
                if not driver_paths:
                    raise ValueError("No JDBC driver JAR files found in the jdbc_drivers directory")
                
                # Determine database type and set appropriate JDBC URL and driver class
                jdbc_url = connection.connection_string
                driver_class = None
                driver_options = {
                    'user': connection.username,
                    'password': connection.password,
                }
                
                if connection.db_type == DatabaseType.AS400:
                    # Extract host and optional database from the JDBC URL for AS400
                    url_parts = connection.connection_string.replace("jdbc:as400://", "").split("/")
                    host = url_parts[0]
                    database = url_parts[1] if len(url_parts) > 1 else None
                    
                    # Rebuild the AS400 JDBC URL
                    if database:
                        jdbc_url = f"jdbc:as400://{host}/{database}"
                    else:
                        jdbc_url = f"jdbc:as400://{host}"
                    
                    logger.info(f"Using JDBC for AS400 connection to {host}")
                    
                    # AS400-specific connection options
                    driver_options.update({
                        'prompt': 'false',
                        'naming': 'system',
                    })
                    
                    driver_class = "com.ibm.as400.access.AS400JDBCDriver"
                    
                elif connection.db_type == DatabaseType.MSSQL:
                    # The JDBC URL for SQL Server is already in the correct format
                    logger.info(f"Using JDBC for MS SQL Server connection to {jdbc_url}")
                    driver_class = "com.microsoft.sqlserver.jdbc.SQLServerDriver"
                
                # We can't use SQLAlchemy directly with JDBC in this case,
                # so we'll create a wrapper object that provides the minimum functionality needed
                class JdbcEngineWrapper:
                    def __init__(self, conn_func, driver_paths, jdbc_url, driver_class, options):
                        self.conn_func = conn_func
                        self.driver_paths = driver_paths
                        self.jdbc_url = jdbc_url
                        self.driver_class = driver_class
                        self.options = options
                        self.connection = None
                        self.url = jdbc_url  # Required for SQLAlchemy inspector
                    
                    def connect(self):
                        # Connect using JDBC
                        self.connection = self.conn_func(
                            self.driver_paths,
                            self.jdbc_url,
                            self.driver_class,
                            self.options
                        )
                        return self.connection
                    
                    def execute(self, query):
                        # Make sure we have a connection
                        if not self.connection:
                            self.connect()
                        # Execute through JDBC
                        return jdbc_utils.execute_query(self.connection, query)
                    
                    def get_schemas(self):
                        """Get all schemas in the database."""
                        # Make sure we have a connection
                        if not self.connection:
                            self.connect()
                        # Get schemas through JDBC
                        return jdbc_utils.get_schemas(self.connection)
                    
                    def get_tables(self, schema=None):
                        """Get all tables in the specified schema."""
                        # Make sure we have a connection
                        if not self.connection:
                            self.connect()
                        # Get tables through JDBC
                        return jdbc_utils.get_tables(self.connection, schema)
                    
                    def dispose(self):
                        # Clean up resources
                        if self.connection:
                            try:
                                self.connection.close()
                            except:
                                pass
                            self.connection = None
                    
                    # Support methods for SQLAlchemy inspection
                    def dialect(self):
                        # Simulate the dialect property for SQLAlchemy inspector
                        class Dialect:
                            def get_schema_names(self, conn):
                                if not conn.connection:
                                    conn.connect()
                                return jdbc_utils.get_schemas(conn.connection)
                                
                            def get_table_names(self, conn, schema=None):
                                if not conn.connection:
                                    conn.connect()
                                return jdbc_utils.get_tables(conn.connection, schema)
                        
                        return Dialect()
                
                # Create the wrapper with the appropriate JDBC driver
                engine = JdbcEngineWrapper(
                    jdbc_utils.connect_to_database,
                    driver_paths,
                    jdbc_url,
                    driver_class,
                    driver_options
                )
                
                self.engines[connection_id] = engine
                return engine
                
            except ImportError as e:
                logger.error(f"Failed to import JDBC utilities: {str(e)}")
                raise ValueError("JDBC support is required for AS400 on this platform but is not available")
            except Exception as e:
                logger.error(f"Error creating JDBC engine: {str(e)}")
                raise Exception(f"Failed to create JDBC engine: {str(e)}")
        
        # Standard SQLAlchemy engine creation for other database types
        try:
            # Use NullPool to avoid leaving connections open
            engine = create_engine(connection.connection_string, poolclass=NullPool)
            self.engines[connection_id] = engine
            return engine
        except Exception as e:
            logger.error(f"Error creating database engine: {str(e)}")
            raise Exception(f"Failed to create database engine: {str(e)}")
