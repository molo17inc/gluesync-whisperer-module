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


class MsSqlSqlStatements(BaseSqlStatements):
    """Microsoft SQL Server-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT schema_name
        FROM information_schema.schemata
        ORDER BY schema_name
        """
    
    def get_tables_statement(self, schema=None):
        if schema:
            return """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = ?
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        else:
            return """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            ORDER BY table_name
            """
    
    def get_columns_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT
                C.COLUMN_NAME,
                C.ORDINAL_POSITION,
                C.DATA_TYPE,
                C.CHARACTER_MAXIMUM_LENGTH,
                C.CHARACTER_OCTET_LENGTH,
                C.CHARACTER_SET_NAME,
                C.NUMERIC_PRECISION,
                C.NUMERIC_PRECISION_RADIX,
                C.NUMERIC_SCALE,
                C.DATETIME_PRECISION,
                C.IS_NULLABLE,
                C.COLUMN_DEFAULT,
                COLUMNPROPERTY(OBJECT_ID(C.TABLE_SCHEMA + '.' + C.TABLE_NAME), C.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY,
                IIF(K.COLUMN_NAME IS NOT NULL, 1, 0) AS IS_PRIMARY_KEY
            FROM INFORMATION_SCHEMA.COLUMNS AS C
            LEFT JOIN (
                SELECT KCU.COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU
                INNER JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
                    ON TC.TABLE_SCHEMA = KCU.TABLE_SCHEMA
                       AND TC.TABLE_NAME = KCU.TABLE_NAME
                       AND TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
                WHERE KCU.TABLE_SCHEMA = ?
                    AND KCU.TABLE_NAME = ?
                    AND TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
                GROUP BY KCU.COLUMN_NAME
            ) AS K ON K.COLUMN_NAME = C.COLUMN_NAME
            WHERE C.TABLE_SCHEMA = ?
               AND C.TABLE_NAME = ?
            ORDER BY C.ORDINAL_POSITION
            """
        else:
            return """
            SELECT
                C.COLUMN_NAME,
                C.ORDINAL_POSITION,
                C.DATA_TYPE,
                C.CHARACTER_MAXIMUM_LENGTH,
                C.CHARACTER_OCTET_LENGTH,
                C.CHARACTER_SET_NAME,
                C.NUMERIC_PRECISION,
                C.NUMERIC_PRECISION_RADIX,
                C.NUMERIC_SCALE,
                C.DATETIME_PRECISION,
                C.IS_NULLABLE,
                C.COLUMN_DEFAULT,
                COLUMNPROPERTY(OBJECT_ID(C.TABLE_SCHEMA + '.' + C.TABLE_NAME), C.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY,
                IIF(K.COLUMN_NAME IS NOT NULL, 1, 0) AS IS_PRIMARY_KEY
            FROM INFORMATION_SCHEMA.COLUMNS AS C
            LEFT JOIN (
                SELECT KCU.COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU
                INNER JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
                    ON TC.TABLE_SCHEMA = KCU.TABLE_SCHEMA
                       AND TC.TABLE_NAME = KCU.TABLE_NAME
                       AND TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
                WHERE KCU.TABLE_NAME = ?
                    AND TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
                GROUP BY KCU.COLUMN_NAME
            ) AS K ON K.COLUMN_NAME = C.COLUMN_NAME
            WHERE C.TABLE_NAME = ?
            ORDER BY C.ORDINAL_POSITION
            """
    
    def get_table_schema_statement(self, schema=None):
        """Get the SQL statement for retrieving a table's schema.
        
        Args:
            schema: Optional schema name
            
        Returns:
            SQL statement for retrieving table schema
        """
        if schema:
            return """
            SELECT 
                c.column_name,
                c.ordinal_position,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.datetime_precision,
                c.is_nullable,
                COLUMNPROPERTY(OBJECT_ID(c.table_schema + '.' + c.table_name), c.column_name, 'IsIdentity') AS is_identity,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT 
                    ku.table_schema,
                    ku.table_name,
                    ku.column_name
                FROM
                    information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS ku
                        ON tc.constraint_name = ku.constraint_name
                        AND tc.table_schema = ku.table_schema
                        AND tc.table_name = ku.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.table_schema = pk.table_schema
                AND c.table_name = pk.table_name
                AND c.column_name = pk.column_name
            WHERE c.table_schema = ?
                AND c.table_name = ?
            ORDER BY c.ordinal_position
            """
        else:
            return """
            SELECT 
                c.column_name,
                c.ordinal_position,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.datetime_precision,
                c.is_nullable,
                COLUMNPROPERTY(OBJECT_ID(c.table_schema + '.' + c.table_name), c.column_name, 'IsIdentity') AS is_identity,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT 
                    ku.table_schema,
                    ku.table_name,
                    ku.column_name
                FROM
                    information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS ku
                        ON tc.constraint_name = ku.constraint_name
                        AND tc.table_schema = ku.table_schema
                        AND tc.table_name = ku.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.table_schema = pk.table_schema
                AND c.table_name = pk.table_name
                AND c.column_name = pk.column_name
            WHERE c.table_name = ?
            ORDER BY c.ordinal_position
            """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT 
                ku.column_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.table_schema = ku.table_schema
                    AND tc.table_name = ku.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = ?
                AND tc.table_name = ?
            ORDER BY ku.ordinal_position
            """
        else:
            return """
            SELECT 
                ku.column_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.table_name = ku.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name = ?
            ORDER BY ku.ordinal_position
            """
    
    def get_primary_keys_statement_sys(self, schema=None, table=None):
        """Get primary keys using sys catalog views for better compatibility with MS SQL Server.
        
        This is an alternative method to get primary keys when the information_schema approach fails.
        """
        return """
        SELECT 
            c.name AS column_name
        FROM 
            sys.indexes i
        INNER JOIN 
            sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        INNER JOIN 
            sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        INNER JOIN 
            sys.tables t ON i.object_id = t.object_id
        INNER JOIN 
            sys.schemas s ON t.schema_id = s.schema_id
        WHERE 
            i.is_primary_key = 1
            AND t.name = ?
            AND s.name = ?
        ORDER BY 
            ic.key_ordinal
        """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT
                kcu1.column_name AS column_name,
                kcu2.table_schema AS referenced_table_schema,
                kcu2.table_name AS referenced_table_name,
                kcu2.column_name AS referenced_column_name
            FROM information_schema.referential_constraints AS rc
            JOIN information_schema.key_column_usage AS kcu1
                ON kcu1.constraint_catalog = rc.constraint_catalog
                AND kcu1.constraint_schema = rc.constraint_schema
                AND kcu1.constraint_name = rc.constraint_name
            JOIN information_schema.key_column_usage AS kcu2
                ON kcu2.constraint_catalog = rc.unique_constraint_catalog
                AND kcu2.constraint_schema = rc.unique_constraint_schema
                AND kcu2.constraint_name = rc.unique_constraint_name
                AND kcu2.ordinal_position = kcu1.ordinal_position
            WHERE kcu1.table_schema = ?
                AND kcu1.table_name = ?
            """
        else:
            return """
            SELECT
                kcu1.column_name AS column_name,
                kcu2.table_schema AS referenced_table_schema,
                kcu2.table_name AS referenced_table_name,
                kcu2.column_name AS referenced_column_name
            FROM information_schema.referential_constraints AS rc
            JOIN information_schema.key_column_usage AS kcu1
                ON kcu1.constraint_catalog = rc.constraint_catalog
                AND kcu1.constraint_schema = rc.constraint_schema
                AND kcu1.constraint_name = rc.constraint_name
            JOIN information_schema.key_column_usage AS kcu2
                ON kcu2.constraint_catalog = rc.unique_constraint_catalog
                AND kcu2.constraint_schema = rc.unique_constraint_schema
                AND kcu2.constraint_name = rc.unique_constraint_name
                AND kcu2.ordinal_position = kcu1.ordinal_position
            WHERE kcu1.table_name = ?
            """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(*) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT @@VERSION AS version"
        
    # This is a fallback method for systems where INFORMATION_SCHEMA doesn't work properly
    def get_primary_keys_statement_sys(self, schema, table_name):
        """Return a SQL statement to get primary keys for a table using sys catalog views."""
        return """
        SELECT c.name as COLUMN_NAME
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE i.is_primary_key = 1
        AND t.name = ?
        AND s.name = ?
        ORDER BY ic.key_ordinal
        """


# Create alias for compatibility with both naming conventions
MSSQLSqlStatements = MsSqlSqlStatements
