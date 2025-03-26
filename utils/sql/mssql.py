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
            WHERE table_schema = :schema
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
            WHERE c.table_schema = :schema
                AND c.table_name = :table
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
            WHERE c.table_name = :table
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
                AND tc.table_schema = :schema
                AND tc.table_name = :table
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
            WHERE kcu1.table_schema = :schema
                AND kcu1.table_name = :table
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
            WHERE kcu1.table_name = :table
            """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(*) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT @@VERSION AS version"
