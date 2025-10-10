#!/usr/bin/env python3
"""
 * This file is part of Gluesync Whisperer.
 *
 * Gluesync Whisperer is dual-licensed under the following licenses:
 * - GNU Affero General Public License v3.0
 * - Gluesync Commercial License
 *
 * You can choose between one of them if you use this software.
 *
 * For more information about the Gluesync Commercial License
 * contact us at info@gluesync.com
 *
 * GNU Affero General Public License v3.0:
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
"""

import logging
from typing import Dict, Type

from utils.db_connector import DatabaseType
from services.database_service_base import DatabaseServiceBase
from services.database_service_mssql import MSSQLDatabaseService
from services.database_service_as400 import AS400DatabaseService
from services.database_service_sqlite import SQLiteDatabaseService
from services.database_service_mysql import MySQLDatabaseService
from services.database_service_postgresql import PostgreSQLDatabaseService
from services.database_service_oracle import OracleDatabaseService

logger = logging.getLogger(__name__)

class DatabaseServiceFactory:
    """Factory class to create database service instances based on database type"""
    
    # Registry of database service implementations
    _registry: Dict[DatabaseType, Type[DatabaseServiceBase]] = {}
    
    @classmethod
    def register(cls, db_type: DatabaseType, service_class: Type[DatabaseServiceBase]) -> None:
        """Register a database service implementation for a specific database type"""
        cls._registry[db_type] = service_class
        logger.info(f"Registered {service_class.__name__} for database type {db_type}")
    
    @classmethod
    def create(cls, db_type: DatabaseType, db) -> DatabaseServiceBase:
        """Create a database service instance for the specified database type"""
        # Convert string db_type to enum if needed
        if isinstance(db_type, str):
            try:
                db_type = DatabaseType[db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {db_type}")
                raise ValueError(f"Unsupported database type: {db_type}")
                
        if db_type not in cls._registry:
            logger.error(f"No database service implementation registered for {db_type}")
            raise ValueError(f"Unsupported database type: {db_type}")
        
        service_class = cls._registry[db_type]
        logger.info(f"Creating {service_class.__name__} for database type {db_type}")
        return service_class(db)
    
    @classmethod
    def get_service_for_connection(cls, connection, db) -> DatabaseServiceBase:
        """Get the appropriate database service for a connection"""
        db_type = connection.db_type
        
        # Convert string db_type to enum if needed
        if isinstance(db_type, str):
            try:
                db_type = DatabaseType[db_type.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown database type string: {db_type}")
                raise ValueError(f"Unsupported database type: {db_type}")
        
        return cls.create(db_type, db)

# Register database service implementations
DatabaseServiceFactory.register(DatabaseType.MSSQL, MSSQLDatabaseService)
DatabaseServiceFactory.register(DatabaseType.AS400, AS400DatabaseService)
DatabaseServiceFactory.register(DatabaseType.SQLITE, SQLiteDatabaseService)
DatabaseServiceFactory.register(DatabaseType.MYSQL, MySQLDatabaseService)
DatabaseServiceFactory.register(DatabaseType.POSTGRESQL, PostgreSQLDatabaseService)
DatabaseServiceFactory.register(DatabaseType.ORACLE, OracleDatabaseService)
