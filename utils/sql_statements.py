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

import logging
from abc import ABC, abstractmethod
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType

logger = logging.getLogger(__name__)

class BaseSqlStatements(ABC):
    """Base class for database-specific SQL statements."""

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


class MySqlSqlStatements(BaseSqlStatements):
    """MySQL-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT SCHEMA_NAME
        FROM INFORMATION_SCHEMA.SCHEMATA
        """
    
    def get_tables_statement(self, schema=None):
        return """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
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
        return f"SELECT COUNT(1) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT VERSION() AS version"
    
    def get_show_tables(self):
        return "SHOW TABLES"
    
    def get_describe_table(self, table):
        return f"DESCRIBE {table}"


class PostgreSqlSqlStatements(BaseSqlStatements):
    """PostgreSQL-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schema_name
        """
    
    def get_tables_statement(self, schema=None):
        return """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = ?
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    
    def get_columns_statement(self, schema=None, table=None):
        return """
        SELECT
            c.column_name,
            c.ordinal_position,
            c.data_type,
            c.character_maximum_length,
            c.character_octet_length,
            c.numeric_precision,
            c.numeric_scale,
            c.datetime_precision,
            c.is_nullable,
            CASE WHEN pk.constraint_type = 'PRIMARY KEY' THEN 1 ELSE 0 END AS is_primary_key,
            c.column_default,
            c.udt_name
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT
                tc.constraint_type,
                kcu.table_schema,
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk 
            ON pk.table_schema = c.table_schema
            AND pk.table_name = c.table_name
            AND pk.column_name = c.column_name
        WHERE c.table_schema = ?
        AND c.table_name = ?
        ORDER BY c.ordinal_position
        """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        return """
        SELECT
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
            AND tc.table_name = kcu.table_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = ?
            AND tc.table_name = ?
        ORDER BY kcu.ordinal_position
        """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        return """
        SELECT
            kcu.column_name,
            ccu.table_schema AS referenced_table_schema,
            ccu.table_name AS referenced_table_name,
            ccu.column_name AS referenced_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
            AND tc.table_name = kcu.table_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = ?
            AND tc.table_name = ?
        """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(1) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT version() AS version"


