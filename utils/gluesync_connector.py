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
import json
import logging
import os
import sys
import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def discover_gluesync_test_databases(gluesync_test_suite_path):
    """Discover database configurations in the gluesync-test-suite."""
    # Check for docker-compose files which often contain database configurations
    docker_compose_files = []
    for root, dirs, files in os.walk(gluesync_test_suite_path):
        for file in files:
            if file in ["docker-compose.yml", "docker-compose.yaml"]:
                docker_compose_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(docker_compose_files)} potential docker-compose files")
    
    # Parse docker-compose files to find database services
    databases = []
    for file_path in docker_compose_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
                # Basic detection of database services
                if any(db_term in content.lower() for db_term in ["mysql", "postgres", "postgresql", "mariadb", "sqlite", "sqlserver", "mssql", "oracle"]):
                    logger.info(f"Found potential database configuration in {file_path}")
                    databases.append({
                        "file_path": file_path,
                        "directory": os.path.dirname(file_path)
                    })
        except Exception as e:
            logger.error(f"Error reading {file_path}: {str(e)}")
    
    return databases

def register_databases_with_whisperer(host, port, databases):
    """Register discovered databases with the whisperer service."""
    base_url = f"http://{host}:{port}/api"
    
    for db_info in databases:
        try:
            # Parse docker-compose file to extract database connection details
            file_path = db_info["file_path"]
            dir_name = os.path.basename(db_info["directory"])
            
            # Determine database type from file content
            with open(file_path, 'r') as f:
                content = f.read().lower()
                
                db_type = None
                if "mysql" in content or "mariadb" in content:
                    db_type = DatabaseType.MYSQL.value
                    default_port = 3306
                elif "postgres" in content:
                    db_type = DatabaseType.POSTGRESQL.value
                    default_port = 5432
                elif "sqlite" in content:
                    db_type = DatabaseType.SQLITE.value
                    default_port = None
                elif "sqlserver" in content or "mssql" in content:
                    db_type = DatabaseType.MSSQL.value
                    default_port = 1433
                elif "oracle" in content:
                    db_type = DatabaseType.ORACLE.value
                    default_port = 1521
            
            if not db_type:
                logger.warning(f"Could not determine database type for {file_path}, skipping")
                continue
            
            # Construct a connection based on common defaults
            connection_data = {
                "name": f"Gluesync-{dir_name}",
                "description": f"Auto-discovered from gluesync-test-suite: {dir_name}",
                "db_type": db_type,
                "host": "localhost",
                "port": default_port,
                "username": "root" if db_type == DatabaseType.MYSQL.value else "postgres",
                "password": "password",
                "database_name": "test_db"
            }
            
            # For SQLite, use a path in the directory
            if db_type == DatabaseType.SQLITE.value:
                connection_data["database_name"] = os.path.join(db_info["directory"], "test.db")
                connection_data["host"] = None
                connection_data["port"] = None
                connection_data["username"] = None
                connection_data["password"] = None
            
            # Register with whisperer
            logger.info(f"Registering database: {connection_data['name']}")
            response = requests.post(f"{base_url}/connections", json=connection_data)
            if response.status_code == 201:
                logger.info(f"Successfully registered database: {connection_data['name']}")
                
                # Get connection ID from response
                connection_id = response.json()["id"]
                
                # Test the connection
                test_response = requests.post(f"{base_url}/connections/{connection_id}/test")
                if test_response.status_code == 200 and test_response.json()["success"]:
                    logger.info(f"Connection test successful for {connection_data['name']}")
                    
                    # Get tables
                    tables_response = requests.get(f"{base_url}/connections/{connection_id}/tables")
                    if tables_response.status_code == 200:
                        tables = tables_response.json()
                        logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
                        
                        # Configure all tables for automation
                        for table in tables:
                            table_config = {
                                "connection_id": connection_id,
                                "table_name": table,
                                "operation_type": "all",
                                "operation_delay": 1.0,
                                "batch_size": 1,
                                "enabled": True
                            }
                            
                            table_response = requests.post(f"{base_url}/tables", json=table_config)
                            if table_response.status_code == 201:
                                logger.info(f"Configured table {table} for automation")
                            else:
                                logger.warning(f"Failed to configure table {table}: {table_response.text}")
                    else:
                        logger.warning(f"Failed to get tables: {tables_response.text}")
                else:
                    logger.warning(f"Connection test failed for {connection_data['name']}: {test_response.text}")
            elif response.status_code == 400 and "already exists" in response.text:
                logger.info(f"Database {connection_data['name']} already registered")
            else:
                logger.warning(f"Failed to register database: {response.text}")
        
        except Exception as e:
            logger.error(f"Error processing {db_info['file_path']}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Discover and connect to databases in gluesync-test-suite")
    parser.add_argument("--gluesync-path", required=True, help="Path to gluesync-test-suite repository")
    parser.add_argument("--whisperer-host", default="localhost", help="Whisperer API host")
    parser.add_argument("--whisperer-port", default=8000, type=int, help="Whisperer API port")
    
    args = parser.parse_args()
    
    # Verify path exists
    if not os.path.exists(args.gluesync_path):
        logger.error(f"Path does not exist: {args.gluesync_path}")
        sys.exit(1)
    
    # Discover databases
    logger.info(f"Discovering databases in {args.gluesync_path}...")
    databases = discover_gluesync_test_databases(args.gluesync_path)
    logger.info(f"Found {len(databases)} potential database configurations")
    
    # Register with whisperer
    if databases:
        logger.info(f"Registering databases with whisperer at {args.whisperer_host}:{args.whisperer_port}...")
        register_databases_with_whisperer(args.whisperer_host, args.whisperer_port, databases)

if __name__ == "__main__":
    main()
