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

from models import DatabaseType
from utils.sql.mysql import MySqlSqlStatements
from utils.sql.postgresql import PostgreSqlSqlStatements
from utils.sql.sqlite import SqliteSqlStatements
from utils.sql.mssql import MsSqlSqlStatements
from utils.sql.oracle import OracleSqlStatements
from utils.sql.as400 import AS400SqlStatements


def get_sql_statements(database_type):
    """
    Factory function to get the appropriate SQL statements implementation
    based on the database type.
    
    Args:
        database_type (DatabaseType): The type of database
        
    Returns:
        BaseSqlStatements: An instance of a class that implements BaseSqlStatements
        
    Raises:
        ValueError: If the database type is not supported
    """
def get_sql_statements(database_type):
    """
    Factory function to get the appropriate SQL statements implementation
    based on the database type.
    
    Args:
        database_type (DatabaseType): The type of database
        
    Returns:
        BaseSqlStatements: An instance of a class that implements BaseSqlStatements
        
    Raises:
        ValueError: If the database type is not supported
    """
    if database_type == DatabaseType.MYSQL:
        return MySqlSqlStatements()
    elif database_type == DatabaseType.MARIADB:
        # MariaDB shares the same metadata/catalog structure as MySQL
        return MySqlSqlStatements()
    elif database_type == DatabaseType.POSTGRESQL:
        return PostgreSqlSqlStatements()
    elif database_type == DatabaseType.SQLITE:
        return SqliteSqlStatements()
    elif database_type == DatabaseType.MSSQL:
        return MsSqlSqlStatements()
    elif database_type == DatabaseType.ORACLE:
        return OracleSqlStatements()
    elif database_type == DatabaseType.AS400:
        return AS400SqlStatements()
    else:
        raise ValueError(f"Unsupported database type: {database_type}")
