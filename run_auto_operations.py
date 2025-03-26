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
import random
import sys
import time
import string
import traceback
from datetime import datetime
from utils.db_connector import DatabaseConnector
from models import DatabaseType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class TableAutomator:
    """Class to automate random operations on database tables."""
    
    def __init__(self, connector, table_name, delay=1.0, operations=None):
        """Initialize the automator with a database connector and table name."""
        self.connector = connector
        self.table_name = table_name
        self.delay = delay
        self.operations = operations or ["insert", "update", "delete"]
        self.operation_weights = {
            "insert": 0.33,
            "update": 0.33,
            "delete": 0.34
        }
        self.schema = None
        self.running = False
        self.operation_count = {op: 0 for op in self.operations}
    
    def initialize(self):
        """Initialize the automator by getting the table schema."""
        try:
            self.schema = self.connector.get_table_schema(self.table_name)
            logger.info(f"Initialized automator for table {self.table_name}")
            return True
        except Exception as e:
            logger.error(f"Error initializing automator: {str(e)}")
            return False
    
    def generate_random_value(self, column_name, column_type):
        """Generate a random value for a column based on its type."""
        if "INT" in column_type.upper():
            return random.randint(1, 1000)
        elif "VARCHAR" in column_type.upper() or "TEXT" in column_type.upper():
            if "NAME" in column_name.upper():
                names = ["John", "Mary", "Emma", "Michael", "Sarah", "James", "Lisa", "Robert", 
                         "Jennifer", "David", "Elizabeth", "William", "Linda", "Richard", "Susan"]
                return random.choice(names)
            elif "SURNAME" in column_name.upper():
                surnames = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", 
                           "Garcia", "Wilson", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Martin"]
                return random.choice(surnames)
            elif "ADDRESS" in column_name.upper():
                streets = ["Main St", "Oak Ave", "Maple Rd", "Cedar Ln", "Park Blvd", "Pine St", 
                         "Elm St", "Washington Ave", "Lake Rd", "River Dr"]
                return f"{random.randint(1, 999)} {random.choice(streets)}"
            elif "GENDER" in column_name.upper():
                return random.choice(["Male", "Female", "Other"])
            elif "PHONE" in column_name.upper():
                return f"+{random.randint(1, 99)} {random.randint(100, 999)} {random.randint(100, 999)} {random.randint(1000, 9999)}"
            elif "EMAIL" in column_name.upper():
                domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "example.com", "company.com"]
                username = ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
                return f"{username}@{random.choice(domains)}"
            else:
                return ''.join(random.choice(string.ascii_letters) for _ in range(10))
        elif "DATE" in column_type.upper():
            year = random.randint(2000, 2023)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            return f"{year}-{month:02d}-{day:02d}"
        elif "FLOAT" in column_type.upper() or "DOUBLE" in column_type.upper() or "DECIMAL" in column_type.upper():
            return round(random.uniform(1, 1000), 2)
        elif "BOOL" in column_type.upper():
            return random.choice([True, False])
        else:
            return None
    
    def perform_insert(self):
        """Perform an INSERT operation on the table."""
        try:
            # Generate values for all columns
            columns = []
            values = []
            
            # For the CUSTOMERS table, we need to specifically handle the ID
            # First, let's get the maximum ID
            max_id = 1
            if self.table_name == "CUSTOMERS":
                try:
                    max_id_query = f"SELECT MAX(ID) as max_id FROM {self.table_name}"
                    max_id_result = self.connector.execute_query(max_id_query)
                    if max_id_result and max_id_result[0]['max_id'] is not None:
                        max_id = int(max_id_result[0]['max_id']) + 1
                except Exception as e:
                    logger.warning(f"Failed to get max ID: {str(e)}")
            
            for col_name, col_info in self.schema["columns"].items():
                # For CUSTOMERS table, explicitly set ID
                if self.table_name == "CUSTOMERS" and col_name == "ID":
                    columns.append(col_name)
                    values.append(max_id)
                    continue
                
                # For other tables or columns, check if it's a primary key with auto-increment
                if col_info["primary_key"] and "INT" in col_info["type"].upper() and self.table_name != "CUSTOMERS":
                    continue
                
                value = self.generate_random_value(col_name, col_info["type"])
                if value is not None:
                    columns.append(col_name)
                    values.append(value)
            
            # Prepare query
            columns_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(values))
            query = f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({placeholders})"
            
            # Convert to SQLAlchemy format
            query = query.replace("%s", "?")
            values_str = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in values])
            final_query = query.replace("?", "{}").format(*([f"'{v}'" if isinstance(v, str) else str(v) for v in values]))
            
            # Execute query
            result = self.connector.execute_query(final_query)
            self.operation_count["insert"] += 1
            logger.info(f"INSERT operation successful: {final_query}")
            return True
        
        except Exception as e:
            logger.error(f"Error performing INSERT: {str(e)}")
            traceback.print_exc()
            return False
    
    def perform_update(self):
        """Perform an UPDATE operation on the table."""
        try:
            # Get a random record to update
            # Make sure we have a WHERE condition to avoid updating all records
            primary_keys = self.schema["primary_keys"]
            
            if not primary_keys:
                logger.warning(f"No primary keys found for table {self.table_name}, cannot perform update")
                return False
            
            primary_key = primary_keys[0]
            
            # Get all IDs from the table
            query = f"SELECT {primary_key} FROM {self.table_name}"
            results = self.connector.execute_query(query)
            
            if not results:
                logger.warning(f"No records found in table {self.table_name}, cannot perform update")
                return False
            
            record_id = random.choice(results)[primary_key]
            
            # Choose a random column to update
            updatable_columns = [
                col_name for col_name, col_info in self.schema["columns"].items()
                if not col_info["primary_key"]
            ]
            
            if not updatable_columns:
                logger.warning(f"No updatable columns found for table {self.table_name}, cannot perform update")
                return False
            
            column = random.choice(updatable_columns)
            value = self.generate_random_value(column, self.schema["columns"][column]["type"])
            
            # Prepare query
            value_str = f"'{value}'" if isinstance(value, str) else str(value)
            query = f"UPDATE {self.table_name} SET {column} = {value_str} WHERE {primary_key} = {record_id}"
            
            # Execute query
            result = self.connector.execute_query(query)
            self.operation_count["update"] += 1
            logger.info(f"UPDATE operation successful: {query}")
            return True
        
        except Exception as e:
            logger.error(f"Error performing UPDATE: {str(e)}")
            traceback.print_exc()
            return False
    
    def perform_delete(self):
        """Perform a DELETE operation on the table."""
        try:
            # Get a random record to delete
            # Make sure we have a WHERE condition to avoid deleting all records
            primary_keys = self.schema["primary_keys"]
            
            if not primary_keys:
                logger.warning(f"No primary keys found for table {self.table_name}, cannot perform delete")
                return False
            
            primary_key = primary_keys[0]
            
            # Get all IDs from the table
            query = f"SELECT {primary_key} FROM {self.table_name}"
            results = self.connector.execute_query(query)
            
            if not results:
                logger.warning(f"No records found in table {self.table_name}, cannot perform delete")
                return False
            
            record_id = random.choice(results)[primary_key]
            
            # Check if this record has any dependencies before deleting
            if self.table_name == "CUSTOMERS":
                # Check if customer has orders before deleting
                check_query = f"SELECT COUNT(*) as count FROM ORDERS_HEADERS WHERE CUSTOMER_ID = {record_id}"
                try:
                    check_result = self.connector.execute_query(check_query)
                    if check_result and check_result[0]['count'] > 0:
                        logger.info(f"Skipping delete for CUSTOMER ID {record_id} - has dependent orders")
                        # Try to find a customer without orders
                        for _ in range(5):  # Try 5 times
                            alt_id = random.choice(results)[primary_key]
                            check_query = f"SELECT COUNT(*) as count FROM ORDERS_HEADERS WHERE CUSTOMER_ID = {alt_id}"
                            check_result = self.connector.execute_query(check_query)
                            if check_result and check_result[0]['count'] == 0:
                                record_id = alt_id
                                logger.info(f"Found alternative CUSTOMER ID {record_id} with no orders")
                                break
                        else:  # If no customer without orders found
                            logger.info(f"Could not find a deletable customer, switching to UPDATE instead")
                            return self.perform_update()  # Perform an update instead
                except Exception as e:
                    logger.warning(f"Failed to check for dependent records: {str(e)}")
                    # Fall back to update if we can't check dependencies
                    return self.perform_update()
            
            # Prepare query
            query = f"DELETE FROM {self.table_name} WHERE {primary_key} = {record_id}"
            
            try:
                # Execute query
                result = self.connector.execute_query(query)
                self.operation_count["delete"] += 1
                logger.info(f"DELETE operation successful: {query}")
                
                # Check if we need to insert more records (to avoid depleting the table)
                if len(results) < 5:
                    self.perform_insert()
                
                return True
            except Exception as e:
                if "foreign key constraint" in str(e).lower():
                    logger.info(f"Foreign key constraint prevented deletion, switching to UPDATE")
                    # If we hit a constraint, do an update instead
                    return self.perform_update()
                else:
                    raise  # Re-raise if it's not a foreign key constraint
        
        except Exception as e:
            logger.error(f"Error performing DELETE: {str(e)}")
            traceback.print_exc()
            return False
    
    def perform_random_operation(self):
        """Perform a random operation based on weights."""
        operations = []
        weights = []
        
        for op in self.operations:
            operations.append(op)
            weights.append(self.operation_weights[op])
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # Choose an operation
        operation = random.choices(operations, weights=weights, k=1)[0]
        
        # Perform the chosen operation
        if operation == "insert":
            return self.perform_insert()
        elif operation == "update":
            return self.perform_update()
        elif operation == "delete":
            return self.perform_delete()
        else:
            logger.warning(f"Unknown operation: {operation}")
            return False
    
    def run(self):
        """Run the automator continuously."""
        self.running = True
        
        try:
            while self.running:
                # Perform a random operation
                self.perform_random_operation()
                
                # Wait for the specified delay
                time.sleep(self.delay)
                
                # Print operation counts every 10 operations
                total_ops = sum(self.operation_count.values())
                if total_ops % 10 == 0:
                    logger.info(f"Operation counts: {self.operation_count}")
        
        except KeyboardInterrupt:
            logger.info("Automator stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Error in automator: {str(e)}")
            traceback.print_exc()
            self.running = False
        finally:
            logger.info(f"Final operation counts: {self.operation_count}")

