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

import logging
import random
import string
import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from utils.db_connector import DatabaseConnector
from models import DatabaseType, OperationType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global registry for active pillow fights
active_pillow_fights = {}

class PillowFightService:
    """Service to manage database pillow fights (automated operations)."""
    
    def __init__(
            self,
            db_type: DatabaseType,
            host: str,
            port: int,
            database: str,
            username: str,
            password: str,
            operation_types: List[str] = None,
            operation_delay: float = 1.0,
            batch_size: int = 1,
            schema_name: str = None
        ):
        """Initialize the pillow fight service."""
        self.db_type = db_type
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.operation_types = operation_types or ["insert", "update", "delete"]
        self.operation_delay = operation_delay
        self.batch_size = batch_size
        self.schema_name = schema_name
        self.connectors = {}
        self.stop_events = {}
        self.operation_stats = {}
        self.threads = {}
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test the database connection."""
        try:
            connector = DatabaseConnector(
                db_type=self.db_type,
                host=self.host,
                port=self.port,
                database=self.database,
                username=self.username,
                password=self.password
            )
            if connector.connect():
                tables = connector.get_tables()
                connector.disconnect()
                return True, f"Successfully connected to {self.database}. Found {len(tables)} tables."
            else:
                return False, "Failed to connect to the database."
        except Exception as e:
            return False, f"Error testing connection: {str(e)}"
    
    async def list_tables(self) -> List[str]:
        """List all tables in the database."""
        try:
            connector = DatabaseConnector(
                db_type=self.db_type,
                host=self.host,
                port=self.port,
                database=self.database,
                username=self.username,
                password=self.password
            )
            if connector.connect():
                tables = connector.get_tables()
                connector.disconnect()
                return tables
            else:
                return []
        except Exception as e:
            logger.error(f"Error listing tables: {str(e)}")
            return []
    
    async def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific table."""
        try:
            connector = DatabaseConnector(
                db_type=self.db_type,
                host=self.host,
                port=self.port,
                database=self.database,
                username=self.username,
                password=self.password
            )
            if connector.connect():
                schema = connector.get_table_schema(table_name)
                connector.disconnect()
                return schema
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting table schema: {str(e)}")
            return None
    
    def start_pillow_fight(self, table_name: str, schema_name: str = None, on_complete: Optional[Callable] = None, table_config=None) -> bool:
        """Start a pillow fight (automated operations) on a table.
        
        Args:
            table_name: Name of the table to operate on
            schema_name: Schema name for databases that require it
            on_complete: Optional callback when the operation completes
            table_config: Optional pre-existing table configuration
        """
        # Use provided schema_name or the one set in the constructor
        use_schema = schema_name or self.schema_name
        
        # For AS400, include schema name in the fight_id when available
        if self.db_type == DatabaseType.AS400 and use_schema:
            fight_id = f"{self.database}_{use_schema}_{table_name}"
        else:
            fight_id = f"{self.database}_{table_name}"
        
        # Check if this pillow fight is already running
        if fight_id in self.stop_events and not self.stop_events[fight_id].is_set():
            logger.info(f"Pillow fight already running for table {table_name}")
            return False
        
        # Create a stop event
        self.stop_events[fight_id] = threading.Event()
        
        # Initialize stats
        self.operation_stats[fight_id] = {
            "start_time": datetime.now(),
            "last_operation_time": None,
            "operations": {
                "insert": 0,
                "update": 0,
                "delete": 0
            },
            "status": "running"
        }
        
        # Start the pillow fight in a separate thread
        thread = threading.Thread(
            target=self._run_pillow_fight,
            args=(table_name, fight_id, on_complete, schema_name, table_config),
            daemon=True
        )
        thread.start()
        self.threads[fight_id] = thread
        
        logger.info(f"Started pillow fight for table {table_name}")
        return True
    
    async def stop_pillow_fight(self, table_name: str, schema_name: str = None) -> bool:
        """Stop a pillow fight on a table."""
        # Use provided schema_name or the one set in the constructor
        use_schema = schema_name or self.schema_name
        
        # For AS400, include schema name in the fight_id when available
        if self.db_type == DatabaseType.AS400 and use_schema:
            fight_id = f"{self.database}_{use_schema}_{table_name}"
        else:
            fight_id = f"{self.database}_{table_name}"
        
        if fight_id not in self.stop_events:
            logger.info(f"No pillow fight running for table {table_name}")
            return False
        
        # Signal the thread to stop
        self.stop_events[fight_id].set()
        
        # Update stats
        if fight_id in self.operation_stats:
            self.operation_stats[fight_id]["status"] = "stopped"
        
        logger.info(f"Stopped pillow fight for table {table_name}")
        return True
    
    def get_stats(self, table_name: str, schema_name: str = None) -> Dict[str, Any]:
        """Get stats for a pillow fight."""
        # Use provided schema_name or the one set in the constructor
        use_schema = schema_name or self.schema_name
        
        # For AS400, include schema name in the fight_id when available
        if self.db_type == DatabaseType.AS400 and use_schema:
            fight_id = f"{self.database}_{use_schema}_{table_name}"
        else:
            fight_id = f"{self.database}_{table_name}"
        
        if fight_id not in self.operation_stats:
            return {
                "status": "not_running",
                "operations": {
                    "insert": 0,
                    "update": 0,
                    "delete": 0
                }
            }
        
        stats = self.operation_stats[fight_id].copy()
        if stats["start_time"]:
            stats["duration"] = (datetime.now() - stats["start_time"]).total_seconds()
        else:
            stats["duration"] = 0
            
        return stats
    
    def _run_pillow_fight(self, table_name: str, fight_id: str, on_complete: Optional[Callable] = None, schema_name: str = None, table_config=None):
        """Run the pillow fight operations.
        
        Args:
            table_name: Name of the table to operate on
            fight_id: Unique identifier for this pillow fight
            on_complete: Optional callback when operation completes
            schema_name: Schema name for databases that require it
            table_config: Optional pre-existing table configuration with schema information
        """
        try:
            # Use provided schema_name or the one set in the constructor
            use_schema = schema_name or self.schema_name
            
            # Create a connector for this thread
            connector = DatabaseConnector(
                db_type=self.db_type,
                host=self.host,
                port=self.port,
                database=self.database,
                username=self.username,
                password=self.password
            )
            
            if not connector.connect():
                logger.error(f"Failed to connect to database for table {table_name}")
                self.operation_stats[fight_id]["status"] = "failed"
                if on_complete:
                    on_complete()
                return
            
            # Create table whisperer from run_auto_operations.py
            from run_auto_operations import TableWhisperer
            
            # Prepare pre-existing schema from table_config if available
            pre_existing_schema = None
            if table_config and hasattr(table_config, 'column_definitions') and hasattr(table_config, 'primary_keys'):
                # Make a copy of column definitions
                columns_with_primary_keys = {}
                primary_key_list = table_config.primary_keys if isinstance(table_config.primary_keys, list) else []
                
                # For each column, ensure it has a 'primary_key' field
                for col_name, col_info in table_config.column_definitions.items():
                    # Make a copy of the column info
                    col_copy = dict(col_info)
                    
                    # Set primary_key field if not already present
                    if 'primary_key' not in col_copy:
                        col_copy['primary_key'] = col_name in primary_key_list
                    
                    # Add to our new columns dictionary
                    columns_with_primary_keys[col_name] = col_copy
                
                pre_existing_schema = {
                    'columns': columns_with_primary_keys,
                    'primary_keys': primary_key_list,
                    'foreign_keys': [],  # We don't need foreign keys for operations
                    'indexes': []  # We don't need indexes for operations
                }
                logger.info(f"Using existing schema information from table configuration with {len(primary_key_list)} primary keys")
            
            # For AS400, pass the schema_name parameter
            if self.db_type == DatabaseType.AS400 and use_schema:
                logger.info(f"Creating TableWhisperer for AS400 table {use_schema}.{table_name}")
                whisperer = TableWhisperer(
                    connector=connector,
                    table_name=table_name,
                    schema_name=use_schema,
                    delay=self.operation_delay,
                    operations=self.operation_types,
                    pre_existing_schema=pre_existing_schema
                )
            else:
                whisperer = TableWhisperer(
                    connector=connector,
                    table_name=table_name,
                    delay=self.operation_delay,
                    operations=self.operation_types,
                    pre_existing_schema=pre_existing_schema
                )
            
            if not whisperer.initialize():
                logger.error(f"Failed to initialize whisperer for table {table_name}")
                self.operation_stats[fight_id]["status"] = "failed"
                if on_complete:
                    on_complete()
                return
            
            # Run operations until stopped
            while not self.stop_events[fight_id].is_set():
                operation_success = whisperer.perform_random_operation()
                
                if operation_success:
                    # Update stats
                    for op_type, count in whisperer.operation_count.items():
                        self.operation_stats[fight_id]["operations"][op_type] = count
                    
                    self.operation_stats[fight_id]["last_operation_time"] = datetime.now()
                
                # Sleep between operations
                time.sleep(self.operation_delay)
            
            # Cleanup
            connector.disconnect()
            
            logger.info(f"Pillow fight for table {table_name} completed")
            if on_complete:
                on_complete()
            
        except Exception as e:
            logger.error(f"Error in pillow fight for table {table_name}: {str(e)}")
            self.operation_stats[fight_id]["status"] = "error"
            if on_complete:
                on_complete()
    
    @staticmethod
    def is_pillow_fight_active(db_name: str, table_name: str) -> bool:
        """Check if a pillow fight is active for a table."""
        fight_id = f"{db_name}_{table_name}"
        return fight_id in active_pillow_fights
