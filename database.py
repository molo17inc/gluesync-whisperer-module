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
import time
import threading
import queue
from contextlib import contextmanager
from typing import Dict, List, Any, Generator, Optional, Union, Callable

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
        
        # Connection pool / retry configuration
        self.pool_size = int(os.getenv("SQLITE_POOL_SIZE", "5"))
        self.busy_timeout_ms = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000"))
        self.retry_attempts = int(os.getenv("SQLITE_MAX_RETRIES", "5"))
        self.retry_base_delay = float(os.getenv("SQLITE_RETRY_BASE_DELAY", "0.1"))
        self.retry_max_delay = float(os.getenv("SQLITE_RETRY_MAX_DELAY", "1.0"))
        self._pool: "queue.Queue[sqlite3.Connection]" = queue.Queue(maxsize=self.pool_size)
        self._pool_lock = threading.Lock()
        
        # Initialize database schema and connection pool
        self._initialize_database()
        self._initialize_pool()
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Create database tables if they don't exist."""
        logger.info(f"Creating tables in database: {self.db_path}")
        try:
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
                    cascade_delete INTEGER NOT NULL DEFAULT 0,
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
                
            # Add cascade_delete column to table_configs if it doesn't exist
            try:
                # Check if the column exists
                cursor.execute("PRAGMA table_info(table_configs)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'cascade_delete' not in columns:
                    logger.info("Adding cascade_delete column to table_configs table")
                    cursor.execute('''
                        ALTER TABLE table_configs ADD COLUMN cascade_delete INTEGER NOT NULL DEFAULT 0
                        ''')
                    logger.info("Added cascade_delete column to table_configs table")
            except Exception as e:
                logger.error(f"Error adding cascade_delete column: {str(e)}")

            # Create pillow fight job tracking tables
            logger.info("Creating pillow fight job tracking tables if they don't exist")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pillow_fight_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    connection_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    operation_types TEXT NOT NULL,
                    operation_delay REAL NOT NULL DEFAULT 1.0,
                    batch_size INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    last_heartbeat TEXT,
                    error_message TEXT,
                    warning_message TEXT,
                    FOREIGN KEY (connection_id) REFERENCES database_connections (id) ON DELETE CASCADE
                )
                ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pillow_fight_job_tables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    table_config_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    insert_count INTEGER NOT NULL DEFAULT 0,
                    update_count INTEGER NOT NULL DEFAULT 0,
                    delete_count INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    last_operation_at TEXT,
                    resume_cursor TEXT,
                    FOREIGN KEY (job_id) REFERENCES pillow_fight_jobs (job_id) ON DELETE CASCADE,
                    FOREIGN KEY (table_config_id) REFERENCES table_configs (id) ON DELETE CASCADE
                )
                ''')

            # Ensure warning_message column exists on pillow_fight_jobs
            cursor.execute("PRAGMA table_info(pillow_fight_jobs)")
            job_columns = [column[1] for column in cursor.fetchall()]
            if 'warning_message' not in job_columns:
                logger.info("Adding warning_message column to pillow_fight_jobs table")
                cursor.execute('''
                    ALTER TABLE pillow_fight_jobs ADD COLUMN warning_message TEXT
                    ''')

            # Ensure warning_count column exists on pillow_fight_job_tables
            cursor.execute("PRAGMA table_info(pillow_fight_job_tables)")
            job_table_columns = [column[1] for column in cursor.fetchall()]
            if 'warning_count' not in job_table_columns:
                logger.info("Adding warning_count column to pillow_fight_job_tables table")
                cursor.execute('''
                    ALTER TABLE pillow_fight_job_tables ADD COLUMN warning_count INTEGER NOT NULL DEFAULT 0
                    ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_pillow_fight_job_tables_job 
                ON pillow_fight_job_tables(job_id)
                ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_pillow_fight_job_tables_table 
                ON pillow_fight_job_tables(table_config_id)
                ''')
                
            conn.commit()
            logger.info("All tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}", exc_info=True)
    
    def _initialize_database(self):
        """Create database schema using a temporary connection."""
        with self._temporary_connection() as conn:
            self._create_tables(conn)
    
    def _initialize_pool(self):
        """Pre-populate the connection pool."""
        for _ in range(self.pool_size):
            self._pool.put(self._create_connection())
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a configured SQLite connection."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=self.busy_timeout_ms / 1000.0,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms};")
        conn.commit()
        return conn
    
    @contextmanager
    def _temporary_connection(self):
        conn = self._create_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    def _acquire_connection(self) -> sqlite3.Connection:
        conn = self._pool.get()
        if conn is None:
            conn = self._create_connection()
        return conn
    
    def _release_connection(self, conn: sqlite3.Connection):
        try:
            self._pool.put(conn, block=False)
        except queue.Full:
            conn.close()
    
    @contextmanager
    def _connection(self):
        conn = self._acquire_connection()
        try:
            yield conn
        finally:
            self._release_connection(conn)
    
    def _with_retry(self, operation_name: str, func: Callable):
        attempts = 0
        delay = self.retry_base_delay
        while True:
            try:
                return func()
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if "database is locked" in message and attempts < self.retry_attempts:
                    attempts += 1
                    logger.warning(
                        "SQLite database is locked during %s (attempt %s/%s). Retrying in %.2fs",
                        operation_name,
                        attempts,
                        self.retry_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, self.retry_max_delay)
                    continue
                raise
    
    def execute(self, query, params=None):
        """Execute a query and return the last row id."""
        def op():
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()
                return cursor.lastrowid
        return self._with_retry("execute", op)
    
    def commit(self):
        """Commit the current transaction."""
        # SQLite auto-commits after each execute, so this is a no-op
        pass
    
    def query(self, query, params=None):
        """Execute a query and return all results as dictionaries."""
        def op():
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        return self._with_retry("query", op)
    
    def query_one(self, query, params=None):
        """Execute a query and return the first result as a dictionary."""
        logger.info(f"Executing query_one: {query} with params: {params}")
        def op():
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                row = cursor.fetchone()
                logger.info(f"Query result: {row}")
                if row:
                    columns = [col[0] for col in cursor.description]
                    result = dict(zip(columns, row))
                    logger.info(f"Returning result: {result}")
                    return result
                logger.info("No results found")
                return None
        try:
            return self._with_retry("query_one", op)
        except Exception as e:
            logger.error(f"Error executing query_one: {str(e)}", exc_info=True)
            return None
            
    def cursor(self):
        """Return a cursor for direct SQL operations.
        
        This method is used by the JDBC-only implementation to execute SQL queries directly.
        The cursor is wrapped to ensure proper connection management.
        """
        db = self
        
        class ManagedCursor:
            def __init__(self, database: "Database"):
                self._database = database
                self._conn_cm = database._connection()
                self.conn = self._conn_cm.__enter__()
                self.cursor = self.conn.cursor()
            
            def execute(self, query, params=None):
                return self.cursor.execute(query, params or ())
            
            def fetchall(self):
                return self.cursor.fetchall()
            
            def fetchone(self):
                return self.cursor.fetchone()
            
            def close(self):
                if self.cursor:
                    try:
                        self.cursor.close()
                    except Exception:
                        pass
                if self._conn_cm:
                    self._conn_cm.__exit__(None, None, None)
                    self._conn_cm = None
            
            def commit(self):
                self.conn.commit()
            
            @property
            def lastrowid(self):
                return self.cursor.lastrowid
            
            @property
            def description(self):
                return self.cursor.description
            
            def __del__(self):
                self.close()
        
        return ManagedCursor(db)
    
    def scalar(self, query, params=None):
        """Execute a query and return a single value."""
        def op():
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                row = cursor.fetchone()
                return row[0] if row else None
        return self._with_retry("scalar", op)

# Singleton database instance
_db = Database(settings.DB_URL)

def get_db():
    """Get the database connection."""
    return _db

def init_db():
    """Initialize the database."""
    # The database is already initialized when the singleton is created
    return _db
