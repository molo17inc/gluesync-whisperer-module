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

import jpype
import jaydebeapi
from typing import Dict, List, Optional, Any

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

def _normalize_identifier(value: Any) -> str:
    """Convert JDBC/JPype identifiers to clean Python strings."""
    if value is None:
        return ""
    text = str(value)
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        text = text[1:-1]
    return text

def _sanitize_sql(query: Any) -> Any:
    """Strip trailing semicolons/whitespace from SQL strings."""
    if not isinstance(query, str):
        return query
    cleaned = query.strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    return cleaned

def build_jdbc_connection_info(db_type, host, port, username, password, database):
    """
    Build JDBC connection information based on database type.
    
    Args:
        db_type: Database type (DatabaseType enum or string)
        host: Database host
        port: Database port
        username: Database username
        password: Database password
        database: Database name
        
    Returns:
        tuple: (jdbc_url, driver_class, properties)
    """
    properties = {
        "user": username,
        "password": password
    }
    
    if db_type == DatabaseType.MYSQL:
        jdbc_url = f"jdbc:mysql://{host}:{port}/{database}"
        driver_class = "com.mysql.cj.jdbc.Driver"
        
    elif db_type == DatabaseType.POSTGRESQL:
        jdbc_url = f"jdbc:postgresql://{host}:{port}/{database}"
        driver_class = "org.postgresql.Driver"
        # PostgreSQL-specific connection properties for better performance and reliability
        properties.update({
            "loginTimeout": "30",
            "connectTimeout": "10",
            "socketTimeout": "30",
            "tcpKeepAlive": "true",
            "prepareThreshold": "5",
            "preparedStatementCacheQueries": "256",
            "preparedStatementCacheSizeMiB": "5",
            "logUnclosedConnections": "true"
        })
        
    elif db_type == DatabaseType.SQLITE:
        jdbc_url = f"jdbc:sqlite:{database}"
        driver_class = "org.sqlite.JDBC"
        properties = {}  # No authentication for SQLite
        
    elif db_type == DatabaseType.MSSQL:
        jdbc_url = f"jdbc:sqlserver://{host}:{port};databaseName={database};trustServerCertificate=true;encrypt=true"
        driver_class = "com.microsoft.sqlserver.jdbc.SQLServerDriver"
        logger.info("Using JDBC for MS SQL Server connection")
        
    elif db_type == DatabaseType.ORACLE:
        jdbc_url = f"jdbc:oracle:thin:@{host}:{port}/{database}"
        driver_class = "oracle.jdbc.OracleDriver"
        
    elif db_type == DatabaseType.AS400:
        # Always use JDBC for AS400 - no fallbacks to ensure cross-platform compatibility
        logger.info("Using JDBC for AS400 connection")
        if database:
            jdbc_url = f"jdbc:as400://{host}/{database}"
        else:
            jdbc_url = f"jdbc:as400://{host}"
        driver_class = "com.ibm.as400.access.AS400JDBCDriver"
        # AS400-specific connection options
        properties.update({
            "prompt": "false",
            "naming": "system"
        })
            
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
        
    return jdbc_url, driver_class, properties

