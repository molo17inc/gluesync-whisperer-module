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
            batch_size: int = 1
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
    
    def start_pillow_fight(self, table_name: str, on_complete: Optional[Callable] = None) -> bool:
        """Start a pillow fight (automated operations) on a table."""
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
            args=(table_name, fight_id, on_complete),
            daemon=True
        )
        thread.start()
        self.threads[fight_id] = thread
        
        logger.info(f"Started pillow fight for table {table_name}")
        return True
    
    async def stop_pillow_fight(self, table_name: str) -> bool:
        """Stop a pillow fight on a table."""
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
    
    def get_stats(self, table_name: str) -> Dict[str, Any]:
        """Get stats for a pillow fight."""
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
    
    def _run_pillow_fight(self, table_name: str, fight_id: str, on_complete: Optional[Callable] = None):
        """Run the pillow fight operations."""
        try:
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
            
            # Create table automator from run_auto_operations.py
            from run_auto_operations import TableAutomator
            
            automator = TableAutomator(
                connector=connector,
                table_name=table_name,
                delay=self.operation_delay,
                operations=self.operation_types
            )
            
            if not automator.initialize():
                logger.error(f"Failed to initialize automator for table {table_name}")
                self.operation_stats[fight_id]["status"] = "failed"
                if on_complete:
                    on_complete()
                return
            
            # Run operations until stopped
            while not self.stop_events[fight_id].is_set():
                operation_success = automator.perform_random_operation()
                
                if operation_success:
                    # Update stats
                    for op_type, count in automator.operation_count.items():
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
