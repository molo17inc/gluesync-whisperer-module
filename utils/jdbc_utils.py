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

import json
import os
import platform
import logging
from pathlib import Path
from typing import List, Any, Tuple, Optional, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Try to import JPype, fall back to PyJNIus if not available
try:
    import jpype
    import jpype.imports
    from jpype.types import *
    import jaydebeapi
    USE_JPYPE = True
    logger.debug("Using JPype for JVM interaction")
except ImportError:
    try:
        import jnius_config
        import pyjnius
        import jaydebeapi
        USE_JPYPE = False
        logger.debug("Using PyJNIus for JVM interaction")
    except ImportError:
        logger.error("Neither JPype nor PyJNIus available. JDBC functionality will be disabled.")
        USE_JPYPE = None

def create_properties(prop_dict: Dict[str, str]):
    """Create a Java Properties object from a Python dictionary."""
    if USE_JPYPE:
        Properties = jpype.JClass('java.util.Properties')
        props = Properties()
        for key, value in prop_dict.items():
            props.setProperty(str(key), str(value))
        return props
    elif USE_JPYPE is False:  # PyJNIus
        from jnius import autoclass
        Properties = autoclass('java.util.Properties')
        props = Properties()
        for key, value in prop_dict.items():
            props.setProperty(str(key), str(value))
        return props
    else:
        logger.error("JVM not available - cannot create Properties object")
        raise RuntimeError("JVM not available")

def initialize_jvm(driver_path: List[str]) -> None:
    """Initialize JVM with proper parameters if not already running."""
    if USE_JPYPE is None:
        raise RuntimeError("JVM libraries not available")
        
    try:
        if USE_JPYPE:
            if not jpype.isJVMStarted():
                logger.debug("Starting JVM with JPype...")
                classpath = os.pathsep.join([os.path.abspath(p) for p in driver_path])
                java_home = os.getenv('JAVA_HOME', '/usr/lib/jvm/default-java')
                
                # Determine JVM path based on platform
                if platform.system() == 'Darwin':  # macOS
                    if platform.processor() == 'arm':  # Apple Silicon
                        jvm_path = os.path.join(java_home, 'lib', 'server', 'libjvm.dylib')
                    else:  # Intel Mac
                        jvm_path = os.path.join(java_home, 'lib', 'server', 'libjvm.dylib')
                elif platform.system() == 'Windows':
                    jvm_path = os.path.join(java_home, 'bin', 'server', 'jvm.dll')
                else:  # Linux and others
                    jvm_path = os.path.join(java_home, 'lib', 'server', 'libjvm.so')

                logger.debug(f"JAVA_HOME: {java_home}")
                logger.debug(f"JVM Path: {jvm_path}")
                logger.debug(f"Classpath: {classpath}")

                jpype.startJVM(
                    jvm_path,
                    f"-Djava.class.path={classpath}",
                    "-ea",
                    convertStrings=True,
                    interrupt=True
                )
                logger.debug("JVM started successfully with JPype")
            else:
                logger.debug("JVM is already running (JPype)")
        else:  # PyJNIus
            logger.debug("Starting JVM with PyJNIus...")
            jnius_config.set_classpath(*driver_path)
            logger.debug("JVM started successfully with PyJNIus")

    except Exception as e:
        logger.error(f"Failed to initialize JVM: {str(e)}")
        raise RuntimeError(f"Unable to start JVM: {str(e)}")

def connect_to_database(driver_path: List[str], connection_string: str, driverclass: str = None, driver_options: Optional[dict] = None) -> jaydebeapi.Connection:
    """
    Connect to a database using JDBC.
    
    Args:
        driver_path: List of paths to JDBC driver JAR files
        connection_string: JDBC connection URL
        driverclass: JDBC driver class name
        driver_options: Dictionary of connection properties
        
    Returns:
        A database connection object
    """
    if USE_JPYPE is None:
        raise RuntimeError("JVM libraries not available")
        
    try:
        initialize_jvm(driver_path)

        logger.debug(f"Attempting connection with:")
        logger.debug(f"Driver class: {driverclass}")
        logger.debug(f"Connection string: {connection_string}")
        logger.debug(f"Driver path: {driver_path}")

        if driver_options is None:
            driver_options = {}

        # Handle AS400/DB2 specific configuration
        if driverclass in ["com.ibm.as400.access.AS400JDBCDriver", "com.ibm.db2.jcc.DB2Driver"]:
            # Create properties dictionary with all string values
            properties = {
                'user': str(driver_options.get('user', '')),
                'password': str(driver_options.get('password', '')),
                'prompt': 'false',
                'libraries': str(driver_options.get('libraries', '*LIBL')),
                'naming': 'system',
                'errors': 'full',
                'date format': 'iso',
                'time format': 'iso',
                'transaction isolation': 'none'
            }

            # Convert any additional driver options
            properties.update({k: str(v) for k, v in driver_options.items()
                             if k not in ['user', 'password']})

            # Create Java Properties object
            java_props = create_properties(properties)

            # Create connection using the URL and Properties object
            connection = jaydebeapi.connect(
                jclassname=driverclass,
                url=connection_string,
                driver_args=(java_props,),  # Pass just the Properties object
                jars=driver_path
            )
        # Handle Oracle specific configuration
        elif driverclass == "oracle.jdbc.OracleDriver":
            # Create properties dictionary with all string values
            properties = {
                'user': str(driver_options.get('user', '')),
                'password': str(driver_options.get('password', '')),
                'oracle.net.disableOob': 'true',
                'oracle.jdbc.readTimeout': '10000',
                'oracle.net.CONNECT_TIMEOUT': '10000',
                'defaultRowPrefetch': '20'
            }

            # Convert any additional driver options
            properties.update({k: str(v) for k, v in driver_options.items()
                             if k not in ['user', 'password']})

            # Create Java Properties object
            java_props = create_properties(properties)

            # Create connection using the URL and Properties object
            connection = jaydebeapi.connect(
                jclassname=driverclass,
                url=connection_string,
                driver_args=(java_props,),  # Pass just the Properties object
                jars=driver_path
            )
        else:
            # For non-Oracle connections
            connection = jaydebeapi.connect(
                jclassname=driverclass,
                url=connection_string,
                driver_args=driver_options,
                jars=driver_path
            )

        logger.info("Database connection established successfully")
        return connection

    except Exception as e:
        logger.error(f"JDBC: Database connection failed: {str(e)}")
        raise

