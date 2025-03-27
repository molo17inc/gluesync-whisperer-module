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
        
        # Handle JDBC connections separately
        if db_connection.db_type == DatabaseType.AS400 and hasattr(engine, 'get_tables'):
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
        
        # Handle JDBC connections separately for AS400
        if db_connection.db_type == DatabaseType.AS400 and hasattr(engine, 'connection'):
            try:
                # For JDBC, we need to use a direct approach
                columns = {}
                primary_keys = []
                
                if not engine.connection:
                    engine.connect()
                
                cursor = engine.connection.cursor()
                try:
                    # Get columns for the table
                    metadata = cursor.connection.getMetaData()
                    schema = schema_name or (db_connection.database_name if db_connection.database_name else None)
                    
                    rs = metadata.getColumns(None, schema, table_name, "%")
                    while rs.next():
                        column_name = rs.getString("COLUMN_NAME")
                        data_type = rs.getString("TYPE_NAME")
                        nullable = (rs.getInt("NULLABLE") == 1)
                        columns[column_name] = {
                            'name': column_name,
                            'type': data_type,
                            'nullable': nullable
                        }
                    rs.close()
                    
                    # Get primary keys
                    rs = metadata.getPrimaryKeys(None, schema, table_name)
                    while rs.next():
                        column_name = rs.getString("COLUMN_NAME")
                        primary_keys.append(column_name)
                    rs.close()
                    
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
        """
        if connection.db_type == DatabaseType.MYSQL:
            # MySQL: mysql+pymysql://username:password@host:port/database
            return f"mysql+pymysql://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
        
        elif connection.db_type == DatabaseType.POSTGRESQL:
            # PostgreSQL: postgresql://username:password@host:port/database
            return f"postgresql://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
        
        elif connection.db_type == DatabaseType.SQLITE:
            # SQLite: sqlite:///path/to/database.db
            return f"sqlite:///{connection.database_name}"
        
        elif connection.db_type == DatabaseType.MSSQL:
            # MSSQL: mssql+pyodbc://username:password@host:port/database?driver=ODBC+Driver+17+for+SQL+Server
            driver = "ODBC+Driver+17+for+SQL+Server"
            return f"mssql+pyodbc://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}?driver={driver}"
        
        elif connection.db_type == DatabaseType.ORACLE:
            # Oracle: oracle+cx_oracle://username:password@host:port/service_name
            return f"oracle+cx_oracle://{connection.username}:{connection.password}@{connection.host}:{connection.port}/{connection.database_name}"
        
        elif connection.db_type == DatabaseType.AS400:
            # First try to use the native ibm_db_sa driver
            try:
                import ibm_db_sa
                # AS400: ibm_db_sa://username:password@host/database_name
                # Note: port is typically ignored for AS400, using the default port
                if connection.database_name:
                    return f"ibm_db_sa://{connection.username}:{connection.password}@{connection.host}/{connection.database_name}"
                else:
                    # If no database name is provided, connect without specifying one
                    return f"ibm_db_sa://{connection.username}:{connection.password}@{connection.host}"
            except ImportError:
                # Native drivers not available - try JDBC approach
                logger.warning("Native IBM DB2/AS400 drivers not available. Falling back to JDBC.")
                try:
                    # Check if JDBC utils are available
                    from utils import jdbc_utils
                    # We'll handle this connection directly through JDBC in create_engine_instance method
                    # Return a special connection string format to indicate JDBC usage
                    if connection.database_name:
                        return f"jdbc:as400://{connection.host}/{connection.database_name}"
                    else:
                        return f"jdbc:as400://{connection.host}"
                except ImportError:
                    # JDBC not available either
                    logger.error("Neither native IBM DB2 drivers nor JDBC utilities are available.")
                    raise ValueError("AS400 database support requires either ibm_db_sa or JDBC utilities.")
        
        else:
            raise ValueError(f"Unsupported database type: {connection.db_type}")

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
        
        # Check if this is a JDBC connection string (for AS400 fallback)
        if connection.connection_string.startswith("jdbc:as400://"):
            try:
                from utils import jdbc_utils
                
                # Extract host and optional database from the JDBC URL
                url_parts = connection.connection_string.replace("jdbc:as400://", "").split("/")
                host = url_parts[0]
                database = url_parts[1] if len(url_parts) > 1 else None
                
                # Get JDBC driver paths
                driver_paths = jdbc_utils.get_jdbc_drivers_path()
                if not driver_paths:
                    raise ValueError("No JDBC driver JAR files found in the jdbc_drivers directory")
                
                # Determine the appropriate JDBC URL
                if database:
                    jdbc_url = f"jdbc:as400://{host}/{database}"
                else:
                    jdbc_url = f"jdbc:as400://{host}"
                
                logger.info(f"Using JDBC for AS400 connection to {host}")
                
                # Create connection options
                driver_options = {
                    'user': connection.username,
                    'password': connection.password,
                    'prompt': 'false',
                    'naming': 'system',
                }
                
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
                
                # Create the wrapper with the AS400 JDBC driver
                engine = JdbcEngineWrapper(
                    jdbc_utils.connect_to_database,
                    driver_paths,
                    jdbc_url,
                    "com.ibm.as400.access.AS400JDBCDriver",
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
