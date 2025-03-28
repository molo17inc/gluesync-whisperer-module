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
from sqlalchemy.dialects import registry

# Configure logging
logger = logging.getLogger(__name__)

def register_jdbc_dialects():
    """
    Register JDBC dialects with SQLAlchemy.
    This ensures SQLAlchemy knows how to use JDBC for all database types.
    Must be called before any SQLAlchemy operations.
    """
    try:
        # Register JayDeBeApi dialects
        registry.register("mysql.jdbc", "sqlalchemy_jdbcapi.mysqldb", "MySQLDBDialect_jdbc")
        registry.register("postgresql.jdbc", "sqlalchemy_jdbcapi.postgresql", "PostgresqlDialect_jdbc")
        registry.register("oracle.jdbc", "sqlalchemy_jdbcapi.oracle", "OracleDialect_jdbc")
        registry.register("mssql.jdbc", "sqlalchemy_jdbcapi.mssql", "MSDialect_jdbc")
        registry.register("as400.jdbc", "sqlalchemy_jdbcapi.as400", "AS400Dialect_jdbc")
        
        logger.info("Successfully registered JDBC dialects with SQLAlchemy")
        return True
    except Exception as e:
        logger.error(f"Error registering JDBC dialects: {str(e)}")
        return False

# Register dialects automatically when this module is imported
registered = register_jdbc_dialects()