def is_select_query(sql_query: str) -> bool:
    """Check if a query is a SELECT statement."""
    return sql_query.strip().upper().startswith("SELECT")

def execute_query(connection: jaydebeapi.Connection, query: str) -> List[Tuple]:
    """Execute a SQL query on the given connection."""
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall() if is_select_query(query) else None
    except Exception as e:
        logger.error(f"JDBC: Query execution error: {str(e)}, in Query: '{query}'")
        raise
    finally:
        if cursor:
            cursor.close()

def get_jdbc_drivers_path(additional_paths=None):
    """
    Get a list of JDBC driver JAR file paths from the jdbc_drivers directory.
    
    Args:
        additional_paths: Optional list of additional paths to include
        
    Returns:
        List of paths to JDBC driver JAR files
    """
    # Find the jdbc_drivers directory relative to the current module
    jdbc_dir = Path(__file__).parent.parent / "jdbc_drivers"
    
    if not jdbc_dir.exists():
        logger.warning(f"JDBC drivers directory not found at {jdbc_dir}")
        jar_files = []
    else:
        # Get all JAR files from the jdbc_drivers directory
        jar_files = [str(jdbc_dir / jar) for jar in os.listdir(jdbc_dir) if jar.endswith(".jar")]
    
    # Add any additional paths
    if additional_paths:
        jar_files.extend(additional_paths)
    
    if not jar_files:
        logger.warning("No JDBC driver JAR files found")
    
    return jar_files

def get_schemas(connection):
    """
    Get all schemas from the database.
    
    Args:
        connection: JDBC connection object
        
    Returns:
        List of schema names
    """
    schemas = []
    cursor = None
    try:
        cursor = connection.cursor()
        metadata = cursor.connection.getMetaData()
        
        # For AS400/DB2, use a different approach to get schemas
        if "as400" in cursor.connection.getMetaData().getURL().lower():
            # For AS400, libraries are considered schemas
            rs = metadata.getSchemas()
            while rs.next():
                schema_name = rs.getString("TABLE_SCHEM")
                schemas.append(schema_name)
            rs.close()
        else:
            # Generic approach for other databases
            cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA")
            rows = cursor.fetchall()
            schemas = [row[0] for row in rows]
        
        return schemas
    except Exception as e:
        logger.error(f"Error getting schemas via JDBC: {str(e)}")
        # Fallback approach for AS400
        try:
            if cursor:
                cursor.execute("SELECT DISTINCT TABLE_SCHEMA FROM QSYS2.SYSTABLES WHERE TABLE_SCHEMA NOT LIKE 'Q%' OR TABLE_SCHEMA = 'QGPL'")
                rows = cursor.fetchall()
                schemas = [row[0] for row in rows]
                return schemas
        except Exception as inner_e:
            logger.error(f"Fallback schema query failed: {str(inner_e)}")
        raise
    finally:
        if cursor:
            cursor.close()

def get_tables(connection, schema=None):
    """
    Get all tables from the specified schema or all schemas if not specified.
    
    Args:
        connection: JDBC connection object
        schema: Optional schema name to filter tables
        
    Returns:
        List of table names or (schema, table) tuples if schema is None
    """
    tables = []
    cursor = None
    try:
        cursor = connection.cursor()
        metadata = cursor.connection.getMetaData()
        
        if schema:
            rs = metadata.getTables(None, schema, "%", ["TABLE"])
            while rs.next():
                table_name = rs.getString("TABLE_NAME")
                tables.append(table_name)
            rs.close()
        else:
            rs = metadata.getTables(None, "%", "%", ["TABLE"])
            while rs.next():
                schema_name = rs.getString("TABLE_SCHEM")
                table_name = rs.getString("TABLE_NAME")
                tables.append((schema_name, table_name))
            rs.close()
        
        return tables
    except Exception as e:
        logger.error(f"Error getting tables via JDBC: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
