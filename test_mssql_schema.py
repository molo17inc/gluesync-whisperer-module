#!/usr/bin/env python3
"""
Test script to verify MS SQL Server schema retrieval with the refactored database service
"""

import requests
import json
import time
import datetime
import sys

# Base URL for the API
BASE_URL = "http://localhost:1717/api"

def create_connection():
    """Create a test MS SQL Server connection"""
    url = f"{BASE_URL}/connections"
    
    # Use timestamp to create a unique connection name
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    data = {
        "name": f"MS SQL Test {timestamp}",
        "description": "MS SQL connection for testing schema retrieval",
        "host": "10.17.3.169",
        "port": 1433,
        "database": "demo",
        "username": "sa",
        "password": "GecYTBtXQxHe-mD7ePmdC",
        "db_type": "mssql"
    }
    
    print(f"Creating connection with data: {json.dumps(data, indent=2)}")
    response = requests.post(url, json=data)
    print(f"Connection creation response: {response.status_code}")
    if response.status_code == 201:
        return response.json()
    else:
        print(f"Error creating connection: {response.text}")
        return None

def get_schemas(connection_id):
    """Get all schemas for a connection"""
    url = f"{BASE_URL}/connections/{connection_id}/schemas"
    
    print(f"Requesting schemas from: {url}")
    response = requests.get(url)
    print(f"Schemas retrieval response: {response.status_code}")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error retrieving schemas: {response.text}")
        return None

def get_tables(connection_id, schema_name="dbo"):
    """Get all tables in a schema"""
    url = f"{BASE_URL}/connections/{connection_id}/tables"
    if schema_name:
        url += f"?schema={schema_name}"
    
    print(f"Requesting tables from: {url}")
    response = requests.get(url)
    print(f"Tables retrieval response: {response.status_code}")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error retrieving tables: {response.text}")
        return None

def get_table_schema(connection_id, table_name, schema_name="dbo"):
    """Get schema for a specific table"""
    url = f"{BASE_URL}/connections/{connection_id}/tables/{table_name}/schema"
    if schema_name:
        url += f"?schema={schema_name}"
    
    print(f"Requesting schema from: {url}")
    response = requests.get(url)
    print(f"Schema retrieval response: {response.status_code}")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error retrieving schema: {response.text}")
        return None

def main():
    # Create a connection
    connection = create_connection()
    if not connection:
        return
    
    connection_id = connection["id"]
    print(f"Created connection with ID: {connection_id}")
    
    # Wait a moment for the connection to be fully established
    time.sleep(2)
    
    # Get all schemas
    print("\nRetrieving all schemas:")
    schemas = get_schemas(connection_id)
    if schemas:
        print(f"Found schemas: {schemas}")
    
    # Get all tables in the dbo schema
    print("\nRetrieving all tables in dbo schema:")
    tables = get_tables(connection_id, "dbo")
    if tables:
        print(f"Found tables: {tables}")
    
    # Try to get schema for the DRIVERS table
    print("\nRetrieving schema for DRIVERS table:")
    schema = get_table_schema(connection_id, "DRIVERS", "dbo")
    if schema:
        print("\nSchema for DRIVERS table:")
        print(f"Columns: {json.dumps(schema['columns'], indent=2)}")
        print(f"Primary keys: {schema['primary_keys']}")
        print(f"Total columns: {len(schema['columns'])}")
    
    # Try some other tables if DRIVERS doesn't work
    if not schema or not schema['columns']:
        for table in tables[:3]:  # Try the first 3 tables
            print(f"\nRetrieving schema for {table} table:")
            schema = get_table_schema(connection_id, table, "dbo")
            if schema and schema['columns']:
                print(f"\nSchema for {table} table:")
                print(f"Columns: {json.dumps(schema['columns'], indent=2)}")
                print(f"Primary keys: {schema['primary_keys']}")
                print(f"Total columns: {len(schema['columns'])}")
                break

if __name__ == "__main__":
    main()
