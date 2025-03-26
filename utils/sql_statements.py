#!/usr/bin/env python3
"""
 * This file is part of Database Whisperer.
 *
 * Database Whisperer is dual-licensed under the following licenses:
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
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import DatabaseType
from utils.sql.base import BaseSqlStatements
from utils.sql.mysql import MySqlSqlStatements 
from utils.sql.postgresql import PostgreSqlSqlStatements
from utils.sql.sqlite import SqliteSqlStatements
from utils.sql.mssql import MsSqlSqlStatements
from utils.sql.oracle import OracleSqlStatements
from utils.sql.as400 import AS400SqlStatements
from utils.sql.factory import get_sql_statements

logger = logging.getLogger(__name__)

# Re-export all the SQL statement classes and factory function
__all__ = [
    'BaseSqlStatements',
    'MySqlSqlStatements',
    'PostgreSqlSqlStatements',
    'SqliteSqlStatements',
    'MsSqlSqlStatements',
    'OracleSqlStatements',
    'AS400SqlStatements',
    'get_sql_statements'
]
