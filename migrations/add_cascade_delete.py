#!/usr/bin/env python3
"""
Migration script to add cascade_delete column to table_configs table.
"""

import os
import sqlite3
import logging
import sys

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add cascade_delete column to table_configs table if it doesn't exist."""
    db_path = settings.DB_URL
    if db_path.startswith('sqlite:///'):
        db_path = db_path.replace('sqlite:///', '')
    
    logger.info(f"Running migration on database: {db_path}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the column exists
        cursor.execute("PRAGMA table_info(table_configs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'cascade_delete' not in columns:
            logger.info("Adding cascade_delete column to table_configs table")
            cursor.execute('''
            ALTER TABLE table_configs ADD COLUMN cascade_delete INTEGER NOT NULL DEFAULT 0
            ''')
            conn.commit()
            logger.info("Added cascade_delete column to table_configs table")
        else:
            logger.info("cascade_delete column already exists in table_configs table")
        
        conn.close()
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Error running migration: {str(e)}")
        raise

if __name__ == "__main__":
    run_migration()
