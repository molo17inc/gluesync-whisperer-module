#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Database Automator is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Database Automator.  If not, see <http://www.gnu.org/licenses/>.
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
    
    def connect(self):
        """Connect to the database."""
        try:
            # Build connection string
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
            
            logger.info(f"Connected to {self.db_type.value} database")
            return True
        
        except SQLAlchemyError as e:
            logger.error(f"Error connecting to database: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the database."""
        if self.engine:
            self.engine.dispose()
            logger.info("Disconnected from database")
    
    def get_tables(self):
        """Get a list of all tables in the database."""
        if not self.inspector:
            raise RuntimeError("Not connected to database")
        
        tables = self.inspector.get_table_names()
        logger.info(f"Found {len(tables)} tables:")
        for table in tables:
            logger.info(f" - {table}")
        
        return tables
    
    def get_table_schema(self, table_name):
        """Get the schema of a table."""
        if not self.inspector:
            raise RuntimeError("Not connected to database")
        
        # Get columns
        columns = {}
        for column in self.inspector.get_columns(table_name):
            columns[column['name']] = {
                'type': str(column['type']),
                'nullable': column.get('nullable', True),
                'default': str(column.get('default', None)),
                'primary_key': False  # Will be updated below
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
        for idx in self.inspector.get_indexes(table_name):
            indexes.append({
                'name': idx.get('name', ''),
                'columns': idx.get('column_names', []),
                'unique': idx.get('unique', False)
            })
        
        return {
            'table_name': table_name,
            'columns': columns,
            'primary_keys': primary_keys,
            'foreign_keys': foreign_keys,
            'indexes': indexes
        }
    
    def execute_query(self, query, max_rows=100):
        """Execute a query and return the results."""
        if not self.engine:
            raise RuntimeError("Not connected to database")
        
        try:
            with self.engine.connect() as conn:
                # Execute query
                result = conn.execute(text(query))
                
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
                    return {'affected_rows': result.rowcount}
        
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
