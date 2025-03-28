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

import os
import sqlite3
import logging
from functools import wraps
from contextlib import contextmanager
from typing import Dict, List, Any, Generator

from config import settings

# Configure logging
logger = logging.getLogger(__name__)

class Database:
    """SQLite database connection manager for internal application storage."""
    
    def __init__(self, db_url=None):
        """Initialize the database connection."""
        self.db_url = db_url or settings.DB_URL
        # Remove sqlite:/// prefix if present
        if self.db_url.startswith('sqlite:///'):
            self.db_path = self.db_url.replace('sqlite:///', '')
        else:
            self.db_path = self.db_url
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        # Create tables if they don't exist
        self._init_db()
    
    def _init_db(self):
        """Initialize the database with required tables."""
        # Create tables if they don't exist
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Database connections table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS database_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                db_type TEXT NOT NULL,
                host TEXT,
                port INTEGER,
                username TEXT,
                password TEXT,
                database_name TEXT NOT NULL,
                connection_string TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_operation_at TIMESTAMP
            )
            """)
            
            # Table configs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                schema_name TEXT,
                operation_type TEXT NOT NULL DEFAULT 'all',
                operation_delay REAL NOT NULL DEFAULT 1.0,
                batch_size INTEGER NOT NULL DEFAULT 1,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                column_definitions TEXT,
                primary_keys TEXT,
                FOREIGN KEY (connection_id) REFERENCES database_connections (id) ON DELETE CASCADE
            )
            """)
            
            # Operation logs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_config_id INTEGER NOT NULL,
                operation_type TEXT NOT NULL,
                record_id TEXT,
                operation_data TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (table_config_id) REFERENCES table_configs (id) ON DELETE CASCADE
            )
            """)
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Get a database connection as a context manager."""
        conn = sqlite3.connect(self.db_path)
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Set row_factory to return dictionaries
        conn.row_factory = sqlite3.Row
        
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            conn.close()

# Singleton database instance
_db = Database(settings.DB_URL)

# Method to obtain a database connection
def get_db() -> Database:
    return _db

