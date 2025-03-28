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
import sqlalchemy
from sqlalchemy import create_engine, inspect

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType

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
        # Always use JDBC for MS SQL Server
        return f"jdbc:sqlserver://{host}:{port};databaseName={database_name};trustServerCertificate=true;encrypt=true"
    elif db_type == DatabaseType.ORACLE:
        return f"oracle+cx_oracle://{username}:{password}@{host}:{port}/{database_name}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

def test_connection(connection_string):
    """Test a database connection."""
    try:
        engine = create_engine(connection_string)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        logger.info("Connection successful!")
        return engine
    except Exception as e:
        logger.error(f"Connection failed: {str(e)}")
        return None

def get_tables(engine):
    """Get all tables in the database."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Found {len(tables)} tables:")
    for table in tables:
        logger.info(f" - {table}")
    return tables

def get_table_schema(engine, table_name):
    """Get the schema of a table."""
    inspector = inspect(engine)
    
    # Get columns
    columns = inspector.get_columns(table_name)
    logger.info(f"Table {table_name} has {len(columns)} columns:")
    for column in columns:
        logger.info(f" - {column['name']}: {column['type']} (nullable: {column.get('nullable', True)})")
    
    # Get primary keys
    pk_constraint = inspector.get_pk_constraint(table_name)
    if pk_constraint and 'constrained_columns' in pk_constraint:
        logger.info(f"Primary keys: {', '.join(pk_constraint['constrained_columns'])}")
    else:
        logger.info("No primary keys found")

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
    
    # Build connection string
    db_type = DatabaseType(args.type)
    if db_type == DatabaseType.SQLITE:
        connection_string = build_connection_string(db_type, None, None, None, None, args.database)
    else:
        connection_string = build_connection_string(
            db_type, args.host, args.port, args.username, args.password, args.database
        )
    
    # Test connection
    logger.info(f"Testing connection to {args.type} database...")
    engine = test_connection(connection_string)
    if not engine:
        sys.exit(1)
    
    # List tables if requested
    if args.list_tables:
        tables = get_tables(engine)
    
    # Examine table if specified
    if args.table:
        get_table_schema(engine, args.table)

if __name__ == "__main__":
    main()
