#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is dual-licensed under the following licenses:
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
import os
import sys
import jpype
import jpype.imports
from jpype.types import *
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Mapping of database types to JDBC driver class names and JAR files
JDBC_DRIVERS = {
    DatabaseType.MYSQL: {
        "driver_class": "com.mysql.cj.jdbc.Driver",
        "jar_file": "mysql-connector-j-9.2.0.jar",
        "url_template": "jdbc:mysql://{host}:{port}/{database}",
    },
    DatabaseType.POSTGRESQL: {
        "driver_class": "org.postgresql.Driver",
        "jar_file": "postgresql-42.7.5.jar",
        "url_template": "jdbc:postgresql://{host}:{port}/{database}",
    },
    DatabaseType.SQLITE: {
        "driver_class": "org.sqlite.JDBC",
        "jar_file": "sqlite-jdbc-3.47.1.0.jar",
        "url_template": "jdbc:sqlite:{database}",
    },
    DatabaseType.MSSQL: {
        "driver_class": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "jar_file": "mssql-jdbc-12.2.0.jre8.jar",
        "url_template": "jdbc:sqlserver://{host}:{port};databaseName={database}",
    },
    DatabaseType.ORACLE: {
        "driver_class": "oracle.jdbc.driver.OracleDriver",
        "jar_file": "ojdbc8.jar",
        "url_template": "jdbc:oracle:thin:@{host}:{port}:{database}",
    },
}

