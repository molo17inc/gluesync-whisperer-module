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

from abc import ABC, abstractmethod


class BaseSqlStatements(ABC):
    """Base abstract class for database-specific SQL statements.
    
    This class defines the interface that all database-specific SQL statement
    classes must implement.
    """

    @abstractmethod
    def get_schemas_statement(self):
        """Get SQL statement to retrieve database schemas."""
        pass

    @abstractmethod
    def get_tables_statement(self, schema=None):
        """Get SQL statement to retrieve tables from a schema."""
        pass

    @abstractmethod
    def get_columns_statement(self, schema=None, table=None):
        """Get SQL statement to retrieve column definitions for a table."""
        pass

    @abstractmethod
    def get_primary_keys_statement(self, schema=None, table=None):
        """Get SQL statement to retrieve primary keys for a table."""
        pass
    
    @abstractmethod
    def get_foreign_keys_statement(self, schema=None, table=None):
        """Get SQL statement to retrieve foreign keys for a table."""
        pass
    
    @abstractmethod
    def count_rows_statement(self, table):
        """Get SQL statement to count rows in a table."""
        pass
    
    @abstractmethod
    def get_version_statement(self):
        """Get SQL statement to retrieve database version."""
        pass
