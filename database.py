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
from typing import Dict, List, Any, Generator, Optional, Union

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
        
        logger.info(f"Database initialized with path: {self.db_path}")
        
        # Ensure the directory exists
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        logger.info(f"Ensuring directory exists: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)
        
        # Create tables if they don't exist
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        logger.info(f"Creating tables in database: {self.db_path}")
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                logger.info("Database connection established successfully")
                
                # Create database_connections table
                logger.info("Creating database_connections table if it doesn't exist")
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS database_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    database_name TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    db_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'idle',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_operation_at TEXT,
                    connection_string TEXT
                )
                ''')
                
                # Create table_configs table
                logger.info("Creating table_configs table if it doesn't exist")
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS table_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    connection_id INTEGER NOT NULL,
                    table_name TEXT NOT NULL,
                    schema_name TEXT,
                    operation_type TEXT NOT NULL,
                    operation_delay REAL NOT NULL DEFAULT 1.0,
                    batch_size INTEGER NOT NULL DEFAULT 1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    column_definitions TEXT,
                    primary_keys TEXT,
                    FOREIGN KEY (connection_id) REFERENCES database_connections (id) ON DELETE CASCADE
                )
                ''')
                
                # Create operation_logs table
                logger.info("Creating operation_logs table if it doesn't exist")
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_config_id INTEGER NOT NULL,
                    operation_type TEXT NOT NULL,
                    record_id TEXT,
                    operation_data TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT,
                    FOREIGN KEY (table_config_id) REFERENCES table_configs (id) ON DELETE CASCADE
                )
                ''')
                
                conn.commit()
                logger.info("All tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}", exc_info=True)
    
    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def execute(self, query, params=None):
        """Execute a query and return the last row id."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()  # Explicitly commit the transaction
            return cursor.lastrowid
    
    def commit(self):
        """Commit the current transaction."""
        # SQLite auto-commits after each execute, so this is a no-op
        pass
    
    def query(self, query, params=None):
        """Execute a query and return all results as dictionaries."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()  # Explicitly commit the transaction
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def query_one(self, query, params=None):
        """Execute a query and return the first result as a dictionary."""
        logger.info(f"Executing query_one: {query} with params: {params}")
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()  # Explicitly commit the transaction
                row = cursor.fetchone()
                logger.info(f"Query result: {row}")
                if row:
                    columns = [col[0] for col in cursor.description]
                    result = dict(zip(columns, row))
                    logger.info(f"Returning result: {result}")
                    return result
                logger.info("No results found")
                return None
        except Exception as e:
            logger.error(f"Error executing query_one: {str(e)}", exc_info=True)
            return None
            
    def cursor(self):
        """Return a cursor for direct SQL operations.
        
        This method is used by the JDBC-only implementation to execute SQL queries directly.
        The cursor is wrapped to ensure proper connection management.
        """
        # Create a connection and cursor
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Wrap the cursor to handle connection management
        class ManagedCursor:
            def __init__(self, conn, cursor):
                self.conn = conn
                self.cursor = cursor
                
            def execute(self, query, params=None):
                return self.cursor.execute(query, params or ())
                
            def fetchall(self):
                return self.cursor.fetchall()
                
            def fetchone(self):
                return self.cursor.fetchone()
                
            def close(self):
                self.conn.close()
                
            def commit(self):
                self.conn.commit()
                
            @property
            def lastrowid(self):
                return self.cursor.lastrowid
                
            @property
            def description(self):
                return self.cursor.description
        
        return ManagedCursor(conn, cursor)
    
    def scalar(self, query, params=None):
        """Execute a query and return a single value."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            row = cursor.fetchone()
            return row[0] if row else None

# Singleton database instance
_db = Database(settings.DB_URL)

def get_db():
    """Get the database connection."""
    return _db

def init_db():
    """Initialize the database."""
    # The database is already initialized when the singleton is created
    return _db
