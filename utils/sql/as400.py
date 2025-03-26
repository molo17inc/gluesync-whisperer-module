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
            return """
            SELECT TABLE_NAME
            FROM QSYS2.SYSTABLES
            WHERE TABLE_SCHEMA = :schema
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
        if schema:
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
                CASE 
                    WHEN (
                        SELECT COUNT(*) 
                        FROM QSYS2.SYSKEYS K
                        JOIN QSYS2.SYSKEYCST KC ON K.CONSTRAINT_NAME = KC.CONSTRAINT_NAME
                        WHERE K.TABLE_SCHEMA = C.TABLE_SCHEMA
                        AND K.TABLE_NAME = C.TABLE_NAME
                        AND KC.COLUMN_NAME = C.COLUMN_NAME
                        AND K.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    ) > 0 THEN 1
                    ELSE 0
                END AS IS_PRIMARY_KEY
            FROM QSYS2.SYSCOLUMNS C
            WHERE TABLE_SCHEMA = :schema
            AND TABLE_NAME = :table
            ORDER BY ORDINAL_POSITION
            """
        else:
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
                CASE 
                    WHEN (
                        SELECT COUNT(*) 
                        FROM QSYS2.SYSKEYS K
                        JOIN QSYS2.SYSKEYCST KC ON K.CONSTRAINT_NAME = KC.CONSTRAINT_NAME
                        WHERE K.TABLE_NAME = C.TABLE_NAME
                        AND KC.COLUMN_NAME = C.COLUMN_NAME
                        AND K.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    ) > 0 THEN 1
                    ELSE 0
                END AS IS_PRIMARY_KEY
            FROM QSYS2.SYSCOLUMNS C
            WHERE TABLE_NAME = :table
            ORDER BY ORDINAL_POSITION
            """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT 
                KC.COLUMN_NAME
            FROM QSYS2.SYSKEYS K
            JOIN QSYS2.SYSKEYCST KC ON K.CONSTRAINT_NAME = KC.CONSTRAINT_NAME
            WHERE K.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND K.TABLE_SCHEMA = :schema
            AND K.TABLE_NAME = :table
            ORDER BY KC.ORDINAL_POSITION
            """
        else:
            return """
            SELECT 
                KC.COLUMN_NAME
            FROM QSYS2.SYSKEYS K
            JOIN QSYS2.SYSKEYCST KC ON K.CONSTRAINT_NAME = KC.CONSTRAINT_NAME
            WHERE K.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND K.TABLE_NAME = :table
            ORDER BY KC.ORDINAL_POSITION
            """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT 
                CU.COLUMN_NAME,
                R.UNIQUE_CONSTRAINT_SCHEMA AS REFERENCED_TABLE_SCHEMA,
                R.REFERENCED_TABLE_NAME,
                R.REFERENCED_COLUMN_NAME
            FROM QSYS2.SYSREFCST R
            JOIN QSYS2.SYSCST C ON R.CONSTRAINT_NAME = C.CONSTRAINT_NAME
            JOIN QSYS2.SYSCSTCOL CU ON C.CONSTRAINT_NAME = CU.CONSTRAINT_NAME
            WHERE C.CONSTRAINT_TYPE = 'FOREIGN KEY'
            AND C.TABLE_SCHEMA = :schema
            AND C.TABLE_NAME = :table
            """
        else:
            return """
            SELECT 
                CU.COLUMN_NAME,
                R.UNIQUE_CONSTRAINT_SCHEMA AS REFERENCED_TABLE_SCHEMA,
                R.REFERENCED_TABLE_NAME,
                R.REFERENCED_COLUMN_NAME
            FROM QSYS2.SYSREFCST R
            JOIN QSYS2.SYSCST C ON R.CONSTRAINT_NAME = C.CONSTRAINT_NAME
            JOIN QSYS2.SYSCSTCOL CU ON C.CONSTRAINT_NAME = CU.CONSTRAINT_NAME
            WHERE C.CONSTRAINT_TYPE = 'FOREIGN KEY'
            AND C.TABLE_NAME = :table
            """
    
    def count_rows_statement(self, table):
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
