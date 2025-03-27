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


class AS400SqlStatements(BaseSqlStatements):
    """IBM i Series (AS400)-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT SCHEMA_NAME
        FROM QSYS2.SYSSCHEMAS
        WHERE SCHEMA_NAME NOT LIKE 'Q%'
        AND SCHEMA_NAME NOT IN ('SYSTOOLS', 'SYSIBM', 'SYSIBMADM', 'SYSPROC', 'SYSPUBLIC')
        ORDER BY SCHEMA_NAME
        """
    
    def get_tables_statement(self, schema=None):
        if schema:
            # Use direct string substitution, not placeholders
            return f"""
            SELECT TABLE_NAME
            FROM QSYS2.SYSTABLES
            WHERE TABLE_SCHEMA = '{schema}'
            AND TABLE_TYPE = 'T'
            ORDER BY TABLE_NAME
            """
        else:
            return """
            SELECT TABLE_NAME
            FROM QSYS2.SYSTABLES
            WHERE TABLE_TYPE = 'T'
            ORDER BY TABLE_NAME
            """
    
    def get_columns_statement(self, schema=None, table=None):
        # AS400 doesn't support named parameters in JDBC, use direct string substitution
        if schema and table:
            return f"""
            SELECT 
                COLUMN_NAME,
                ORDINAL_POSITION,
                DATA_TYPE,
                LENGTH,
                NUMERIC_SCALE,
                COLUMN_TEXT,
                CASE WHEN IS_NULLABLE = 'Y' THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                COLUMN_DEFAULT,
                CASE WHEN HAS_DEFAULT = 'Y' THEN 1 ELSE 0 END AS HAS_DEFAULT,
                0 AS IS_PRIMARY_KEY  -- We'll detect primary keys in a separate query
            FROM QSYS2.SYSCOLUMNS C
            WHERE TABLE_SCHEMA = '{schema}'
            AND TABLE_NAME = '{table}'
            ORDER BY ORDINAL_POSITION
            """
        elif table:
            return f"""
            SELECT 
                COLUMN_NAME,
                ORDINAL_POSITION,
                DATA_TYPE,
                LENGTH,
                NUMERIC_SCALE,
                COLUMN_TEXT,
                CASE WHEN IS_NULLABLE = 'Y' THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                COLUMN_DEFAULT,
                CASE WHEN HAS_DEFAULT = 'Y' THEN 1 ELSE 0 END AS HAS_DEFAULT,
                0 AS IS_PRIMARY_KEY  -- We'll detect primary keys in a separate query
            FROM QSYS2.SYSCOLUMNS C
            WHERE TABLE_NAME = '{table}'
            ORDER BY ORDINAL_POSITION
            """
        else:
            # Return a valid SQL that will return empty result
            return """
            SELECT 
                COLUMN_NAME,
                ORDINAL_POSITION,
                DATA_TYPE,
                LENGTH,
                NUMERIC_SCALE,
                COLUMN_TEXT,
                CASE WHEN IS_NULLABLE = 'Y' THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                COLUMN_DEFAULT,
                CASE WHEN HAS_DEFAULT = 'Y' THEN 1 ELSE 0 END AS HAS_DEFAULT,
                0 AS IS_PRIMARY_KEY
            FROM QSYS2.SYSCOLUMNS
            WHERE 1=0
            """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        # AS400 doesn't support named parameters in JDBC, use direct string substitution
        # Use a simpler approach for AS400 primary keys with minimal column dependencies
        # This uses just COLUMN_NAME which is more consistently available across AS400 versions
        if schema and table:
            return f"""
            SELECT 
                K.COLUMN_NAME AS COLUMN_NAME
            FROM QSYS2.SYSCST K
            WHERE K.TABLE_SCHEMA = '{schema}'
            AND K.TABLE_NAME = '{table}'
            AND K.CONSTRAINT_TYPE = 'PRIMARY KEY'
            """
        elif table:
            return f"""
            SELECT 
                K.COLUMN_NAME AS COLUMN_NAME
            FROM QSYS2.SYSCST K
            WHERE K.TABLE_NAME = '{table}'
            AND K.CONSTRAINT_TYPE = 'PRIMARY KEY'
            """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        # AS400 doesn't support named parameters in JDBC, use direct string substitution
        # Use a simpler approach that doesn't rely on REFERENCED_COLUMN_NAME
        # Instead, just get the foreign key relationships, suitable for different AS400 versions
        if schema and table:
            return f"""
            SELECT 
                C.COLUMN_NAME AS COLUMN_NAME,
                R.PARENT_SCHEMA AS REFERENCED_TABLE_SCHEMA,
                R.PARENT_TABLE AS REFERENCED_TABLE_NAME
            FROM QSYS2.SYSCST C
            JOIN QSYS2.SYSREFCST R ON R.CONSTRAINT_SCHEMA = C.CONSTRAINT_SCHEMA 
                AND R.CONSTRAINT_NAME = C.CONSTRAINT_NAME
            WHERE C.TABLE_SCHEMA = '{schema}'
            AND C.TABLE_NAME = '{table}'
            AND C.CONSTRAINT_TYPE = 'FOREIGN KEY'
            """
        elif table:
            return f"""
            SELECT 
                DISTINCT C.COLUMN_NAME AS COLUMN_NAME,
                R.REFERENCED_TABLE_SCHEMA AS REFERENCED_TABLE_SCHEMA,
                R.REFERENCED_TABLE_NAME AS REFERENCED_TABLE_NAME,
                R.REFERENCED_COLUMN_NAME AS REFERENCED_COLUMN_NAME
            FROM QSYS2.SYSREFCST R
            JOIN QSYS2.SYSCST C ON R.CONSTRAINT_SCHEMA = C.CONSTRAINT_SCHEMA 
                AND R.CONSTRAINT_NAME = C.CONSTRAINT_NAME
            WHERE C.TABLE_NAME = '{table}'
            AND C.CONSTRAINT_TYPE = 'FOREIGN KEY'
            """
    
    def count_rows_statement(self, table, schema=None):
        # In AS400, tables must be qualified with their schema/library
        # or they won't be found in the default *LIBL
        if schema:
            # Fully qualify the table name with its schema
            return f"SELECT COUNT(*) AS count FROM {schema}.{table}"
        else:
            # Try to use the table name as-is, but this may fail if it's not in the library list
            return f"SELECT COUNT(*) AS count FROM {table}"
    
    def get_version_statement(self):
        return """
        SELECT OS_VERSION, OS_RELEASE
        FROM SYSIBMADM.ENV_SYS_INFO
        """
        
    def get_system_info(self):
        return """
        SELECT OS_VERSION, OS_RELEASE, HOST_NAME
        FROM SYSIBMADM.ENV_SYS_INFO
        """
        
    def get_active_jobs(self):
        return """
        SELECT JOB_NAME, AUTHORIZATION_NAME, SUBSYSTEM, JOB_TYPE
        FROM TABLE(QSYS2.ACTIVE_JOB_INFO()) AS A
        ORDER BY JOB_NAME
        LIMIT 50
        """
