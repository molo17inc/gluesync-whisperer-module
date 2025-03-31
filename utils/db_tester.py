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
import jaydebeapi
import jpype

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# This function is no longer needed as we're directly building JDBC URLs in the test_connection function

def test_connection(db_type, host, port, username, password, database):
    """Test a database connection using JDBC."""
    try:
        # Determine JDBC driver class and URL based on database type
        if db_type == DatabaseType.MYSQL:
            jdbc_url = f"jdbc:mysql://{host}:{port}/{database}"
            driver_class = "com.mysql.cj.jdbc.Driver"
        elif db_type == DatabaseType.POSTGRESQL:
            jdbc_url = f"jdbc:postgresql://{host}:{port}/{database}"
            driver_class = "org.postgresql.Driver"
        elif db_type == DatabaseType.SQLITE:
            jdbc_url = f"jdbc:sqlite:{database}"
            driver_class = "org.sqlite.JDBC"
            username = None
            password = None
        elif db_type == DatabaseType.MSSQL:
            jdbc_url = f"jdbc:sqlserver://{host}:{port};databaseName={database};trustServerCertificate=true;encrypt=true"
            driver_class = "com.microsoft.sqlserver.jdbc.SQLServerDriver"
        elif db_type == DatabaseType.ORACLE:
            jdbc_url = f"jdbc:oracle:thin:@{host}:{port}/{database}"
            driver_class = "oracle.jdbc.OracleDriver"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        # Create connection properties
        properties = {}
        if username and password:
            properties = {"user": username, "password": password}
        
        # Find JDBC driver JAR files
        jdbc_driver_dir = os.path.abspath("./jdbc_drivers")
        if os.path.exists(jdbc_driver_dir):
            # Initialize JVM if not already started
            if not jpype.isJVMStarted():
                # Try to find JVM path
                jvm_paths = [
                    "/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home/lib/libjli.dylib",
                    "/Library/Java/JavaVirtualMachines/temurin-8.jdk/Contents/Home/jre/lib/jli/libjli.dylib",
                    "/Library/Java/JavaVirtualMachines/jdk1.8.0_102.jdk/Contents/Home/jre/lib/jli/libjli.dylib"
                ]
                
                jvm_started = False
                for jvm_path in jvm_paths:
                    if os.path.exists(jvm_path):
                        try:
                            jpype.startJVM(jvm_path, f"-Djava.class.path={jdbc_driver_dir}/*")
                            jvm_started = True
                            break
                        except Exception as jvm_err:
                            logger.warning(f"Failed to start JVM with {jvm_path}: {str(jvm_err)}")
                
                if not jvm_started:
                    raise RuntimeError("Could not start JVM with any available paths")
        
        # Create JDBC connection
        conn = jaydebeapi.connect(driver_class, jdbc_url, properties)
        
        # Test connection with a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        
        logger.info("Connection successful!")
        return conn
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        return None

def get_tables(conn):
    """Get all tables in the database using JDBC metadata."""
    try:
        metadata = conn.jconn.getMetaData()
        catalog = None  # Usually null in JDBC
        schema_pattern = None  # All schemas
        table_name_pattern = "%"  # All tables
        table_types = ["TABLE"]  # Only regular tables
        
        # Get table information
        rs = metadata.getTables(catalog, schema_pattern, table_name_pattern, table_types)
        
        tables = []
        while rs.next():
            table_name = rs.getString("TABLE_NAME")
            tables.append(table_name)
        
        rs.close()
        
        logger.info(f"Found {len(tables)} tables:")
        for table in tables:
            logger.info(f" - {table}")
        
        return tables
    except Exception as e:
        logger.error(f"Error getting tables: {str(e)}")
        return []

def get_table_schema(conn, table_name):
    """Get the schema of a table using JDBC metadata."""
    try:
        metadata = conn.jconn.getMetaData()
        catalog = None  # Usually null in JDBC
        schema_pattern = None  # All schemas
        column_name_pattern = "%"  # All columns
        
        # Get column information
        rs = metadata.getColumns(catalog, schema_pattern, table_name, column_name_pattern)
        
        columns = []
        while rs.next():
            column_name = rs.getString("COLUMN_NAME")
            type_name = rs.getString("TYPE_NAME")
            nullable = rs.getInt("NULLABLE") != 0  # 0 means not nullable
            
            columns.append({
                'name': column_name,
                'type': type_name,
                'nullable': nullable
            })
        
        rs.close()
        
        logger.info(f"Table {table_name} has {len(columns)} columns:")
        for column in columns:
            logger.info(f" - {column['name']}: {column['type']} (nullable: {column['nullable']})")
        
        # Get primary keys
        rs = metadata.getPrimaryKeys(catalog, schema_pattern, table_name)
        
        primary_keys = []
        while rs.next():
            pk_column = rs.getString("COLUMN_NAME")
            primary_keys.append(pk_column)
        
        rs.close()
        
        if primary_keys:
            logger.info(f"Primary keys: {', '.join(primary_keys)}")
        else:
            logger.info("No primary keys found")
            
        return {
            'columns': columns,
            'primary_keys': primary_keys
        }
    except Exception as e:
        logger.error(f"Error getting table schema: {str(e)}")
        return {'columns': [], 'primary_keys': []}

def main():
    parser = argparse.ArgumentParser(description="Test database connections and explore schema")
    parser.add_argument("--type", required=True, choices=[t.value for t in DatabaseType], help="Database type")
    parser.add_argument("--host", help="Database host")
    parser.add_argument("--port", help="Database port")
    parser.add_argument("--username", help="Database username")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--database", required=True, help="Database name/path")
    parser.add_argument("--list-tables", action="store_true", help="List all tables")
    parser.add_argument("--table", help="Table to examine")
    
    args = parser.parse_args()
    
    # Get database type
    db_type = DatabaseType(args.type)
    
    # Test connection
    logger.info(f"Testing connection to {args.type} database...")
    conn = test_connection(
        db_type=db_type,
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        database=args.database
    )
    
    if not conn:
        sys.exit(1)
    
    # List tables if requested
    if args.list_tables:
        tables = get_tables(conn)
    
    # Examine table if specified
    if args.table:
        get_table_schema(conn, args.table)

if __name__ == "__main__":
    main()