def main():
    """Main function for running table automation."""
    parser = argparse.ArgumentParser(description="Automate operations on a database table")
    parser.add_argument("--type", default="mysql", choices=[t.value for t in DatabaseType], help="Database type")
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", default="3306", help="Database port")
    parser.add_argument("--username", default="gluesync", help="Database username")
    parser.add_argument("--password", default="password", help="Database password")
    parser.add_argument("--database", default="demo", help="Database name/path")
    parser.add_argument("--table", default="CUSTOMERS", help="Table to automate")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between operations in seconds")
    parser.add_argument("--operations", nargs="+", choices=["insert", "update", "delete"], 
                      default=["insert", "update", "delete"], help="Operations to perform")
    
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
            logger.error("Failed to connect to database")
            sys.exit(1)
        
        # Create automator
        automator = TableAutomator(
            connector=connector,
            table_name=args.table,
            delay=args.delay,
            operations=args.operations
        )
        
        # Initialize automator
        if not automator.initialize():
            logger.error("Failed to initialize automator")
            sys.exit(1)
        
        # Run automator
        logger.info(f"Starting automator for table {args.table} with delay {args.delay}s")
        logger.info(f"Operations to perform: {args.operations}")
        automator.run()
    
    finally:
        # Disconnect
        connector.disconnect()

if __name__ == "__main__":
    main()
