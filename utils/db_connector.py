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

import argparse
import logging
import os
import sys
import json
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType
from utils.sql import get_sql_statements

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def build_connection_string(db_type, host, port, username, password, database_name):
    """Build a connection string based on database type and parameters."""
    if db_type == DatabaseType.MYSQL:
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type == DatabaseType.POSTGRESQL:
        return f"postgresql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type == DatabaseType.SQLITE:
        return f"sqlite:///{database_name}"
    elif db_type == DatabaseType.MSSQL:
        return f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database_name}?driver=ODBC+Driver+17+for+SQL+Server"
    elif db_type == DatabaseType.ORACLE:
        return f"oracle+cx_oracle://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type == DatabaseType.AS400:
        # IBM i Series uses 'ibm_db_sa' dialect, or 'pyodbc' with the proper driver
        # This requires installing either:
        #   - ibm_db and ibm_db_sa packages (pip install ibm_db ibm_db_sa)
        #   - pyodbc with IBM i Access ODBC Driver installed on the system
        # 
        # Default port for IBM i is 446 but can be overridden
        # Format: ibm_db_sa://username:password@host:port/database
        # Alternatively with pyodbc: pyodbc://username:password@dsn_name
        if host and port:
            return f"ibm_db_sa://{username}:{password}@{host}:{port}/{database_name}"
        else:
            # If no host/port, assume DSN configuration with pyodbc
            return f"pyodbc://{username}:{password}@{database_name}?driver=IBM+i+Access+ODBC+Driver"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

