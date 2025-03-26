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
        
        # Initialize Faker once with a consistent seed for reproducibility
        from faker import Faker
        self.faker = Faker()
        self.faker.seed_instance(42)  # Use a fixed seed for reproducibility
        
        # Analyze existing data (sampling) if available
        self.sample_data = {}
        self.column_patterns = {}
    
    def initialize(self):
        """Initialize the automator by getting the table schema."""
        try:
            self.schema = self.connector.get_table_schema(self.table_name)
            logger.info(f"Initialized automator for table {self.table_name}")
            # Now that we have schema information, introspect the table
            self.introspect_table()
            return True
        except Exception as e:
            logger.error(f"Error initializing automator: {str(e)}")
            return False
    
    def introspect_table(self):
        """Analyze the table structure and sample data to understand patterns."""
        try:
            # Use the get_table_schema method which now has specialized SQL for each DB type
            logger.info(f"Introspecting table {self.table_name} using database-specific methods")
            
            # This will already set self.schema, but let's make sure we have the latest
            # schema in case the table changed since initialization
            self.schema = self.connector.get_table_schema(self.table_name)
            
            # The schema now contains enhanced information:
            # - columns: detailed column specifications including types, nullability, etc.
            # - primary_keys: list of primary key columns
            # - foreign_keys: information about references to other tables
            # - indexes: information about table indexes
            
            logger.debug(f"Found {len(self.schema['columns'])} columns for {self.table_name}")
            logger.debug(f"Primary keys: {self.schema['primary_keys']}")
            logger.debug(f"Foreign keys: {len(self.schema['foreign_keys'])} relations")
            
            # Try to get sample data from the table to understand patterns
            try:
                # Use proper SQL quotes based on the database type
                if hasattr(self.connector, 'db_type'):
                    sample_query = self.connector.sql_statements.count_rows_statement(self.table_name)
                    row_count = self.connector.execute_query(sample_query)[0]['count']
                    logger.info(f"Table {self.table_name} has {row_count} rows")
                    
                    # Only get sample data if the table is not empty
                    if row_count > 0:
                        sample_query = f"SELECT * FROM {self.table_name} LIMIT 5"
                sample = self.connector.execute_query(sample_query)
                
                if sample:
                    # Store sample data for reference
                    for row in sample:
                        for col, val in row.items():
                            if col not in self.sample_data:
                                self.sample_data[col] = []
                            if val is not None:
                                self.sample_data[col].append(val)
                    
                    logger.debug(f"Collected sample data for {self.table_name}")
            except Exception as e:
                logger.debug(f"Could not get sample data for {self.table_name}: {str(e)}")
            
            # Analyze column patterns based on name, type and sample data
            for col_info in structure:
                # Handle different structures returned by different DB engines
                if 'Field' in col_info:
                    col_name = col_info['Field']
                    col_type = col_info['Type']
                elif 'COLUMN_NAME' in col_info:
                    col_name = col_info['COLUMN_NAME']
                    col_type = col_info['DATA_TYPE']
                else:
                    continue
                
                # Map column names to likely data types
                pattern = self.detect_column_pattern(col_name, col_type)
                self.column_patterns[col_name] = pattern
                
            logger.debug(f"Column patterns for {self.table_name}: {self.column_patterns}")
            
        except Exception as e:
            logger.warning(f"Error during table introspection: {str(e)}")
    
    def detect_column_pattern(self, column_name, column_type):
        """Detect what kind of data should be in this column based on name and type."""
        col_lower = column_name.lower()
        type_upper = column_type.upper() if column_type else ""
        
        # Determine category based on column name and type
        if any(keyword in col_lower for keyword in ['id', 'code', 'num', 'number']):
            if any(t in type_upper for t in ['INT', 'BIGINT', 'SMALLINT']):
                return 'id'
        
        if 'uuid' in col_lower:
            return 'uuid'
            
        if any(name in col_lower for name in ['first_name', 'firstname', 'fname', 'name']):
            return 'first_name'
            
        if any(name in col_lower for name in ['last_name', 'lastname', 'lname', 'surname']):
            return 'last_name'
            
        if any(name in col_lower for name in ['full_name', 'fullname']):
            return 'full_name'
            
        if 'email' in col_lower:
            return 'email'
            
        if any(addr in col_lower for addr in ['address', 'street', 'location']):
            return 'address'
            
        if any(city in col_lower for city in ['city', 'town']):
            return 'city'
            
        if any(state in col_lower for state in ['state', 'province', 'region']):
            return 'state'
            
        if any(zip in col_lower for zip in ['zip', 'postal', 'postcode']):
            return 'postcode'
            
        if any(country in col_lower for country in ['country', 'nation']):
            return 'country'
            
        if any(phone in col_lower for phone in ['phone', 'tel', 'mobile', 'cell']):
            return 'phone'
            
        if any(gender in col_lower for gender in ['gender', 'sex']):
            return 'gender'
            
        if 'company' in col_lower or 'organization' in col_lower:
            return 'company'
            
        if 'job' in col_lower or 'position' in col_lower or 'title' in col_lower:
            return 'job'
            
        if 'birthdate' in col_lower or 'birth_date' in col_lower or 'dob' in col_lower:
            return 'birthdate'
        
        # License and document fields
        if 'license' in col_lower or 'document' in col_lower or 'passport' in col_lower:
            return 'document'
            
        # Fallback to data type
        if 'INT' in type_upper:
            return 'integer'
        elif 'FLOAT' in type_upper or 'DOUBLE' in type_upper or 'DECIMAL' in type_upper:
            return 'float'
        elif 'DATE' in type_upper:
            return 'date'
        elif 'TIME' in type_upper:
            return 'time'
        elif 'TIMESTAMP' in type_upper or 'DATETIME' in type_upper:
            return 'datetime'
        elif 'BOOL' in type_upper:
            return 'boolean'
        elif 'VARCHAR' in type_upper or 'TEXT' in type_upper or 'CHAR' in type_upper:
            # For text fields we don't have a specific pattern for
            if int(type_upper.split('(')[1].split(')')[0]) < 20 if '(' in type_upper else False:
                return 'short_text'
            else:
                return 'text'
        else:
            return 'unknown'
    
    def generate_random_value(self, column_name, column_type):
        """Generate a random value for a column based on its pattern or data type."""
        # Use the detected pattern or fall back to simple data type
        pattern = self.column_patterns.get(column_name, 'unknown')
        
        # Generate value based on the detected pattern
        if pattern == 'id':
            return random.randint(1, 100000)
        elif pattern == 'uuid':
            return str(self.faker.uuid4())
        elif pattern == 'first_name':
            return self.faker.first_name()
        elif pattern == 'last_name':
            return self.faker.last_name()
        elif pattern == 'full_name':
            return self.faker.name()
        elif pattern == 'email':
            return self.faker.email()
        elif pattern == 'address':
            return self.faker.street_address()
        elif pattern == 'city':
            return self.faker.city()
        elif pattern == 'state':
            return self.faker.state()
        elif pattern == 'postcode':
            return self.faker.postcode()
        elif pattern == 'country':
            return self.faker.country()
        elif pattern == 'phone':
            return self.faker.phone_number()
        elif pattern == 'gender':
            return random.choice(['Male', 'Female', 'Other'])
        elif pattern == 'company':
            return self.faker.company()
        elif pattern == 'job':
            return self.faker.job()
        elif pattern == 'birthdate':
            return self.faker.date_of_birth(minimum_age=18, maximum_age=90).strftime('%Y-%m-%d')
        elif pattern == 'document':
            return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        elif pattern == 'integer':
            return random.randint(1, 1000)
        elif pattern == 'float':
            return round(random.uniform(1, 1000), 2)
        elif pattern == 'date':
            return self.faker.date_between(start_date='-5y', end_date='today').strftime('%Y-%m-%d')
        elif pattern == 'time':
            return self.faker.time()
        elif pattern == 'datetime':
            return self.faker.date_time_between(start_date='-5y', end_date='today').strftime('%Y-%m-%d %H:%M:%S')
        elif pattern == 'boolean':
            return random.choice([True, False, 0, 1])
        elif pattern == 'short_text':
            return ''.join(random.choice(string.ascii_letters) for _ in range(min(10, int(column_type.split('(')[1].split(')')[0]) if '(' in column_type else 10)))
        elif pattern == 'text':
            return self.faker.paragraph(nb_sentences=2)
        else:  # unknown
            # Fallback to the original method of determining by column type
            if "INT" in column_type.upper():
                return random.randint(1, 1000)
            elif "VARCHAR" in column_type.upper() or "TEXT" in column_type.upper():
                return self.faker.text(max_nb_chars=min(100, int(column_type.split('(')[1].split(')')[0]) if '(' in column_type else 100))
            elif "DATE" in column_type.upper():
                return self.faker.date_this_decade().strftime('%Y-%m-%d')
            elif "FLOAT" in column_type.upper() or "DOUBLE" in column_type.upper() or "DECIMAL" in column_type.upper():
                return round(random.uniform(1, 1000), 2)
            elif "BOOL" in column_type.upper():
                return random.choice([True, False])
            else:
                # If we have samples, try to mimic them
                if column_name in self.sample_data and self.sample_data[column_name]:
                    return random.choice(self.sample_data[column_name])
                return None
    
    def perform_insert(self):
        """Perform an INSERT operation on the table."""
        try:
            # Generate values for all columns
            columns = []
            values = []
            
            # Get the maximum ID for any table with an ID primary key
            # This is a more dynamic approach that works for any table
            max_id = None
            primary_keys = self.schema.get("primary_keys", [])
            if primary_keys:
                primary_key = primary_keys[0]
                try:
                    # Check if primary key is auto-incremented or ID
                    if primary_key.upper() == "ID" or ("auto_increment" in str(self.schema.get("columns", {}).get(primary_key, {}).get("extra", "")).lower()):
                        max_id_query = f"SELECT MAX({primary_key}) as max_id FROM {self.table_name}"
                        max_id_result = self.connector.execute_query(max_id_query)
                        if max_id_result and max_id_result[0]['max_id'] is not None:
                            max_id = int(max_id_result[0]['max_id']) + 1
                        else:
                            max_id = 1
                except Exception as e:
                    logger.warning(f"Failed to get max ID for {self.table_name}: {str(e)}")
                    max_id = random.randint(10000, 99999)  # Fallback to a random large number
            
            # Dynamic approach for all tables
            for col_name, col_info in self.schema["columns"].items():
                # Handle primary keys dynamically based on their data type and patterns
                if col_info["primary_key"]:
                    # Use our pattern detection for better primary key handling
                    pattern = self.column_patterns.get(col_name, 'unknown')
                    
                    if "INT" in col_info["type"].upper():
                        if max_id is not None:
                            # Use the max ID we've already calculated, plus a random offset
                            random_id = max_id + random.randint(1, 100)
                        else:
                            # Generate a random ID in a higher range to avoid conflicts
                            random_id = random.randint(10000, 100000)
                        columns.append(col_name)
                        values.append(random_id)
                    elif pattern == 'uuid':
                        # For UUID primary keys
                        uuid_val = str(self.faker.uuid4())
                        columns.append(col_name)
                        values.append(f"'{uuid_val}'")
                    else:
                        # For other primary key types
                        pk_value = self.generate_random_value(col_name, col_info["type"])
                        if pk_value is not None:
                            columns.append(col_name)
                            # For string values, add quotes
                            if isinstance(pk_value, str):
                                values.append(f"'{pk_value}'")
                            else:
                                values.append(pk_value)
                    continue
                
                # For non-primary keys, use our smart data generation
                value = self.generate_random_value(col_name, col_info["type"])
                if value is not None:
                    columns.append(col_name)
                    # Handle formatting based on value type
                    if isinstance(value, str):
                        # Escape any single quotes in the string
                        escaped_value = value.replace("'", "''")
                        values.append(f"'{escaped_value}'")
                    else:
                        values.append(value)
            
            # Prepare query
            columns_str = ", ".join(columns)
            
            # Build values string directly with proper SQL escaping
            # Values are already properly formatted from the loop above (with quotes for strings)
            values_str = ", ".join([str(v) for v in values])
            
            # Create query with direct value substitution - avoids double escaping issues
            final_query = f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({values_str})"
            
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
            
            # Generic foreign key constraint check - a more dynamic approach
            try:
                # First, try to get all tables to check for potential relationships
                all_tables_query = "SHOW TABLES"
                try:
                    all_tables = self.connector.execute_query(all_tables_query)
                    potential_related_tables = [list(table.values())[0] for table in all_tables if list(table.values())[0] != self.table_name]
                except Exception:
                    # If SHOW TABLES doesn't work (depends on DB type), we'll just continue
                    potential_related_tables = []
                
                # Generate potential foreign key column names based on typical naming patterns
                singular_name = self.table_name.rstrip('S')  # Simple heuristic to get singular form
                potential_fk_cols = [f"{singular_name}_ID", f"{self.table_name}_ID", "PARENT_ID"]
                
                # Try to get foreign key information from information_schema if available
                try:
                    fk_query = """
                    SELECT TABLE_NAME, COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                    WHERE REFERENCED_TABLE_NAME = ? AND REFERENCED_COLUMN_NAME = ? 
                    AND CONSTRAINT_SCHEMA = DATABASE()
                    """
                    fk_results = self.connector.execute_query(fk_query, params=[self.table_name, 'ID'])
                    
                    if fk_results:
                        # If we have actual FK information, use that instead of guessing
                        for fk_info in fk_results:
                            potential_related_tables = [fk_info['TABLE_NAME']]
                            potential_fk_cols = [fk_info['COLUMN_NAME']]
                        logger.info(f"Using actual foreign key information: {potential_related_tables} -> {potential_fk_cols}")
                except Exception:
                    # Information schema query might not work on all databases, continue with heuristic approach
                    logger.debug("Could not retrieve foreign key information from information_schema, using heuristic approach")
                
                has_dependent_records = False
                dependent_table = None
                dependent_column = None
                
                # Create a custom connector that doesn't log expected errors
                from utils.db_connector import DBConnector
                class QuietConnector:
                    def __init__(self, connector):
                        self._connector = connector
                    
                    def execute_query(self, query, params=None):
                        try:
                            return self._connector.execute_query(query, params)
                        except Exception as e:
                            if "Unknown column" in str(e):
                                # This is an expected error during FK discovery - log at debug level
                                logger.debug(f"Foreign key check: {str(e)}")
                                return None
                            # For other errors, let them propagate
                            raise
                
                quiet_connector = QuietConnector(self.connector)
                
                # Check each potential related table
                for related_table in potential_related_tables:
                    for fk_col in potential_fk_cols:
                        check_query = f"SELECT COUNT(*) as count FROM {related_table} WHERE {fk_col} = {record_id}"
                        check_result = quiet_connector.execute_query(check_query)
                        
                        if check_result and check_result[0]['count'] > 0:
                            logger.info(f"Found dependent records in {related_table}.{fk_col} for {self.table_name} ID {record_id}")
                            has_dependent_records = True
                            dependent_table = related_table
                            dependent_column = fk_col
                            break
                    
                    if has_dependent_records:
                        break
                
                # If we found dependent records, try to find an alternative record to delete
                if has_dependent_records and len(results) > 1:
                    logger.info(f"Looking for an alternative {self.table_name} record with no dependencies")
                    
                    for _ in range(5):  # Try 5 times
                        alt_id = random.choice(results)[primary_key]
                        check_query = f"SELECT COUNT(*) as count FROM {dependent_table} WHERE {dependent_column} = {alt_id}"
                        check_result = quiet_connector.execute_query(check_query)
                        
                        if check_result and check_result[0]['count'] == 0:
                            record_id = alt_id
                            logger.info(f"Found alternative {self.table_name} ID {record_id} with no dependencies")
                            break
                    
                    else:  # If no suitable record found
                        logger.info(f"Could not find a deletable {self.table_name} record, switching to UPDATE instead")
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
