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


class OracleSqlStatements(BaseSqlStatements):
    """Oracle-specific SQL statements."""
    
    def get_schemas_statement(self):
        return """
        SELECT username AS schema_name
        FROM all_users
        WHERE username NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DIP', 
                              'ORACLE_OCM', 'DBSNMP', 'APPQOSSYS', 
                              'WMSYS', 'EXFSYS', 'CTXSYS', 'XDB', 
                              'ANONYMOUS', 'OLAPSYS', 'ORDDATA', 
                              'ORDPLUGINS', 'ORDSYS', 'MDSYS')
        ORDER BY username
        """
    
    def get_tables_statement(self, schema=None):
        if schema:
            return """
            SELECT table_name
            FROM all_tables
            WHERE owner = :schema
            ORDER BY table_name
            """
        else:
            return """
            SELECT table_name
            FROM all_tables
            ORDER BY table_name
            """
    
    def get_columns_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT
                column_name,
                column_id AS ordinal_position,
                data_type,
                data_length,
                data_precision,
                data_scale,
                CASE WHEN nullable = 'Y' THEN 'YES' ELSE 'NO' END AS is_nullable,
                CASE WHEN identity_column = 'YES' THEN 1 ELSE 0 END AS is_identity,
                data_default AS column_default,
                (SELECT CASE
                    WHEN EXISTS (
                        SELECT 1 FROM all_constraints ac 
                        JOIN all_cons_columns acc ON ac.constraint_name = acc.constraint_name
                        WHERE ac.constraint_type = 'P'
                        AND ac.owner = atc.owner
                        AND ac.table_name = atc.table_name
                        AND acc.column_name = atc.column_name
                    ) THEN 1
                    ELSE 0
                END FROM dual) AS is_primary_key
            FROM all_tab_columns atc
            WHERE owner = :schema
            AND table_name = :table
            ORDER BY column_id
            """
        else:
            return """
            SELECT
                column_name,
                column_id AS ordinal_position,
                data_type,
                data_length,
                data_precision,
                data_scale,
                CASE WHEN nullable = 'Y' THEN 'YES' ELSE 'NO' END AS is_nullable,
                CASE WHEN identity_column = 'YES' THEN 1 ELSE 0 END AS is_identity,
                data_default AS column_default,
                (SELECT CASE
                    WHEN EXISTS (
                        SELECT 1 FROM all_constraints ac 
                        JOIN all_cons_columns acc ON ac.constraint_name = acc.constraint_name
                        WHERE ac.constraint_type = 'P'
                        AND ac.table_name = atc.table_name
                        AND acc.column_name = atc.column_name
                    ) THEN 1
                    ELSE 0
                END FROM dual) AS is_primary_key
            FROM all_tab_columns atc
            WHERE table_name = :table
            ORDER BY column_id
            """
    
    def get_primary_keys_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT
                acc.column_name
            FROM
                all_constraints ac
                JOIN all_cons_columns acc ON ac.constraint_name = acc.constraint_name
                                        AND ac.owner = acc.owner
            WHERE ac.constraint_type = 'P'
                AND ac.owner = :schema
                AND ac.table_name = :table
            ORDER BY acc.position
            """
        else:
            return """
            SELECT
                acc.column_name
            FROM
                all_constraints ac
                JOIN all_cons_columns acc ON ac.constraint_name = acc.constraint_name
            WHERE ac.constraint_type = 'P'
                AND ac.table_name = :table
            ORDER BY acc.position
            """
    
    def get_foreign_keys_statement(self, schema=None, table=None):
        if schema:
            return """
            SELECT
                acc1.column_name AS column_name,
                ac.r_owner AS referenced_table_schema,
                ac.r_constraint_name AS referenced_constraint_name,
                acc2.table_name AS referenced_table_name,
                acc2.column_name AS referenced_column_name
            FROM
                all_constraints ac
                JOIN all_cons_columns acc1 ON ac.constraint_name = acc1.constraint_name
                                          AND ac.owner = acc1.owner
                JOIN all_cons_columns acc2 ON ac.r_constraint_name = acc2.constraint_name
                                          AND ac.r_owner = acc2.owner
                                          AND acc1.position = acc2.position
            WHERE ac.constraint_type = 'R'
                AND ac.owner = :schema
                AND ac.table_name = :table
            ORDER BY acc1.position
            """
        else:
            return """
            SELECT
                acc1.column_name AS column_name,
                ac.r_owner AS referenced_table_schema,
                ac.r_constraint_name AS referenced_constraint_name,
                acc2.table_name AS referenced_table_name,
                acc2.column_name AS referenced_column_name
            FROM
                all_constraints ac
                JOIN all_cons_columns acc1 ON ac.constraint_name = acc1.constraint_name
                JOIN all_cons_columns acc2 ON ac.r_constraint_name = acc2.constraint_name
                                          AND acc1.position = acc2.position
            WHERE ac.constraint_type = 'R'
                AND ac.table_name = :table
            ORDER BY acc1.position
            """
    
    def count_rows_statement(self, table):
        return f"SELECT COUNT(*) AS count FROM {table}"
    
    def get_version_statement(self):
        return "SELECT BANNER AS version FROM V$VERSION WHERE BANNER LIKE 'Oracle%'"