class DatabaseConnector:
    """Class to handle database connections using SQLAlchemy."""
    
    def __init__(self, db_type, host=None, port=None, database=None, username=None, password=None):
        """Initialize database connection parameters."""
        self.db_type = db_type
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.engine = None
        self.inspector = None
        # Initialize database-specific SQL statements based on type
        self.sql_statements = get_sql_statements(db_type)
    
    def connect(self):
        """Connect to the database."""
        try:
            # Use JDBC for AS400 connections on all architectures
            if self.db_type == DatabaseType.AS400:
                # Always use JDBC approach for AS400 - more consistent across architectures
                from utils.jdbc_utils import get_jdbc_drivers_path, connect_to_database, execute_query
                
                # Get JDBC driver paths
                jdbc_driver_paths = get_jdbc_drivers_path()
                
                # Format JDBC connection string for AS400
                jdbc_url = f"jdbc:as400://{self.host}/{self.database}"
                jdbc_driver = "com.ibm.as400.access.AS400JDBCDriver"
                
                # Connection properties
                connection_props = {
                    "user": self.username,
                    "password": self.password,
                    "prompt": "false",
                    "libraries": self.database
                }
                
                # Create a JDBC connection
                self.connection = connect_to_database(
                    driver_path=jdbc_driver_paths,
                    connection_string=jdbc_url,
                    driverclass=jdbc_driver,
                    driver_options=connection_props
                )
                
                # Store a reference to execute_query for JDBC
                self.jdbc_execute_query = execute_query
                
                # Create a wrapper engine object with necessary methods
                class JdbcEngineWrapper:
                    def __init__(self, connection, execute_fn):
                        self.connection = connection
                        self.execute_query = execute_fn
                
                # Create an engine wrapper that mimics the needed SQLAlchemy engine functionality
                self.engine = JdbcEngineWrapper(self.connection, execute_query)
                self.version = "JDBC AS400"
                logger.info(f"Connected to {self.db_type.value} database via JDBC")
                return True
            else:
                # Normal SQLAlchemy connection for other database types
                if self.db_type == DatabaseType.SQLITE:
                    connection_string = build_connection_string(
                        self.db_type, None, None, None, None, self.database
                    )
                else:
                    connection_string = build_connection_string(
                        self.db_type, self.host, self.port, self.username, self.password, self.database
                    )
                
                # Create engine and test connection
                self.engine = create_engine(connection_string)
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                
                # Create inspector
                self.inspector = inspect(self.engine)
            
            # Get database version
            self.version = self.get_database_version()
            
            logger.info(f"Connected to {self.db_type.value} database version {self.version}")
            return True
        
        except SQLAlchemyError as e:
            logger.error(f"Error connecting to database: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            return False
            
    def get_database_version(self):
        """Get the database version using database-specific SQL statements."""
        try:
            if not self.engine:
                return "unknown"
                
            # Get version SQL statement from our specialized SQL statements
            version_query = self.sql_statements.get_version_statement()
            
            # Execute the version query
            result = self.execute_query(version_query)
            
            if result and len(result) > 0:
                # Extract version info from result
                row = result[0]
                
                # Different databases return version in different column names
                if 'VERSION()' in row:
                    return row['VERSION()']
                elif 'version' in row:
                    return row['version']
                elif 'VERSION' in row:
                    return row['VERSION']
                elif 'BANNER' in row: # Oracle specific
                    return row['BANNER']
                else:
                    # Return first column's value if we can't identify a specific version column
                    return list(row.values())[0]
            
            return "unknown"
        except Exception as e:
            logger.warning(f"Error getting database version: {str(e)}")
            return "unknown"
    
    def disconnect(self):
        """Disconnect from the database."""
        if self.engine:
            try:
                # Check if it's a JDBC connection
                if self.db_type == DatabaseType.AS400 or hasattr(self.engine, 'connection') and 'jdbc' in str(type(self.engine)).lower():
                    # For JDBC connections, close the connection instead of disposing the engine
                    if hasattr(self, 'connection') and self.connection is not None:
                        self.connection.close()
                        logger.info("Closed JDBC connection")
                else:
                    # For SQLAlchemy engines, use dispose
                    self.engine.dispose()
                logger.info("Disconnected from database")
            except Exception as e:
                logger.warning(f"Error during database disconnect: {str(e)}")
    
    def get_tables(self, schema=None):
        """Get a list of all tables in the database."""
        if not self.engine:
            raise RuntimeError("Not connected to database")
        
        try:
            # Use specialized SQL statements specific to the database type
            if schema is None and self.db_type != DatabaseType.SQLITE:
                # Try to get schema from connection
                schema = self.database
            
            if self.db_type == DatabaseType.SQLITE:
                # For SQLite, which doesn't have schemas in the traditional sense
                query = self.sql_statements.get_tables_statement()
                result = self.execute_query(query)
            else:
                # For databases with schemas
                query = self.sql_statements.get_tables_statement(schema)
                if '?' in query:
                        # The SQL statements now use named parameters directly, no need to replace ?
                    result = self.execute_query(query, params={'schema': schema})
                else:
                    result = self.execute_query(query, params={'schema': schema})
            
            tables = []
            if result:
                # Extract table names, handling different result structures
                if isinstance(result, list) and len(result) > 0:
                    if 'TABLE_NAME' in result[0]:
                        tables = [row['TABLE_NAME'] for row in result]
                    elif 'table_name' in result[0]:
                        tables = [row['table_name'] for row in result]
                    elif len(result[0]) == 1:  # One-column result
                        tables = [list(row.values())[0] for row in result]
            
            logger.info(f"Found {len(tables)} tables in schema {schema}")
            for table in tables:
                logger.debug(f" - {table}")
            
            return tables
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            # Fallback to SQLAlchemy inspect method
            tables = self.inspector.get_table_names()
            logger.info(f"Using SQLAlchemy inspector, found {len(tables)} tables")
            return tables
            
    def get_tables_info(self, schema=None):
        """Get comprehensive information about all tables in the database.
        This is useful for dynamically detecting table relationships."""
        if not self.engine:
            raise RuntimeError("Not connected to database")
            
        try:
            # Get all table names first
            tables = self.get_tables(schema)
            
            # For each table, get schema information
            tables_info = {}
            for table in tables:
                try:
                    # Get detailed table schema
                    table_schema = self.get_table_schema(table, schema)
                    tables_info[table] = {
                        'columns': list(table_schema['columns'].keys()),
                        'primary_keys': table_schema['primary_keys'],
                        'foreign_keys': table_schema['foreign_keys']
                    }
                except Exception as e:
                    logger.warning(f"Error getting schema for table {table}: {str(e)}")
            
            return tables_info
        except Exception as e:
            logger.error(f"Error getting tables info: {str(e)}")
            return {}
    
    def get_table_schema(self, table_name, schema=None):
        """Get the schema of a table using database-specific SQL queries."""
        if not self.engine:
            raise RuntimeError("Not connected to database")
        
        try:
            # Use specialized SQL statements for this database type
            if schema is None and self.db_type != DatabaseType.SQLITE:
                # Try to get schema from connection
                schema = self.database
                
            # Make sure schema is never None for databases that require it
            if schema is None and self.db_type == DatabaseType.MYSQL:
                # For MySQL, use the database name if schema isn't specified
                schema = self.database
                
            # Get columns with detailed information
            columns = {}
            
            # Use database-specific column query
            if self.db_type == DatabaseType.SQLITE:
                query = self.sql_statements.get_columns_statement(table=table_name)
                column_results = self.execute_query(query)
                
                # SQLite PRAGMA table_info returns different column names
                for col in column_results:
                    name = col.get('name')
                    columns[name] = {
                        'type': col.get('type', ''),
                        'nullable': col.get('notnull', 1) == 0,  # 0 means nullable in SQLite
                        'default': col.get('dflt_value'),
                        'primary_key': col.get('pk', 0) == 1,  # 1 means primary key
                        'extra': ''
                    }
            else:
                # For other databases, use the specialized query
                query = self.sql_statements.get_columns_statement(schema, table_name)
                
                # For MySQL, directly substitute parameters to avoid escaping issues
                if self.db_type == DatabaseType.MYSQL:
                    # Directly substitute parameters in the query for MySQL
                    # This is a special case to work around the %s escaping issue
                    from sqlalchemy import text
                    
                    # Replace the %s with concrete values
                    import re
                    # Extract the SQL parts before and after WHERE clause
                    match = re.search(r'(.*WHERE\s+C\.TABLE_SCHEMA\s*=\s*)%s(\s*AND\s+C\.TABLE_NAME\s*=\s*)%s(.*)', query, re.DOTALL | re.IGNORECASE)
                    
                    if match:
                        part1, part2, part3 = match.groups()
                        # Create a query with literal values
                        formatted_query = f"{part1}'{schema}'{part2}'{table_name}'{part3}"
                        column_results = self.execute_query(formatted_query)
                    else:
                        # Fallback to inspector if we can't parse the query
                        logger.warning("Could not parse MySQL query pattern, falling back to SQLAlchemy inspector")
                        return self.inspector.get_columns(table_name)
                else:
                    # For other databases, use the standard parameter mechanism
                    params = {}
                    if schema is not None:
                        params['schema'] = schema
                    params['table'] = table_name
                    column_results = self.execute_query(query, params=params)
                
                # Process column results based on database type
                for col in column_results:
                    # Normalize column names (handle case sensitivity)
                    col_dict = {k.lower(): v for k, v in col.items()}
                    
                    # Extract common properties, adapting to various DB naming conventions
                    name = col_dict.get('column_name') or next((col_dict[k] for k in col_dict if 'column_name' in k.lower()), '')
                    data_type = col_dict.get('data_type') or next((col_dict[k] for k in col_dict if 'data_type' in k.lower()), '')
                    is_nullable = col_dict.get('is_nullable', 'YES') in ('YES', 'yes', 'Y', 'y', True, 1)
                    is_primary = col_dict.get('is_primary_key', 0) in (1, True, 'YES', 'yes', 'Y', 'y')
                    default_val = col_dict.get('column_default') or col_dict.get('default')
                    extra = col_dict.get('extra', '')
                    
                    # For MySQL, examine COLUMN_KEY and EXTRA for primary key and auto_increment
                    if self.db_type == DatabaseType.MYSQL:
                        if col_dict.get('column_key') == 'PRI':
                            is_primary = True
                        extra = col_dict.get('extra', '')
                    
                    # For PostgreSQL, check for identity columns
                    if self.db_type == DatabaseType.POSTGRESQL and 'identity' in str(default_val).lower():
                        extra = 'auto_increment'
                        
                    # For MS SQL Server, check for identity property
                    if self.db_type == DatabaseType.MSSQL and col_dict.get('is_identity', 0) in (1, True):
                        extra = 'auto_increment'
                    
                    # Store normalized column info
                    columns[name] = {
                        'type': data_type,
                        'nullable': is_nullable,
                        'default': default_val,
                        'primary_key': is_primary,
                        'extra': extra
                    }
            
            # Get primary keys specifically
            primary_keys = []
            try:
                if self.db_type == DatabaseType.SQLITE:
                    # For SQLite, primary keys already in column info
                    primary_keys = [name for name, col in columns.items() if col['primary_key']]
                else:
                    # For other databases, use dedicated query with named parameters
                    query = self.sql_statements.get_primary_keys_statement(schema, table_name)
                    
                    # Prepare parameters
                    named_params = {'table': table_name}
                    if schema is not None:
                        named_params['schema'] = schema
                    
                    # Execute query with parameters
                    pk_results = self.execute_query(query, params=named_params)
                    
                    if pk_results:
                        for pk_row in pk_results:
                            # Extract column name (adapt to various DB naming conventions)
                            pk_col = next((pk_row[k] for k in pk_row if 'column_name' in k.lower()), None)
                            if pk_col and pk_col in columns:
                                primary_keys.append(pk_col)
                                columns[pk_col]['primary_key'] = True
            except Exception as e:
                logger.warning(f"Error getting primary keys via standard query: {str(e)}")
                # Try JDBC metadata for AS400 if no keys found yet
                if not primary_keys and self.db_type == DatabaseType.AS400:
                    try:
                        logger.info(f"Attempting JDBC metadata primary key detection for AS400 table {table_name}")
                        
                        # For JDBC connections, ensure we have a connection first
                        if not hasattr(self, 'jdbc_conn') or not self.jdbc_conn:
                            # Try to get the JDBC connection from the engine
                            if hasattr(self, 'engine') and self.engine and hasattr(self.engine, 'connection'):
                                self.jdbc_conn = self.engine.connection
                                logger.info("Retrieved JDBC connection from engine for metadata operations")
                            elif hasattr(self, 'connection_string'):
                                # Reconnect using the connection_string if available
                                from utils.jdbc_utils import connect_jdbc
                                self.jdbc_conn = connect_jdbc(self.connection_string, self.username, self.password)
                                logger.info("Established new JDBC connection for metadata operations")
                        
                        # Now use the connection's metadata
                        if hasattr(self, 'jdbc_conn') and self.jdbc_conn:
                            conn = self.jdbc_conn
                            # Check if the connection has getMetaData method (not all JDBC bridges implement it)
                            if hasattr(conn, 'getMetaData'):
                                # Get metadata from the JDBC connection
                                metadata = conn.getMetaData()
                                
                                # Use metadata to get primary keys
                                schema_param = schema if schema else None
                                rs = metadata.getPrimaryKeys(None, schema_param, table_name)
                                
                                # Extract primary key column names
                                while rs.next():
                                    column_name = rs.getString("COLUMN_NAME")
                                    if column_name and column_name in columns:
                                        primary_keys.append(column_name)
                                        columns[column_name]['primary_key'] = True
                                
                                # Close the result set
                                rs.close()
                                
                                if primary_keys:
                                    logger.info(f"Found primary keys for AS400 table {table_name} using JDBC metadata: {primary_keys}")
                                else:
                                    logger.warning(f"No primary keys found for AS400 table {table_name} using JDBC metadata")
                            else:
                                logger.info(f"JDBC connection does not support getMetaData() method, skipping metadata-based primary key detection")
                        else:
                            logger.warning("No JDBC connection available for metadata retrieval even after reconnection attempt")
                    except Exception as e2:
                        logger.warning(f"Error with JDBC metadata primary key detection: {str(e2)}")
                
                # If still no primary keys, try SQLAlchemy inspector as a last resort
                if not primary_keys and self.inspector:
                    try:
                        pk_constraint = self.inspector.get_pk_constraint(table_name)
                        if pk_constraint and 'constrained_columns' in pk_constraint:
                            primary_keys = pk_constraint['constrained_columns']
                            for pk in primary_keys:
                                if pk in columns:
                                    columns[pk]['primary_key'] = True
                    except Exception as e3:
                        logger.warning(f"Error getting primary keys via SQLAlchemy: {str(e3)}")
            
            # Get foreign keys
            foreign_keys = []
            try:
                # Use JDBC metadata for AS400 foreign keys
                if self.db_type == DatabaseType.AS400:
                    # Ensure we have a valid JDBC connection first
                    if not hasattr(self, 'jdbc_conn') or not self.jdbc_conn:
                        # Try to get the JDBC connection from the engine
                        if hasattr(self, 'engine') and self.engine and hasattr(self.engine, 'connection'):
                            self.jdbc_conn = self.engine.connection
                            logger.info("Retrieved JDBC connection from engine for foreign key operations")
                        elif hasattr(self, 'connection_string'):
                            # Reconnect using the connection_string if available
                            from utils.jdbc_utils import connect_jdbc
                            self.jdbc_conn = connect_jdbc(self.connection_string, self.username, self.password)
                            logger.info("Established new JDBC connection for foreign key operations")
                    
                    if hasattr(self, 'jdbc_conn') and self.jdbc_conn:
                        try:
                            logger.info(f"Retrieving foreign keys for AS400 table {table_name} using JDBC metadata")
                            
                            # Get metadata from the JDBC connection
                            conn = self.jdbc_conn
                            rs = None
                            
                            # Check if the connection has getMetaData method (not all JDBC bridges implement it)
                            if hasattr(conn, 'getMetaData'):
                                metadata = conn.getMetaData()
                                
                                # Use metadata to get imported (foreign) keys
                                schema_param = schema if schema else None
                                rs = metadata.getImportedKeys(None, schema_param, table_name)
                            
                            # Process the result set if it exists
                            fk_dict = {}
                            if rs is not None:
                                while rs.next():
                                    fk_name = rs.getString("FK_NAME")
                                    fk_column = rs.getString("FKCOLUMN_NAME")
                                    pk_schema = rs.getString("PKTABLE_SCHEM")
                                    pk_table = rs.getString("PKTABLE_NAME")
                                    pk_column = rs.getString("PKCOLUMN_NAME")
                                    
                                    if fk_name not in fk_dict:
                                        fk_dict[fk_name] = {
                                            'constrained_columns': [],
                                            'referred_schema': pk_schema,
                                            'referred_table': pk_table,
                                            'referred_columns': []
                                        }
                                
                                if fk_column and fk_column not in fk_dict[fk_name]['constrained_columns']:
                                    fk_dict[fk_name]['constrained_columns'].append(fk_column)
                                
                                if pk_column and pk_column not in fk_dict[fk_name]['referred_columns']:
                                    fk_dict[fk_name]['referred_columns'].append(pk_column)
                            
                            # Close the result set
                            rs.close()
                            
                            # Add foreign keys to our list
                            for fk in fk_dict.values():
                                if fk['constrained_columns'] and fk['referred_columns']:
                                    foreign_keys.append(fk)
                            
                            if foreign_keys:
                                logger.info(f"Found {len(foreign_keys)} foreign keys for AS400 table {table_name} using JDBC metadata")
                            else:
                                logger.warning(f"No foreign keys found for AS400 table {table_name} using JDBC metadata")
                        except Exception as e:
                            logger.warning(f"Error getting AS400 foreign keys via JDBC metadata: {str(e)}")
                elif self.db_type != DatabaseType.SQLITE:
                    query = self.sql_statements.get_foreign_keys_statement(schema, table_name)
                    
                    # Handle different parameter styles based on database type
                    if self.db_type == DatabaseType.MYSQL and "%s" in query:
                        # For MySQL with %s placeholders, use direct string formatting
                        params = []
                        if schema:
                            params.append(schema)
                        if table_name:
                            params.append(table_name)
                            
                        # Safely format the query
                        formatted_query = query
                        for param in params:
                            placeholder_pos = formatted_query.find("%s")
                            if placeholder_pos >= 0:
                                # Apply proper quoting
                                quoted_value = f"'{param}'" if isinstance(param, str) else str(param)
                                formatted_query = formatted_query[:placeholder_pos] + quoted_value + formatted_query[placeholder_pos+2:]
                        
                        # Execute the formatted query without parameters
                        fk_results = self.execute_query(formatted_query)
                    elif '?' in query:
                        # For parameterized queries with ? placeholders
                        # Convert to named parameters for all database types
                        named_params = {}
                        if schema:
                            named_params['schema'] = schema
                        if table_name:
                            named_params['table'] = table_name
                        # Replace all ? with named parameters
                        modified_query = query
                        param_count = 1
                        while '?' in modified_query:
                            param_name = f':p{param_count}'
                            modified_query = modified_query.replace('?', param_name, 1)
                            param_count += 1
                        fk_results = self.execute_query(modified_query, params=named_params)
                    else:
                        # For other parameter styles (named parameters)
                        params = {}
                        if schema:
                            params['schema'] = schema
                        if table_name:
                            params['table'] = table_name
                        fk_results = self.execute_query(query, params=params)
                    
                    if fk_results:
                        for fk_row in fk_results:
                            # Extract and normalize foreign key information
                            fk_dict = {k.lower(): v for k, v in fk_row.items()}
                            column = fk_dict.get('column_name') or next((fk_dict[k] for k in fk_dict if 'column_name' in k.lower()), None)
                            ref_schema = fk_dict.get('referenced_table_schema') or schema
                            ref_table = fk_dict.get('referenced_table_name') or fk_dict.get('referenced_table')
                            ref_column = fk_dict.get('referenced_column_name') or fk_dict.get('referenced_column')
                            
                            if column and ref_table and ref_column:
                                foreign_keys.append({
                                    'constrained_columns': [column],
                                    'referred_schema': ref_schema,
                                    'referred_table': ref_table,
                                    'referred_columns': [ref_column]
                                })
            except Exception as e:
                logger.warning(f"Error getting foreign keys: {str(e)}")
                # Fallback to SQLAlchemy inspector
                for fk in self.inspector.get_foreign_keys(table_name):
                    foreign_keys.append({
                        'constrained_columns': fk.get('constrained_columns', []),
                        'referred_table': fk.get('referred_table', ''),
                        'referred_columns': fk.get('referred_columns', [])
                    })
            
            # Get indexes - primarily use SQLAlchemy here as index info is complex
            indexes = []
            try:
                # Special handling for AS400 - inspector might be None or not support get_indexes
                if self.db_type.name == 'AS400':
                    # For AS400, use the JDBC connection's metadata object directly
                    # This is more reliable than trying to query catalog tables which vary by system
                    try:
                        # Create empty indexes list for now
                        indexes = []
                        
                        # For JDBC connections, try to use the connection's metadata methods
                        if hasattr(self, 'jdbc_conn') and self.jdbc_conn:
                            # Get metadata from the JDBC connection
                            conn = self.jdbc_conn
                            rs = None
                            index_dict = {}
                            
                            # Check if the connection has getMetaData method (not all JDBC bridges implement it)
                            if hasattr(conn, 'getMetaData'):
                                metadata = conn.getMetaData()
                                
                                # Use metadata to get primary keys (these are also indexes)
                                schema_param = schema if schema else None
                                try:
                                    rs = metadata.getPrimaryKeys(None, schema_param, table_name)
                                    
                                    # Process the result set into our index structure
                                    pk_index = {
                                        'name': 'PRIMARY',
                                        'columns': [],
                                        'unique': True  # Primary keys are always unique
                                    }
                                    
                                    # Only process if we got a valid result set
                                    if rs is not None:
                                        while rs.next():
                                            column_name = rs.getString("COLUMN_NAME")
                                            if column_name and column_name not in pk_index['columns']:
                                                pk_index['columns'].append(column_name)
                                        
                                        # Close the result set
                                        rs.close()
                                        
                                        if pk_index['columns']:
                                            indexes.append(pk_index)
                                            logger.info(f"Found primary key for AS400 table {table_name} with columns: {pk_index['columns']}")
                                    
                                    # Now try to get other indexes
                                    try:
                                        rs = metadata.getIndexInfo(None, schema_param, table_name, False, True)
                                        
                                        # Group by index name
                                        index_dict = {}
                                        while rs.next():
                                            index_name = rs.getString("INDEX_NAME")
                                            column_name = rs.getString("COLUMN_NAME")
                                            non_unique = rs.getBoolean("NON_UNIQUE")
                                        
                                            if index_name and index_name != 'PRIMARY':
                                                if index_name not in index_dict:
                                                    index_dict[index_name] = {
                                                        'name': index_name,
                                                        'columns': [],
                                                        'unique': not non_unique
                                                    }
                                                if column_name and column_name not in index_dict[index_name]['columns']:
                                                    index_dict[index_name]['columns'].append(column_name)
                                        
                                        # Close the result set
                                        rs.close()
                                        
                                        # Add other indexes to our list
                                        for idx in index_dict.values():
                                            if idx['columns']:
                                                indexes.append(idx)
                                    except Exception as idx_err:
                                        logger.warning(f"Error getting index info: {idx_err}")
                                except Exception as pk_err:
                                    logger.warning(f"Error getting primary key info: {pk_err}")
                                    
                                if len(indexes) > 0:
                                    logger.info(f"Retrieved {len(indexes)} indexes for AS400 table {table_name} using JDBC metadata")
                                else:
                                    logger.warning(f"No indexes found for AS400 table {table_name}")
                            else:
                                logger.info(f"JDBC connection does not support getMetaData() method, skipping index retrieval")
                        else:
                            logger.warning("No JDBC connection available for metadata retrieval")
                            
                    except Exception as e:
                        logger.warning(f"Error getting AS400 indexes via JDBC metadata: {str(e)}")
                        # If this fails, we'll fall back to empty indexes
                        indexes = []
                elif self.inspector:  # Make sure inspector is not None
                    for idx in self.inspector.get_indexes(table_name):
                        indexes.append({
                            'name': idx.get('name', ''),
                            'columns': idx.get('column_names', []),
                            'unique': idx.get('unique', False)
                        })
                else:
                    logger.warning("SQLAlchemy inspector is None, cannot retrieve indexes")
            except Exception as e:
                logger.warning(f"Error getting indexes: {str(e)}")
            
            # Return consolidated schema information
            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys,
                'indexes': indexes
            }
        
        except Exception as e:
            logger.error(f"Error getting table schema: {str(e)}")
            # Fallback to the original SQLAlchemy-based implementation
            logger.info("Falling back to SQLAlchemy inspector for schema info")
            
            # Get columns using SQLAlchemy inspector
            columns = {}
            for column in self.inspector.get_columns(table_name):
                columns[column['name']] = {
                    'type': str(column['type']),
                    'nullable': column.get('nullable', True),
                    'default': str(column.get('default', None)),
                    'primary_key': False,  # Will be updated below
                    'extra': ''
                }
            
            # Get primary keys
            primary_keys = []
            pk_constraint = self.inspector.get_pk_constraint(table_name)
            if pk_constraint and 'constrained_columns' in pk_constraint:
                primary_keys = pk_constraint['constrained_columns']
                for pk in primary_keys:
                    if pk in columns:
                        columns[pk]['primary_key'] = True
            
            # Get foreign keys
            foreign_keys = []
            for fk in self.inspector.get_foreign_keys(table_name):
                foreign_keys.append({
                    'constrained_columns': fk.get('constrained_columns', []),
                    'referred_table': fk.get('referred_table', ''),
                    'referred_columns': fk.get('referred_columns', [])
                })
            
            # Get indexes
            indexes = []
            # Check if inspector exists and supports get_indexes
            if self.inspector and hasattr(self.inspector, 'get_indexes'):
                try:
                    for idx in self.inspector.get_indexes(table_name):
                        indexes.append({
                            'name': idx.get('name', ''),
                            'columns': idx.get('column_names', []),
                            'unique': idx.get('unique', False)
                        })
                except Exception as e:
                    logger.warning(f"Fallback method: Error getting indexes: {str(e)}")
            
            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys,
                'indexes': indexes
            }
    def execute_query(self, query, params=None, max_rows=100):
        """Execute a query with optional parameters and return the results."""
        if not self.engine:
            raise RuntimeError("Not connected to database")
            
        # Special handling for JDBC wrapper for AS400
        if hasattr(self.engine, 'execute_query') and self.db_type == DatabaseType.AS400:
            try:
                # For AS400 JDBC, we use the JDBC connection directly
                logger.debug(f"Executing query via JDBC: {query}")
                # Convert dict params to proper format for JDBC
                jdbc_params = {}
                if params and isinstance(params, dict):
                    for k, v in params.items():
                        # JDBC typically uses positional parameters or named with :
                        if ':' + k in query:
                            jdbc_params[':' + k] = v
                        else:
                            jdbc_params[k] = v
                
                # Execute using the JDBC executor
                return self.jdbc_execute_query(self.connection, query, jdbc_params, max_rows)
            except Exception as jdbc_err:
                logger.error(f"JDBC query execution error: {jdbc_err}")
                raise
            
        try:
            # Standard SQLAlchemy execution path
            # Check if query is a data modification query (not a SELECT)
            is_modification_query = False
            query_upper = query.strip().upper()
            if query_upper.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE')):
                is_modification_query = True
            
            # Use transaction for data modification queries
            with self.engine.begin() if is_modification_query else self.engine.connect() as conn:
                # Convert the query to SQLAlchemy text object
                sql_text = text(query)
                
                # Handle different parameter styles based on database type
                if params is not None:
                    # CASE 1: MySQL with %s placeholders
                    if self.db_type == DatabaseType.MYSQL and "%s" in query:
                        # MySQL needs special handling for %s placeholders
                        # Use direct string interpolation with proper quoting
                        param_values = []
                        
                        # Extract parameter values in the correct order
                        if isinstance(params, dict):
                            # Extract values for named parameters in expected order
                            if "schema" in params:
                                param_values.append(params["schema"])
                            if "table" in params:
                                param_values.append(params["table"])
                            if "column" in params:
                                param_values.append(params["column"])
                        elif isinstance(params, (list, tuple)):
                            param_values = list(params)
                        else:
                            # Single parameter
                            param_values = [params]
                        
                        # Safely replace each %s with properly quoted values
                        formatted_query = query
                        for value in param_values:
                            placeholder_pos = formatted_query.find("%s")
                            if placeholder_pos >= 0:
                                # Apply proper quoting based on value type
                                quoted_value = f"'{value}'" if isinstance(value, str) else str(value)
                                formatted_query = formatted_query[:placeholder_pos] + quoted_value + formatted_query[placeholder_pos+2:]
                        
                        # Execute with the safely interpolated query
                        sql_text = text(formatted_query)
                        result = conn.execute(sql_text)
                    
                    # CASE 2: PostgreSQL/Oracle with named parameters (:param)
                    elif self.db_type in [DatabaseType.POSTGRESQL, DatabaseType.ORACLE, DatabaseType.MSSQL] and any(f":{param}" in query for param in ["schema", "table", "column"]):
                        # These databases work well with SQLAlchemy's named parameter binding
                        result = conn.execute(sql_text, params)
                    
                    # CASE 3: SQLite with named parameters (:param)
                    elif self.db_type == DatabaseType.SQLITE and any(f":{param}" in query for param in ["schema", "table", "column"]):
                        # SQLite works with both named parameters and ? placeholders
                        result = conn.execute(sql_text, params)
                    
                    # CASE 4: AS400/DB2 with parameter markers
                    elif self.db_type == DatabaseType.AS400:
                        # AS400/DB2 uses ? or :name parameter markers depending on configuration
                        # If query contains ? placeholders and params is a list/tuple
                        if "?" in query and isinstance(params, (list, tuple)):
                            # Convert list to dict with positional keys for SQLAlchemy
                            positional_dict = {i: val for i, val in enumerate(params)}
                            result = conn.execute(sql_text, positional_dict)
                        else:
                            # Otherwise use standard parameter binding
                            result = conn.execute(sql_text, params)
                    
                    # CASE 5: Any other database or parameter style
                    else:
                        # Use standard SQLAlchemy parameter binding as fallback
                        result = conn.execute(sql_text, params)
                else:
                    # No parameters - execute the query as-is
                    result = conn.execute(sql_text)
                
                # Note: When using engine.begin(), the transaction is automatically committed
                # when the context manager exits. No need for explicit commit.
                
                # For SELECT queries
                if result.returns_rows:
                    # Get column names
                    columns = result.keys()
                    
                    # Convert rows to dictionaries
                    rows = []
                    for row in result.fetchmany(max_rows):
                        rows.append(dict(zip(columns, row)))
                    
                    return rows
                else:
                    # For UPDATE/INSERT/DELETE queries
                    return {"affected_rows": result.rowcount}
        
        except SQLAlchemyError as e:
            logger.error(f"Error executing query: {str(e)}")
            raise
    
    def execute_batch(self, queries):
        """Execute multiple queries in a batch."""
        if not self.engine:
            raise RuntimeError("Not connected to database")
        
        results = []
        try:
            with self.engine.begin() as conn:
                for query in queries:
                    result = conn.execute(text(query))
                    if result.returns_rows:
                        rows = [dict(zip(result.keys(), row)) for row in result.fetchall()]
                        results.append(rows)
                    else:
                        results.append({'affected_rows': result.rowcount})
            
            return results
        
        except SQLAlchemyError as e:
            logger.error(f"Error executing batch: {str(e)}")
            raise

