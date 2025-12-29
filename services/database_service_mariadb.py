#!/usr/bin/env python3
"""
MariaDB database service, built on top of the MySQL service implementation.
"""

from services.database_service_mysql import MySQLDatabaseService
from utils.db_connector import DatabaseType


class MariaDBDatabaseService(MySQLDatabaseService):
    """MariaDB-specific service leveraging the MySQL implementation."""

    DB_TYPE = DatabaseType.MARIADB
    DISPLAY_NAME = "MariaDB"
    JDBC_SCHEME = "mariadb"