def get_jdbc_drivers_path():
    """Get the path to the JDBC driver JAR files.
    
    By default, these are expected to be in a 'jdbc_drivers' subdirectory of the current directory.
    """
    # Try to find in various locations
    possible_driver_paths = [
        # Relative to current directory
        os.path.join(os.getcwd(), 'jdbc_drivers'),
        # Relative to script directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'jdbc_drivers'),
        # In the application directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'jdbc_drivers'),
        # In the user's home directory
        os.path.join(os.path.expanduser('~'), '.jdbc_drivers'),
        # System locations
        '/opt/gluesync/jdbc_drivers',
        '/usr/local/share/jdbc_drivers',
    ]
    
    # Find the first path that exists and contains JAR files
    for path in possible_driver_paths:
        if os.path.exists(path) and any(f.endswith('.jar') for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
            # Get all JAR files in the directory
            jars = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.jar') and os.path.isfile(os.path.join(path, f))]
            logger.info(f"Found {len(jars)} JDBC driver JAR files in {path}")
            return jars
    
    # If no valid path is found
    logger.warning("No JDBC driver JAR files found in any of the expected locations")
    return []


class DatabaseConnector:
    """Class to handle database connections using direct JDBC."""
    
    def __init__(self, db_type, host=None, port=None, database=None, username=None, password=None):
        """Initialize database connection parameters."""
        self.db_type = db_type
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        # Initialize database-specific SQL statements based on type
        self.sql_statements = get_sql_statements(db_type)
    
    def is_connected(self):
        """Check if the connection is still valid and open."""
        if self.connection is None:
            return False
            
        try:
            # Try a simple query to check if the connection is still valid
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.warning(f"Connection check failed: {str(e)}")
            return False
    
    def connect(self):
        """Connect to the database using direct JDBC."""
        try:
            logger.info(f"Connecting to {self.db_type.value} database")
            
            # Get JDBC connection info
            jdbc_url, driver_class, properties = build_jdbc_connection_info(
                self.db_type, self.host, self.port, self.username, self.password, self.database
            )
            
            # Get JDBC driver JAR files
            jdbc_jars = get_jdbc_drivers_path()
            
            if not jdbc_jars:
                raise ValueError(f"No JDBC driver JAR files found for {self.db_type}")
            
            # Initialize JVM if not already started
            if not jpype.isJVMStarted():
                jpype.startJVM(jpype.getDefaultJVMPath(), '-Djava.class.path=' + os.pathsep.join(jdbc_jars))
                logger.info("JVM started for JDBC connections")
            
            # Create JDBC connection
            logger.info(f"Connecting to {jdbc_url} using {driver_class}")
            self.connection = jaydebeapi.connect(driver_class, jdbc_url, properties, jars=jdbc_jars)
            
            # For SQLite, set specific connection properties
            if self.db_type == DatabaseType.SQLITE:
                self.connection.jconn.setAutoCommit(False)  # Explicit transaction control
            
            # Define a connection wrapper class that provides necessary functionality
            class JdbcConnectionWrapper:
                def __init__(self, connection):
                    self.connection = connection
                    self.cursor = None
                    # Store direct reference to the JDBC connection for metadata access
                    self.jconn = connection.jconn if hasattr(connection, 'jconn') else None
                
                def connect(self):
                    """Return a connection context manager."""
                    return self
                
                def begin(self):
                    """Return a transaction context manager."""
                    return self
                
                def __enter__(self):
                    # Create cursor when entering context
                    self.cursor = self.connection.cursor()
                    return self
                
                def __exit__(self, exc_type, exc_val, exc_tb):
                    # Close cursor when exiting context
                    if self.cursor:
                        if exc_type is None:
                            # No exception - commit
                            self.connection.commit()
                        else:
                            # Exception occurred - rollback
                            self.connection.rollback()
                        self.cursor.close()
                        self.cursor = None
                
                def execute(self, query, params=None):
                    """Execute a SQL query with parameters."""
                    if params is None:
                        params = []
                    # Create cursor if needed
                    if self.cursor is None:
                        self.cursor = self.connection.cursor()
                    # Execute query
                    self.cursor.execute(query, params)
                    return self.cursor
            
            # Create a wrapper for the JDBC connection
            self.engine = JdbcConnectionWrapper(self.connection)
            
            # Store direct reference to JDBC connection for easier access
            self.jconn = self.connection.jconn if hasattr(self.connection, 'jconn') else None
            
            # Get database version
            self.version = self.get_database_version()
            
            logger.info(f"Connected to {self.db_type.value} database version {self.version}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            return False
            
    def get_database_version(self):
        """Get the database version using database-specific SQL statements."""
        try:
            if not self.connection:
                return "unknown"
                
            # Get version SQL statement from our specialized SQL statements
            version_query = self.sql_statements.get_version_statement()
            
            # Execute the version query with JDBC
            cursor = self.connection.cursor()
            cursor.execute(version_query)
            result = cursor.fetchall()
            
            if result and len(result) > 0:
                # Get column names
                column_names = [desc[0] for desc in cursor.description]
                # Convert to dict for consistent processing
                row_dict = dict(zip(column_names, result[0]))
                
                # Different databases return version in different column names
                if 'VERSION()' in row_dict:
                    version = row_dict['VERSION()']
                elif 'version' in row_dict:
                    version = row_dict['version']
                elif 'VERSION' in row_dict:
                    version = row_dict['VERSION']
                elif 'BANNER' in row_dict: # Oracle specific
                    version = row_dict['BANNER']
                elif 'version' in row_dict and self.db_type == DatabaseType.POSTGRESQL:
                    # PostgreSQL version() returns "PostgreSQL 15.3 on x86_64-pc-linux-gnu, compiled by gcc..."
                    version = str(row_dict['version']).split(' ')[1]  # Extract version number
                else:
                    # Return first column's value if we can't identify a specific version column
                    version = result[0][0]
                
                cursor.close()
                return version
            
            cursor.close()
            return "unknown"
        except Exception as e:
            logger.warning(f"Error getting database version: {str(e)}")
            return "unknown"
    
    def disconnect(self):
        """Disconnect from the database."""
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
                self.engine = None
                logger.info("Disconnected from database")
        except Exception as e:
            logger.warning(f"Error during database disconnect: {str(e)}")
    
    def get_tables(self, schema=None):
        """Get a list of all tables in the database using JDBC."""
        if not self.connection:
            raise RuntimeError("Not connected to database")
        
        try:
            # Use specialized SQL statements specific to the database type
            if schema is None and self.db_type != DatabaseType.SQLITE:
                # Try to get schema from connection
                schema = self.database
            
            if self.db_type == DatabaseType.SQLITE:
                # For SQLite, which doesn't have schemas in the traditional sense
                query = self.sql_statements.get_tables_statement()
                params = []
            else:
                # For databases with schemas
                query = self.sql_statements.get_tables_statement(schema)
                # Convert named parameters to positional if needed
                if ':schema' in query:
                    query = query.replace(':schema', '?')
                    params = [schema]
                elif '?' in query:
                    params = [schema]
                else:
                    params = []
            
            # Execute query using JDBC
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            
            # Get column names
            # Convert Java String objects to Python strings before calling upper()
            column_names = [str(desc[0]).upper() for desc in cursor.description] 
            
            # Process results
            tables = []
            if result:
                # Map results to dictionaries
                dict_results = [dict(zip(column_names, row)) for row in result]
                
                # Extract table names based on available columns
                if dict_results and len(dict_results) > 0:
                    if 'TABLE_NAME' in dict_results[0]:
                        tables = [str(row['TABLE_NAME']) for row in dict_results]
                    elif 'TABLENAME' in dict_results[0]:
                        tables = [str(row['TABLENAME']) for row in dict_results]
                    elif len(dict_results[0]) == 1:  # One-column result
                        tables = [str(list(row.values())[0]) for row in dict_results]
                    else:
                        # As a fallback, use the first column
                        tables = [str(row[list(row.keys())[0]]) for row in dict_results]
                        
                # Ensure all table names are Python strings
                tables = [str(table) for table in tables]
            
            cursor.close()
            
            logger.info(f"Found {len(tables)} tables in schema {schema}")
            for table in tables:
                logger.debug(f" - {table}")
            
            return tables
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            # Fallback to JDBC metadata
            try:
                # Use JDBC DatabaseMetaData to get tables
                metadata = self.connection.jconn.getMetaData()
                catalog = None  # Usually null in JDBC
                schema_pattern = schema if schema else "%"
                table_name_pattern = "%"  # All tables
                table_types = ["TABLE"]  # Only regular tables, not views
                
                # Get result set with table info
                rs = metadata.getTables(catalog, schema_pattern, table_name_pattern, table_types)
                
                # Extract table names
                tables = []
                while rs.next():
                    # Convert Java string to Python string
                    table_name = str(rs.getString("TABLE_NAME"))
                    tables.append(table_name)
                
                rs.close()
                logger.info(f"Using JDBC metadata, found {len(tables)} tables")
                
                # Double-check that all table names are Python strings
                tables = [str(table) for table in tables]
                logger.debug(f"Table names: {tables}")
                return tables
            except Exception as jdbc_err:
                logger.error(f"Error getting tables via JDBC metadata: {str(jdbc_err)}")
                return []
            
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
                    # Replace the %s with concrete values directly using string formatting
                    import re
                    # Extract the SQL parts before and after WHERE clause
                    match = re.search(r'(.*WHERE\s+C\.TABLE_SCHEMA\s*=\s*)%s(\s*AND\s+C\.TABLE_NAME\s*=\s*)%s(.*)', query, re.DOTALL | re.IGNORECASE)
                    
                    if match:
                        part1, part2, part3 = match.groups()
                        # Create a query with literal values
                        formatted_query = f"{part1}'{schema}'{part2}'{table_name}'{part3}"
                        column_results = self.execute_query(formatted_query)
                    else:
                        # Fallback to JDBC metadata if we can't parse the query
                        logger.warning("Could not parse MySQL query pattern, falling back to JDBC metadata")
                        # Use JDBC DatabaseMetaData to get columns
                        try:
                            metadata = self.connection.jconn.getMetaData()
                            catalog = None  # Usually null in JDBC
                            schema_pattern = schema
                            table_name_pattern = table_name
                            column_name_pattern = "%"  # All columns
                            
                            # Get result set with column info
                            rs = metadata.getColumns(catalog, schema_pattern, table_name_pattern, column_name_pattern)
                            
                            # Extract column information
                            column_results = []
                            while rs.next():
                                column_info = {
                                    'column_name': rs.getString("COLUMN_NAME"),
                                    'data_type': rs.getString("TYPE_NAME"),
                                    'is_nullable': rs.getString("IS_NULLABLE") == "YES",
                                    'column_default': rs.getString("COLUMN_DEF"),
                                    'is_primary_key': False,  # Will be set later
                                    'extra': ''
                                }
                                column_results.append(column_info)
                            
                            rs.close()
                            return column_results
                        except Exception as jdbc_err:
                            logger.error(f"Error getting columns via JDBC metadata: {str(jdbc_err)}")
                            return []
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
                    name_raw = col_dict.get('column_name') or next((col_dict[k] for k in col_dict if 'column_name' in k.lower()), '')
                    name = _normalize_identifier(name_raw)
                    data_type_raw = col_dict.get('data_type') or next((col_dict[k] for k in col_dict if 'data_type' in k.lower()), '')
                    data_type = _normalize_identifier(data_type_raw)
                    is_nullable = col_dict.get('is_nullable', 'YES') in ('YES', 'yes', 'Y', 'y', True, 1)
                    is_primary = col_dict.get('is_primary_key', 0) in (1, True, 'YES', 'yes', 'Y', 'y')
                    default_raw = col_dict.get('column_default') or col_dict.get('default')
                    default_val = _normalize_identifier(default_raw) if isinstance(default_raw, str) else default_raw
                    extra = col_dict.get('extra', '')
                    
                    # For MySQL, examine COLUMN_KEY and EXTRA for primary key and auto_increment
                    if self.db_type == DatabaseType.MYSQL:
                        if col_dict.get('column_key') == 'PRI':
                            is_primary = True
                        extra = col_dict.get('extra', '')
                    
                    # For PostgreSQL, check for identity columns and specific data types
                    if self.db_type == DatabaseType.POSTGRESQL:
                        if 'identity' in str(default_val).lower():
                            extra = 'auto_increment'
                        # Handle PostgreSQL-specific data types
                        if data_type.lower() in ['json', 'jsonb']:
                            extra = 'json_type'
                        elif data_type.lower() in ['array', 'text[]', 'integer[]', 'varchar[]']:
                            extra = 'array_type'
                        elif data_type.lower() in ['uuid']:
                            extra = 'uuid_type'
                        elif data_type.lower() in ['timestamp with time zone', 'timestamptz']:
                            extra = 'timestamp_with_timezone'
                        elif data_type.lower() in ['timestamp without time zone', 'timestamp']:
                            extra = 'timestamp_without_timezone'
                        
                    # For Oracle, check for identity columns and specific data types
                    if self.db_type == DatabaseType.ORACLE:
                        if col_dict.get('is_identity', 0) in (1, True, 'YES', 'yes', 'Y', 'y'):
                            extra = 'auto_increment'
                        # Handle Oracle-specific data types
                        if data_type.lower() in ['number', 'numeric']:
                            if col_dict.get('data_scale', 0) == 0:
                                extra = 'integer_type'
                        elif data_type.lower() in ['varchar2', 'nvarchar2']:
                            extra = 'varchar2_type'
                        elif data_type.lower() in ['timestamp', 'timestamp with time zone', 'timestamp with local time zone']:
                            extra = 'oracle_timestamp'
                        elif data_type.lower() in ['clob', 'nclob']:
                            extra = 'oracle_clob'
                        elif data_type.lower() in ['blob']:
                            extra = 'oracle_blob'
                        elif data_type.lower() in ['raw', 'long raw']:
                            extra = 'oracle_raw'
                    
                    # Store normalized column info
                    columns[name] = {
                        'name': name,
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
                            pk_col = _normalize_identifier(pk_col)
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
                
                # If still no primary keys, try JDBC metadata as a last resort
                if not primary_keys:
                    try:
                        # Use JDBC DatabaseMetaData to get primary keys
                        metadata = self.connection.jconn.getMetaData()
                        catalog = None  # Usually null in JDBC
                        schema_pattern = schema
                        table_name_pattern = table_name
                        
                        # Get primary key information
                        rs = metadata.getPrimaryKeys(catalog, schema_pattern, table_name_pattern)
                        
                        # Extract primary key column names
                        while rs.next():
                            pk_column = _normalize_identifier(rs.getString("COLUMN_NAME"))
                            primary_keys.append(pk_column)
                            # Update column info to mark as primary key
                            if pk_column in columns:
                                columns[pk_column]['primary_key'] = True
                        
                        rs.close()
                        logger.info(f"Using JDBC metadata, found {len(primary_keys)} primary keys")
                    except Exception as e3:
                        logger.warning(f"Error getting primary keys via JDBC metadata: {str(e3)}")
            
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
                        # Special handling for JDBC MS SQL Server which requires ? placeholders
                        is_jdbc_mssql = (self.db_type == DatabaseType.MSSQL and hasattr(self, 'connection'))
                        
                        if is_jdbc_mssql:
                            # For JDBC MS SQL Server, keep ? placeholders and use positional parameters
                            positional_params = []
                            if schema:
                                positional_params.append(schema)
                            if table_name:
                                positional_params.append(table_name)
                            
                            logger.debug(f"Using MS SQL Server JDBC with positional parameters: {positional_params}")
                            fk_results = self.execute_query(query, params=positional_params)
                        else:
                            # For other databases, convert to named parameters
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
                # Fallback to JDBC metadata
                try:
                    # Use JDBC DatabaseMetaData to get foreign keys
                    metadata = self.connection.jconn.getMetaData()
                    catalog = None  # Usually null in JDBC
                    schema_pattern = schema
                    table_name_pattern = table_name
                    
                    # Get imported keys (foreign keys in this table)
                    rs = metadata.getImportedKeys(catalog, schema_pattern, table_name_pattern)
                    
                    # Process foreign key information
                    fk_dict = {}
                    while rs.next():
                        fk_name = rs.getString("FK_NAME")
                        fk_column = rs.getString("FKCOLUMN_NAME")
                        pk_table = rs.getString("PKTABLE_NAME")
                        pk_column = rs.getString("PKCOLUMN_NAME")
                        
                        if fk_name not in fk_dict:
                            fk_dict[fk_name] = {
                                'constrained_columns': [],
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
                    
                    logger.info(f"Retrieved {len(foreign_keys)} foreign keys for table {table_name} using JDBC metadata")
                except Exception as jdbc_err:
                    logger.warning(f"Error getting foreign keys via JDBC metadata: {str(jdbc_err)}")
            
            # Get indexes using JDBC metadata
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
                else:
                    # Use JDBC metadata as fallback for other database types
                    try:
                        # Get metadata from JDBC connection
                        metadata = self.connection.jconn.getMetaData()
                        catalog = None  # Usually null in JDBC
                        schema_pattern = schema
                        table_name_pattern = table_name
                        
                        # Get index information
                        rs = metadata.getIndexInfo(catalog, schema_pattern, table_name_pattern, False, True)
                        
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
                        
                        # Add indexes to our list
                        for idx in index_dict.values():
                            if idx['columns']:
                                indexes.append(idx)
                                
                        logger.info(f"Retrieved {len(indexes)} indexes for table {table_name} using JDBC metadata")
                    except Exception as jdbc_err:
                        logger.warning(f"Error getting indexes via JDBC metadata: {str(jdbc_err)}")
                        # If this fails, we'll have empty indexes
                        indexes = []
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
            # Fallback to JDBC metadata as a last resort
            logger.info("Falling back to JDBC metadata for schema info")
            
            try:
                # Get columns using JDBC metadata
                columns = {}
                metadata = self.connection.jconn.getMetaData()
                catalog = None  # Usually null in JDBC
                schema_pattern = schema
                table_name_pattern = table_name
                column_name_pattern = "%"  # All columns
                
                # Get column information
                rs = metadata.getColumns(catalog, schema_pattern, table_name_pattern, column_name_pattern)
                
                while rs.next():
                    column_name = rs.getString("COLUMN_NAME")
                    type_name = rs.getString("TYPE_NAME")
                    nullable = rs.getInt("NULLABLE") != 0  # 0 means not nullable
                    default_value = rs.getString("COLUMN_DEF")
                    
                    columns[column_name] = {
                        'type': type_name,
                        'nullable': nullable,
                        'default': default_value,
                        'primary_key': False,  # Will be updated below
                        'extra': ''
                    }
                
                rs.close()
                
                # Get primary keys
                primary_keys = []
                rs = metadata.getPrimaryKeys(catalog, schema_pattern, table_name_pattern)
                
                while rs.next():
                    pk_column = rs.getString("COLUMN_NAME")
                    primary_keys.append(pk_column)
                    if pk_column in columns:
                        columns[pk_column]['primary_key'] = True
                
                rs.close()
                
                # Get foreign keys
                foreign_keys = []
                rs = metadata.getImportedKeys(catalog, schema_pattern, table_name_pattern)
                
                # Process foreign key information
                fk_dict = {}
                while rs.next():
                    fk_name = rs.getString("FK_NAME")
                    fk_column = rs.getString("FKCOLUMN_NAME")
                    pk_table = rs.getString("PKTABLE_NAME")
                    pk_column = rs.getString("PKCOLUMN_NAME")
                    
                    if fk_name not in fk_dict:
                        fk_dict[fk_name] = {
                            'constrained_columns': [],
                            'referred_table': pk_table,
                            'referred_columns': []
                        }
                    
                    if fk_column and fk_column not in fk_dict[fk_name]['constrained_columns']:
                        fk_dict[fk_name]['constrained_columns'].append(fk_column)
                    
                    if pk_column and pk_column not in fk_dict[fk_name]['referred_columns']:
                        fk_dict[fk_name]['referred_columns'].append(pk_column)
                
                rs.close()
                
                # Add foreign keys to our list
                for fk in fk_dict.values():
                    if fk['constrained_columns'] and fk['referred_columns']:
                        foreign_keys.append(fk)
                
                # Get indexes
                indexes = []
                try:
                    rs = metadata.getIndexInfo(catalog, schema_pattern, table_name_pattern, False, True)
                    
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
                    
                    rs.close()
                    
                    # Add indexes to our list
                    for idx in index_dict.values():
                        if idx['columns']:
                            indexes.append(idx)
                except Exception as idx_err:
                    logger.warning(f"Fallback method: Error getting indexes via JDBC: {str(idx_err)}")
                
                logger.info(f"Retrieved schema for table {table_name} using JDBC metadata")
            except Exception as jdbc_err:
                logger.error(f"Error getting schema via JDBC metadata: {str(jdbc_err)}")
                # Return empty schema structure if all else fails
                columns = {}
                primary_keys = []
                foreign_keys = []
                indexes = []
            
            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys,
                'indexes': indexes
            }
    def get_schemas(self):
        """Get all schemas for the current database connection using JDBC."""
        if not self.connection:
            raise RuntimeError("Not connected to database")
            
        try:
            logger.info(f"Getting schemas via JDBC for {self.db_type.value}")
            schemas = []
            
            # Use JDBC metadata to get schemas
            metadata = self.connection.jconn.getMetaData()
            
            # Different databases handle schemas differently
            if self.db_type == DatabaseType.MYSQL:
                # For MySQL, databases are essentially schemas
                rs = metadata.getCatalogs()
                while rs.next():
                    catalog = rs.getString("TABLE_CAT")
                    if catalog and catalog not in ["information_schema", "mysql", "performance_schema", "sys"]:
                        schemas.append(catalog)
                rs.close()
                
            elif self.db_type == DatabaseType.MSSQL:
                # For MS SQL Server, get actual schemas
                logger.info("Getting MS SQL Server schemas via JDBC metadata")
                
                # Define roles to filter out - these are not actual schemas
                roles_to_filter = [
                    "db_accessadmin", "db_backupoperator", "db_datareader", "db_datawriter",
                    "db_ddladmin", "db_denydatareader", "db_denydatawriter", "db_owner",
                    "db_securityadmin", "guest"
                ]
                
                rs = metadata.getSchemas()
                while rs.next():
                    schema = rs.getString("TABLE_SCHEM")
                    # Convert Java String to Python string
                    schema_str = str(schema) if schema else None
                    
                    # Only include actual schemas, not roles
                    if schema_str and schema_str not in roles_to_filter:
                        schemas.append(schema_str)
                        logger.debug(f"Found schema: {schema_str}")
                rs.close()
                
                # If no schemas found, return the default 'dbo' schema
                if not schemas:
                    logger.info("No schemas found, adding default 'dbo' schema")
                    schemas.append("dbo")
                    
                logger.info(f"Retrieved {len(schemas)} schemas from MS SQL Server: {schemas}")
                    
            elif self.db_type == DatabaseType.POSTGRESQL:
                # For PostgreSQL, get schemas
                rs = metadata.getSchemas()
                while rs.next():
                    schema = rs.getString("TABLE_SCHEM")
                    if schema and schema not in ["information_schema", "pg_catalog", "pg_toast"]:
                        schemas.append(schema)
                rs.close()
                
                # If no custom schemas found, return the default 'public' schema
                if not schemas:
                    schemas.append("public")
                    
            elif self.db_type == DatabaseType.ORACLE:
                # For Oracle, get schemas (usually user schemas)
                rs = metadata.getSchemas()
                while rs.next():
                    schema = rs.getString("TABLE_SCHEM")
                    if schema:
                        schemas.append(schema)
                rs.close()
                
            elif self.db_type == DatabaseType.SQLITE:
                # SQLite doesn't have traditional schemas
                schemas.append("main")
                
            elif self.db_type == DatabaseType.AS400:
                # For AS400, get schemas
                rs = metadata.getSchemas()
                while rs.next():
                    schema = rs.getString("TABLE_SCHEM")
                    # Convert Java String to Python string
                    schema_str = str(schema) if schema else None
                    if schema_str and schema_str not in ["QSYS", "QSYS2", "SYSIBM", "SYSCAT", "SYSFUN", "SYSPROC", "SYSTOOLS"]:
                        schemas.append(schema_str)
                rs.close()
                
                # If no schemas found, use the database name or username as default
                if not schemas:
                    if self.database:
                        schemas.append(self.database)
                    elif self.username:
                        schemas.append(self.username.upper())
                    else:
                        schemas.append("QGPL")  # Default AS400 schema
            
            logger.info(f"Retrieved {len(schemas)} schemas using JDBC metadata")
            # Ensure all schemas are Python strings
            return [str(schema) for schema in schemas]
            
        except Exception as e:
            logger.error(f"Error getting schemas via JDBC: {str(e)}")
            # Return a default schema based on database type
            if self.db_type == DatabaseType.MYSQL:
                return [self.database] if self.database else ["mysql"]
            elif self.db_type == DatabaseType.MSSQL:
                return ["dbo"]
            elif self.db_type == DatabaseType.POSTGRESQL:
                return ["public"]
            elif self.db_type == DatabaseType.SQLITE:
                return ["main"]
            elif self.db_type == DatabaseType.AS400:
                return [self.database] if self.database else ["QGPL"]
            elif self.db_type == DatabaseType.ORACLE:
                return [self.username.upper()] if self.username else ["SYSTEM"]
            else:
                return ["default"]
    
    def execute_query(self, query, params=None, max_rows=100):
        """Execute a query with optional parameters and return the results using JDBC."""
        if not self.connection:
            raise RuntimeError("Not connected to database")
        
        try:
            query = _sanitize_sql(query)
            logger.debug(f"Executing query via JDBC for {self.db_type.value}: {query}")
            
            # Process parameters
            jdbc_params = []
            
            if params:
                # Convert parameters to the format needed by JDBC
                if isinstance(params, dict):
                    # Handle named parameters
                    if ':' in query or '{' in query:
                        # Replace named parameters with ? for JDBC prepared statements
                        modified_query = query
                        for k, v in params.items():
                            param_placeholder = f":{k}"
                            if param_placeholder in modified_query:
                                modified_query = modified_query.replace(param_placeholder, '?')
                                jdbc_params.append(v)
                            elif f"{{{k}}}" in modified_query:
                                modified_query = modified_query.replace(f"{{{k}}}", '?')
                                jdbc_params.append(v)
                        
                        # Update query to use positional parameters
                        query = modified_query
                    else:
                        # For SQL Server, convert named parameters to positional
                        if '?' in query and self.db_type == DatabaseType.MSSQL:
                            # For schema and table_name parameters (common case)
                            if 'schema' in params and 'table_name' in params:
                                jdbc_params = [params.get('schema'), params.get('table_name')]
                            else:
                                # Best-effort conversion (may not be in correct order)
                                jdbc_params = list(params.values())
                        else:
                            # Fallback: convert all values to a list
                            jdbc_params = list(params.values())
                else:
                    # Already a list or tuple, use as-is
                    jdbc_params = params
                    
            # Create cursor and execute
            cursor = self.connection.cursor()
            
            # For debugging in MS SQL Server
            if self.db_type == DatabaseType.MSSQL:
                logger.debug(f"JDBC params for query: {jdbc_params}")
            
            try:
                # Execute the query with parameters
                cursor.execute(query, jdbc_params)
                
                # Check if this is a SELECT query or a DML query (INSERT, UPDATE, DELETE)
                is_select_query = query.strip().upper().startswith("SELECT")
                
                if is_select_query and cursor.description:
                    try:
                        # Fetch results (limited by max_rows)
                        result_set = cursor.fetchmany(max_rows) if max_rows else cursor.fetchall()
                        
                        # Get column names from cursor description and ensure they are Python strings
                        column_names = []
                        if cursor.description:
                            for desc in cursor.description:
                                # Convert Java String to Python string or use a default name
                                col_name = str(desc[0]) if desc[0] else f'column_{len(column_names)}'
                                column_names.append(col_name)
                        
                        # Convert results to dictionaries
                        results = []
                        for row in result_set:
                            row_dict = {}
                            for i, col_name in enumerate(column_names):
                                # Convert Java objects to Python types
                                row_dict[col_name] = str(row[i]) if row[i] is not None else None
                            results.append(row_dict)
                        
                        return results
                    except Exception as e:
                        logger.warning(f"Error fetching results: {str(e)}")
                        # Return empty results if fetching fails
                        return []
                else:
                    # For INSERT, UPDATE, DELETE queries, just return an empty list
                    # No need to fetch results for these operations
                    return []
            except Exception as e:
                logger.error(f"Error executing query: {str(e)}")
                if cursor:
                    cursor.close()
                raise
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise
    
    def getMetaData(self):
        """Get database metadata, delegating to the JDBC connection."""
        if not self.connection:
            self.connect()
        return self.connection.conn.getMetaData()
        
    def get_engine(self, **kwargs):
        """Get the database engine (JDBC connection).
        
        This method is provided for compatibility with SQLAlchemy-style interfaces.
        
        Args:
            **kwargs: Optional connection parameters (host, port, database, username, password)
            
        Returns:
            The JDBC connection object
            
        Note:
            In this JDBC implementation, we return the connection itself as the "engine".
        """
        # If connection parameters are provided, create a new connection with those parameters
        if kwargs:
            # Create a new DatabaseConnector with the provided parameters
            db_type = kwargs.get('db_type', self.db_type)
            host = kwargs.get('host', self.host)
            port = kwargs.get('port', self.port)
            database = kwargs.get('database', self.database)
            username = kwargs.get('username', self.username)
            password = kwargs.get('password', self.password)
            
            # Create a new connector with the provided parameters
            connector = DatabaseConnector(
                db_type=db_type,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password
            )
            connector.connect()
            return connector
        
        return self.connection

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
            logger.info(f"Found {len(tables)} tables:")
            for table in tables:
                logger.info(f"  - {table}")
        
        # Get table schema
        if args.table:
            schema = connector.get_table_schema(args.table)
            logger.info(f"\nTable schema for {args.table}:")
            logger.info(f"Primary keys: {schema['primary_keys']}")
            
            logger.info("\nColumns:")
            for col, col_info in schema['columns'].items():
                pk_indicator = "*" if col_info['primary_key'] else " "
                nullable = "NULL" if col_info['nullable'] else "NOT NULL"
                logger.info(f"  {pk_indicator} {col}: {col_info['type']} ({nullable})")
            
            if schema['foreign_keys']:
                logger.info("\nForeign keys:")
                for fk in schema['foreign_keys']:
                    logger.info(f"  {', '.join(fk['constrained_columns'])} -> {fk['referred_table']}({', '.join(fk['referred_columns'])})")
            
            if schema['indexes']:
                logger.info("\nIndexes:")
                for idx in schema['indexes']:
                    unique = "UNIQUE " if idx['unique'] else ""
                    logger.info(f"  {unique}INDEX {idx['name']} on ({', '.join(idx['columns'])})")
        
        # # Execute query
        # if args.query:
        #     results = connector.execute_query(args.query)
        #     logger.info(f"\nQuery results:")    
        #     logger.info(json.dumps(results, indent=2, default=str))
    
    finally:
        # Disconnect
        connector.disconnect()

if __name__ == "__main__":
    main()
