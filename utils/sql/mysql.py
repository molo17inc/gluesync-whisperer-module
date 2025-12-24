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


class MySqlSqlStatements(BaseSqlStatements):
    """MySQL-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT SCHEMA_NAME
        FROM INFORMATION_SCHEMA.SCHEMATA
        """
    
    def get_tables_statement(self, schema=None):
        if schema:
            return f"""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = '{schema}'
            """
        else:
            return """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
            """
    
    def get_columns_statement(self, schema=None, table=None):
        return """
        SELECT
            C.COLUMN_NAME,
            C.ORDINAL_POSITION,
            C.DATA_TYPE,
            C.CHARACTER_MAXIMUM_LENGTH,
            C.CHARACTER_OCTET_LENGTH,
            C.CHARACTER_SET_NAME,
            C.NUMERIC_PRECISION,
            C.NUMERIC_SCALE,
            C.DATETIME_PRECISION,
            C.COLUMN_TYPE,
            C.COLUMN_KEY,
            C.EXTRA,
            CASE
               WHEN TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
               THEN 1
               ELSE 0
            END AS IS_PRIMARY_KEY,
            C.IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS AS C
            LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KCU
                ON KCU.TABLE_SCHEMA = C.TABLE_SCHEMA
                   AND KCU.TABLE_NAME = C.TABLE_NAME
                   AND KCU.COLUMN_NAME = C.COLUMN_NAME
            LEFT JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
                ON TC.TABLE_SCHEMA = KCU.TABLE_SCHEMA
                   AND TC.TABLE_NAME = KCU.TABLE_NAME
                   AND TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
        WHERE C.TABLE_SCHEMA = ?
           AND C.TABLE_NAME = ?
        ORDER BY C.ORDINAL_POSITION
        """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        return """
        SELECT 
            KCU.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS TC
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KCU
            ON TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
            AND TC.TABLE_SCHEMA = KCU.TABLE_SCHEMA
            AND TC.TABLE_NAME = KCU.TABLE_NAME
        WHERE TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND TC.TABLE_SCHEMA = ?
            AND TC.TABLE_NAME = ?
        ORDER BY KCU.ORDINAL_POSITION
        """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        return """
        SELECT
            KCU.COLUMN_NAME,
            KCU.REFERENCED_TABLE_SCHEMA,
            KCU.REFERENCED_TABLE_NAME,
            KCU.REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KCU
        JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS TC
            ON TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
            AND TC.TABLE_SCHEMA = KCU.TABLE_SCHEMA
            AND TC.TABLE_NAME = KCU.TABLE_NAME
        WHERE KCU.REFERENCED_TABLE_NAME IS NOT NULL
            AND TC.CONSTRAINT_TYPE = 'FOREIGN KEY'
            AND KCU.TABLE_SCHEMA = ?
            AND KCU.TABLE_NAME = ?
        """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(*) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT VERSION() AS version"
    
    def get_show_tables(self):
        return "SHOW TABLES"
    
    def get_describe_table(self, table):
        return f"DESCRIBE {table}"