class JDBCConnection:
    """Class to handle JDBC connections using JPype."""
    
    def __init__(self, db_type, host=None, port=None, database=None, username=None, password=None):
        """Initialize JDBC connection parameters."""
        self.db_type = db_type
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self.driver_info = JDBC_DRIVERS.get(db_type)
        
        if not self.driver_info:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def connect(self):
        """Connect to the database using JDBC."""
        if not jpype.isJVMStarted():
            # Find all JAR files in the jdbc_drivers directory
            jdbc_dir = Path(__file__).parent.parent / "jdbc_drivers"
            jar_files = [str(jdbc_dir / jar) for jar in os.listdir(jdbc_dir) if jar.endswith(".jar")]
            
            # Start JVM with all JAR files in the classpath
            classpath = os.pathsep.join(jar_files)
            
            # Try to find the Java installation
            java_home = os.environ.get("JAVA_HOME")
            jvm_path = None
            
            # If JAVA_HOME is set, try to use it
            if java_home:
                possible_jvm_paths = [
                    os.path.join(java_home, "jre", "lib", "server", "libjvm.dylib"),  # Oracle JDK
                    os.path.join(java_home, "lib", "server", "libjvm.dylib"),         # JRE
                    os.path.join(java_home, "lib", "libjli.dylib"),                   # Mac specific
                ]
                
                for path in possible_jvm_paths:
                    if os.path.exists(path):
                        jvm_path = path
                        break
            
            # If we couldn't find it using JAVA_HOME, try common locations
            if not jvm_path:
                # Get Java installation from 'java -XshowSettings:properties -version' output
                try:
                    import subprocess
                    output = subprocess.check_output(
                        ["java", "-XshowSettings:properties", "-version"], 
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    for line in output.splitlines():
                        if "java.home" in line:
                            java_path = line.split("=", 1)[1].strip()
                            possible_jvm_paths = [
                                os.path.join(java_path, "lib", "server", "libjvm.dylib"),  # Unix
                                os.path.join(java_path, "jre", "lib", "server", "libjvm.dylib"),  # Oracle JDK
                                os.path.join(java_path, "lib", "libjli.dylib")  # Mac
                            ]
                            
                            for path in possible_jvm_paths:
                                if os.path.exists(path):
                                    jvm_path = path
                                    break
                except Exception as e:
                    logger.error(f"Error finding Java path: {str(e)}")
            
            # As a last resort, try jpype's default JVM path
            if not jvm_path:
                try:
                    jvm_path = jpype.getDefaultJVMPath()
                except Exception as e:
                    logger.error(f"Error getting default JVM path: {str(e)}")
                    raise RuntimeError("Could not find Java installation. Please ensure Java is installed or set JAVA_HOME environment variable.")
            
            logger.info(f"Using JVM path: {jvm_path}")
            jpype.startJVM(jvm_path, f"-Djava.class.path={classpath}")
        
        try:
            # Load the driver class
            jpype.JClass(self.driver_info["driver_class"])
            
            # Build the JDBC URL
            if self.db_type == DatabaseType.SQLITE:
                jdbc_url = self.driver_info["url_template"].format(database=self.database)
            else:
                jdbc_url = self.driver_info["url_template"].format(
                    host=self.host, 
                    port=self.port, 
                    database=self.database
                )
            
            # Get the DriverManager class
            driver_manager = jpype.JClass("java.sql.DriverManager")
            
            # Establish connection
            if self.username and self.password:
                self.connection = driver_manager.getConnection(jdbc_url, self.username, self.password)
            else:
                self.connection = driver_manager.getConnection(jdbc_url)
            
            logger.info(f"Connected to {self.db_type.value} database: {jdbc_url}")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the database."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Disconnected from database")
            except Exception as e:
                logger.error(f"Error disconnecting from database: {str(e)}")
            finally:
                self.connection = None
    
    def get_tables(self):
        """Get a list of all tables in the database."""
        if not self.connection:
            raise RuntimeError("Not connected to database")
        
        tables = []
        try:
            metadata = self.connection.getMetaData()
            
            # Get tables
            # Parameters: catalog, schema pattern, table name pattern, types
            rs = metadata.getTables(None, None, "%", ["TABLE"])
            
            while rs.next():
                table_name = rs.getString("TABLE_NAME")
                tables.append(table_name)
            
            rs.close()
            return tables
        
        except Exception as e:
            logger.error(f"Error getting tables: {str(e)}")
            return []
    
    def get_table_schema(self, table_name):
        """Get the schema of a table."""
        if not self.connection:
            raise RuntimeError("Not connected to database")
        
        columns = {}
        primary_keys = []
        
        try:
            metadata = self.connection.getMetaData()
            
            # Get primary keys
            rs_pk = metadata.getPrimaryKeys(None, None, table_name)
            while rs_pk.next():
                column_name = rs_pk.getString("COLUMN_NAME")
                primary_keys.append(column_name)
            rs_pk.close()
            
            # Get columns
            rs_cols = metadata.getColumns(None, None, table_name, "%")
            while rs_cols.next():
                column_name = rs_cols.getString("COLUMN_NAME")
                type_name = rs_cols.getString("TYPE_NAME")
                nullable = rs_cols.getInt("NULLABLE") == 1
                default_value = rs_cols.getString("COLUMN_DEF")
                
                columns[column_name] = {
                    "type": type_name,
                    "nullable": nullable,
                    "default": default_value,
                    "is_primary_key": column_name in primary_keys
                }
            rs_cols.close()
            
            return {
                "table_name": table_name,
                "columns": columns,
                "primary_keys": primary_keys
            }
        
        except Exception as e:
            logger.error(f"Error getting table schema: {str(e)}")
            return {"table_name": table_name, "columns": {}, "primary_keys": []}
    
    def execute_query(self, query, max_rows=100):
        """Execute a query and return the results."""
        if not self.connection:
            raise RuntimeError("Not connected to database")
        
        try:
            statement = self.connection.createStatement()
            is_result_set = statement.execute(query)
            
            results = []
            if is_result_set:
                rs = statement.getResultSet()
                metadata = rs.getMetaData()
                column_count = metadata.getColumnCount()
                
                # Get column names
                columns = []
                for i in range(1, column_count + 1):
                    columns.append(metadata.getColumnName(i))
                
                # Get data
                count = 0
                while rs.next() and count < max_rows:
                    row = {}
                    for i in range(1, column_count + 1):
                        value = rs.getString(i)
                        row[columns[i - 1]] = value
                    results.append(row)
                    count += 1
                
                rs.close()
            else:
                update_count = statement.getUpdateCount()
                results = {"update_count": update_count}
            
            statement.close()
            return results
        
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise

def main():
    """Main function for testing JDBC connections."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test JDBC connections")
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
    
    # Create JDBC connection
    jdbc = JDBCConnection(
        db_type=DatabaseType(args.type),
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password
    )
    
    try:
        # Connect to database
        if not jdbc.connect():
            sys.exit(1)
        
        # List tables
        if args.list_tables:
            tables = jdbc.get_tables()
            logger.info(f"Found {len(tables)} tables:")
            for table in tables:
                logger.info(f" - {table}")
        
        # Get table schema
        if args.table:
            schema = jdbc.get_table_schema(args.table)
            logger.info(f"Table schema for {args.table}:")
            logger.info(f"Primary keys: {schema['primary_keys']}")
            for col, col_info in schema["columns"].items():
                logger.info(f" - {col}: {col_info['type']} (nullable: {col_info['nullable']})")
        
        # Execute query
        if args.query:
            results = jdbc.execute_query(args.query)
            logger.info(f"Query results:")
            logger.info(json.dumps(results, indent=2))
    
    finally:
        # Disconnect
        jdbc.disconnect()

if __name__ == "__main__":
    main()
