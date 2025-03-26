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

from utils.sql.base import BaseSqlStatements


class SqliteSqlStatements(BaseSqlStatements):
    """SQLite-specific SQL statements."""
    
    def get_schemas_statement(self):
        # SQLite doesn't have schemas in the traditional sense
        return "SELECT 'main' AS schema_name"
    
    def get_tables_statement(self, schema=None):
        return """
        SELECT name AS table_name
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    
    def get_columns_statement(self, schema=None, table=None):
        # SQLite doesn't have a built-in way to query column information from information_schema
        # We use PRAGMA table_info instead
        return f"PRAGMA table_info({table})"
    
    def get_primary_keys_statement(self, schema=None, table=None):
        # This information is included in the PRAGMA table_info query
        # We'll filter it out in the processor
        return f"PRAGMA table_info({table})"
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        return f"PRAGMA foreign_key_list({table})"
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(1) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT sqlite_version() AS version"
