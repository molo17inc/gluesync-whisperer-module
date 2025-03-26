#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Database Automator is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Database Automator.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models import DatabaseConnection, ConnectionStatus

# Configure logging
logger = logging.getLogger(__name__)

class ConnectionService:
    """Service to manage database connections."""
    
    def __init__(self, db: Session):
        """Initialize the connection service."""
        self.db = db
    
    def get_connections(self) -> List[DatabaseConnection]:
        """Get all database connections."""
        return self.db.query(DatabaseConnection).all()
    
    def get_connection(self, connection_id: int) -> Optional[DatabaseConnection]:
        """Get a database connection by ID."""
        return self.db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id
        ).first()
    
    def create_connection(self, connection_data: dict) -> DatabaseConnection:
        """Create a new database connection."""
        connection = DatabaseConnection(**connection_data)
        connection.status = ConnectionStatus.DISCONNECTED
        connection.created_at = datetime.now()
        connection.updated_at = datetime.now()
        
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        
        return connection
    
    def update_connection(self, connection_id: int, connection_data: dict) -> Optional[DatabaseConnection]:
        """Update a database connection."""
        connection = self.get_connection(connection_id)
        if not connection:
            return None
        
        for key, value in connection_data.items():
            if hasattr(connection, key) and value is not None:
                setattr(connection, key, value)
        
        connection.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(connection)
        
        return connection
    
    def delete_connection(self, connection_id: int) -> bool:
        """Delete a database connection."""
        connection = self.get_connection(connection_id)
        if not connection:
            return False
        
        self.db.delete(connection)
        self.db.commit()
        
        return True
    
    def update_connection_status(self, connection_id: int, status: ConnectionStatus) -> Optional[DatabaseConnection]:
        """Update a database connection status."""
        connection = self.get_connection(connection_id)
        if not connection:
            return None
        
        connection.status = status
        connection.updated_at = datetime.now()
        
        if status == ConnectionStatus.CONNECTED:
            connection.last_operation_at = datetime.now()
        
        self.db.commit()
        self.db.refresh(connection)
        
        return connection
    
    def update_all_busy_connections(self, status: ConnectionStatus) -> int:
        """Update all busy connections to a new status."""
        connections = self.db.query(DatabaseConnection).filter(
            DatabaseConnection.status == ConnectionStatus.BUSY
        ).all()
        
        count = 0
        for connection in connections:
            connection.status = status
            connection.updated_at = datetime.now()
            count += 1
        
        self.db.commit()
        return count