class MsSqlSqlStatements(BaseSqlStatements):
    """Microsoft SQL Server-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT SCHEMA_NAME
        FROM INFORMATION_SCHEMA.SCHEMATA
        """
    
    def get_tables_statement(self, schema=None):
        return """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
        AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
    
    def get_columns_statement(self, schema=None, table=None):
        return """
        SELECT 
            c.COLUMN_NAME,
            c.ORDINAL_POSITION,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.CHARACTER_OCTET_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.DATETIME_PRECISION,
            c.IS_NULLABLE,
            COLUMNPROPERTY(OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS is_identity,
            CASE WHEN pk.CONSTRAINT_TYPE = 'PRIMARY KEY' THEN 1 ELSE 0 END AS is_primary_key,
            c.COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN (
            SELECT 
                tc.CONSTRAINT_TYPE,
                kcu.TABLE_SCHEMA,
                kcu.TABLE_NAME,
                kcu.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu 
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                AND tc.TABLE_NAME = kcu.TABLE_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ) pk 
            ON pk.TABLE_SCHEMA = c.TABLE_SCHEMA
            AND pk.TABLE_NAME = c.TABLE_NAME
            AND pk.COLUMN_NAME = c.COLUMN_NAME
        WHERE c.TABLE_SCHEMA = ?
        AND c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
        """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        return """
        SELECT 
            kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu 
            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
            AND tc.TABLE_NAME = kcu.TABLE_NAME
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND tc.TABLE_SCHEMA = ?
            AND tc.TABLE_NAME = ?
        ORDER BY kcu.ORDINAL_POSITION
        """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        return """
        SELECT
            kcu1.COLUMN_NAME,
            kcu2.TABLE_SCHEMA AS referenced_table_schema,
            kcu2.TABLE_NAME AS referenced_table_name,
            kcu2.COLUMN_NAME AS referenced_column_name
        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu1
            ON kcu1.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            AND kcu1.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2
            ON kcu2.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME
            AND kcu2.CONSTRAINT_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA
        WHERE kcu1.TABLE_SCHEMA = ?
            AND kcu1.TABLE_NAME = ?
        """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(1) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT @@VERSION AS version"


class OracleSqlStatements(BaseSqlStatements):
    """Oracle-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT username AS schema_name
        FROM all_users
        ORDER BY username
        """
    
    def get_tables_statement(self, schema=None):
        return """
        SELECT table_name 
        FROM all_tables 
        WHERE owner = :schema
        ORDER BY table_name
        """
    
    def get_columns_statement(self, schema=None, table=None):
        return """
        SELECT
            c.column_name,
            c.column_id AS ordinal_position,
            c.data_type,
            c.char_length AS character_maximum_length,
            c.char_used AS character_octet_length,
            c.data_precision AS numeric_precision,
            c.data_scale AS numeric_scale,
            CASE WHEN c.nullable = 'Y' THEN 'YES' ELSE 'NO' END AS is_nullable,
            CASE WHEN pk.constraint_type = 'P' THEN 1 ELSE 0 END AS is_primary_key,
            c.data_default AS column_default,
            c.data_length
        FROM all_tab_columns c
        LEFT JOIN (
            SELECT 
                ac.owner,
                ac.table_name,
                ac.column_name,
                ac.constraint_name,
                ac.position,
                tc.constraint_type
            FROM all_cons_columns ac
            JOIN all_constraints tc
                ON ac.owner = tc.owner
                AND ac.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'P'
        ) pk 
            ON pk.owner = c.owner
            AND pk.table_name = c.table_name
            AND pk.column_name = c.column_name
        WHERE c.owner = :schema
            AND c.table_name = :table
        ORDER BY c.column_id
        """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        return """
        SELECT 
            acc.column_name
        FROM all_constraints ac
        JOIN all_cons_columns acc
            ON ac.owner = acc.owner
            AND ac.constraint_name = acc.constraint_name
        WHERE ac.constraint_type = 'P'
            AND ac.owner = :schema
            AND ac.table_name = :table
        ORDER BY acc.position
        """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        return """
        SELECT
            acc.column_name,
            ac.r_owner AS referenced_table_schema,
            ac.r_constraint_name AS referenced_constraint_name,
            r_acc.column_name AS referenced_column_name,
            r_ac.table_name AS referenced_table_name
        FROM all_constraints ac
        JOIN all_cons_columns acc
            ON ac.owner = acc.owner
            AND ac.constraint_name = acc.constraint_name
        JOIN all_constraints r_ac
            ON ac.r_owner = r_ac.owner
            AND ac.r_constraint_name = r_ac.constraint_name
        JOIN all_cons_columns r_acc
            ON r_ac.owner = r_acc.owner
            AND r_ac.constraint_name = r_acc.constraint_name
            AND acc.position = r_acc.position
        WHERE ac.constraint_type = 'R'
            AND ac.owner = :schema
            AND ac.table_name = :table
        """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(1) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT BANNER AS version FROM v$version WHERE BANNER LIKE 'Oracle%'"


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


class AS400SqlStatements(BaseSqlStatements):
    """IBM i Series (AS400) specific SQL statements."""
    
    def get_schemas_statement(self):
        # In IBM i, schemas are called libraries
        return """
        SELECT SCHEMA_NAME AS schema_name
        FROM SYSIBM.SQLSCHEMAS
        WHERE SCHEMA_NAME NOT LIKE 'SYS%'
          AND SCHEMA_NAME NOT LIKE 'Q%'
        ORDER BY SCHEMA_NAME
        """
    
    def get_tables_statement(self, schema=None):
        # In IBM i, tables are in libraries (schemas)
        if schema:
            return """
            SELECT TABLE_NAME as table_name
            FROM SYSIBM.TABLES 
            WHERE TABLE_SCHEMA = ? 
              AND TABLE_TYPE = 'TABLE'
            ORDER BY TABLE_NAME
            """
        else:
            return """
            SELECT TABLE_NAME as table_name
            FROM SYSIBM.TABLES 
            WHERE TABLE_TYPE = 'TABLE'
            ORDER BY TABLE_NAME
            """
    
    def get_columns_statement(self, schema=None, table=None):
        if not table:
            raise ValueError("Table name is required for IBM i column query")
            
        if schema:
            return """
            SELECT 
                COLUMN_NAME as column_name,
                ORDINAL_POSITION as ordinal_position,
                DATA_TYPE as data_type,
                LENGTH as character_maximum_length,
                NUMERIC_SCALE as numeric_scale,
                CASE WHEN IS_NULLABLE = 'Y' THEN 'YES' ELSE 'NO' END as is_nullable,
                CASE WHEN IS_IDENTITY = 'Y' THEN 1 ELSE 0 END as is_identity,
                COLUMN_DEFAULT as column_default,
                COLUMN_TEXT as column_comment
            FROM QSYS2.SYSCOLUMNS
            WHERE TABLE_SCHEMA = ? 
              AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """
        else:
            return """
            SELECT 
                COLUMN_NAME as column_name,
                ORDINAL_POSITION as ordinal_position,
                DATA_TYPE as data_type,
                LENGTH as character_maximum_length,
                NUMERIC_SCALE as numeric_scale,
                CASE WHEN IS_NULLABLE = 'Y' THEN 'YES' ELSE 'NO' END as is_nullable,
                CASE WHEN IS_IDENTITY = 'Y' THEN 1 ELSE 0 END as is_identity,
                COLUMN_DEFAULT as column_default,
                COLUMN_TEXT as column_comment
            FROM QSYS2.SYSCOLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        if not table:
            raise ValueError("Table name is required for IBM i primary key query")
            
        if schema:
            return """
            SELECT 
                COLUMN_NAME as column_name
            FROM QSYS2.SYSKEYS
            JOIN QSYS2.SYSCST ON 
                QSYS2.SYSKEYS.CONSTRAINT_NAME = QSYS2.SYSCST.CONSTRAINT_NAME AND
                QSYS2.SYSKEYS.TABLE_SCHEMA = QSYS2.SYSCST.TABLE_SCHEMA AND
                QSYS2.SYSKEYS.TABLE_NAME = QSYS2.SYSCST.TABLE_NAME
            WHERE QSYS2.SYSCST.CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND QSYS2.SYSKEYS.TABLE_SCHEMA = ?
                AND QSYS2.SYSKEYS.TABLE_NAME = ?
            ORDER BY QSYS2.SYSKEYS.ORDINAL_POSITION
            """
        else:
            return """
            SELECT 
                COLUMN_NAME as column_name
            FROM QSYS2.SYSKEYS
            JOIN QSYS2.SYSCST ON 
                QSYS2.SYSKEYS.CONSTRAINT_NAME = QSYS2.SYSCST.CONSTRAINT_NAME AND
                QSYS2.SYSKEYS.TABLE_NAME = QSYS2.SYSCST.TABLE_NAME
            WHERE QSYS2.SYSCST.CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND QSYS2.SYSKEYS.TABLE_NAME = ?
            ORDER BY QSYS2.SYSKEYS.ORDINAL_POSITION
            """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        if not table:
            raise ValueError("Table name is required for IBM i foreign key query")
            
        if schema:
            return """
            SELECT 
                k.COLUMN_NAME as column_name,
                r.TABLE_SCHEMA as referenced_table_schema,
                r.TABLE_NAME as referenced_table_name,
                r.COLUMN_NAME as referenced_column_name
            FROM QSYS2.SYSREFCST as c
            JOIN QSYS2.SYSKEYS as k ON 
                c.CONSTRAINT_NAME = k.CONSTRAINT_NAME AND
                c.TABLE_SCHEMA = k.TABLE_SCHEMA AND
                c.TABLE_NAME = k.TABLE_NAME
            JOIN QSYS2.SYSKEYS as r ON 
                c.UNIQUE_CONSTRAINT_NAME = r.CONSTRAINT_NAME
            WHERE c.TABLE_SCHEMA = ?
                AND c.TABLE_NAME = ?
            """
        else:
            return """
            SELECT 
                k.COLUMN_NAME as column_name,
                r.TABLE_SCHEMA as referenced_table_schema,
                r.TABLE_NAME as referenced_table_name,
                r.COLUMN_NAME as referenced_column_name
            FROM QSYS2.SYSREFCST as c
            JOIN QSYS2.SYSKEYS as k ON 
                c.CONSTRAINT_NAME = k.CONSTRAINT_NAME AND
                c.TABLE_NAME = k.TABLE_NAME
            JOIN QSYS2.SYSKEYS as r ON 
                c.UNIQUE_CONSTRAINT_NAME = r.CONSTRAINT_NAME
            WHERE c.TABLE_NAME = ?
            """
    
    def count_rows_statement(self, table):
        # For most tables, a simple COUNT(*) works
        # For IBM i, we might need to handle qualified table names (LIBRARY.TABLE)
        if '.' in table:
            # Table name is already qualified
            return f"SELECT COUNT(*) AS count FROM {table}"
        else:
            # Use unqualified table name
            return f"SELECT COUNT(*) AS count FROM {table}"
    
    def get_version_statement(self):
        # IBM i returns version information in a special system view
        return """
        SELECT OS_VERSION as version,
               OS_RELEASE as release
        FROM SYSIBMADM.ENV_SYS_INFO
        """


def get_sql_statements(db_type):
    """Get the appropriate SQL statements class based on database type."""
    if db_type == DatabaseType.MYSQL:
        return MySqlSqlStatements()
    elif db_type == DatabaseType.POSTGRESQL:
        return PostgreSqlSqlStatements()
    elif db_type == DatabaseType.SQLITE:
        return SqliteSqlStatements()
    elif db_type == DatabaseType.MSSQL:
        return MsSqlSqlStatements()
    elif db_type == DatabaseType.ORACLE:
        return OracleSqlStatements()
    elif db_type == DatabaseType.AS400:
        return AS400SqlStatements()
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