def main():
    """Main function for testing database connections."""
    parser = argparse.ArgumentParser(description="Test database connections")
    parser.add_argument("--type", required=True, choices=[t.value for t in DatabaseType], help="Database type")
    parser.add_argument("--host", help="Database host")
    parser.add_argument("--port", help="Database port")
    parser.add_argument("--username", help="Database username")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--database", required=True, help="Database name/path")
    parser.add_argument("--list-tables", action="store_true", help="List all tables")
    parser.add_argument("--table", help="Table to examine")
    parser.add_argument("--query", help="SQL query to execute")
    
    args = parser.parse_args()
    
    # Create database connector
    connector = DatabaseConnector(
        db_type=DatabaseType(args.type),
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password
    )
    
    try:
        # Connect to database
        if not connector.connect():
            sys.exit(1)
        
        # List tables
        if args.list_tables:
            tables = connector.get_tables()
            print(f"Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table}")
        
        # Get table schema
        if args.table:
            schema = connector.get_table_schema(args.table)
            print(f"\nTable schema for {args.table}:")
            print(f"Primary keys: {schema['primary_keys']}")
            
            print("\nColumns:")
            for col, col_info in schema['columns'].items():
                pk_indicator = "*" if col_info['primary_key'] else " "
                nullable = "NULL" if col_info['nullable'] else "NOT NULL"
                print(f"  {pk_indicator} {col}: {col_info['type']} ({nullable})")
            
            if schema['foreign_keys']:
                print("\nForeign keys:")
                for fk in schema['foreign_keys']:
                    print(f"  {', '.join(fk['constrained_columns'])} -> {fk['referred_table']}({', '.join(fk['referred_columns'])})")
            
            if schema['indexes']:
                print("\nIndexes:")
                for idx in schema['indexes']:
                    unique = "UNIQUE " if idx['unique'] else ""
                    print(f"  {unique}INDEX {idx['name']} on ({', '.join(idx['columns'])})")
        
        # Execute query
        if args.query:
            results = connector.execute_query(args.query)
            print(f"\nQuery results:")
            print(json.dumps(results, indent=2, default=str))
    
    finally:
        # Disconnect
        connector.disconnect()

if __name__ == "__main__":
    main()
