#!/usr/bin/env python3
"""
 * This file is part of Database Automator.
 *
 * Database Automator is dual-licensed under the following licenses:
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

import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Create data directory if it doesn't exist
data_dir = Path("./data")
os.makedirs(data_dir, exist_ok=True)

# Create logs directory if it doesn't exist
logs_dir = Path("./logs")
os.makedirs(logs_dir, exist_ok=True)


class Settings(BaseSettings):
    # Database configuration for automator's own database
    DB_URL: str = os.getenv("DB_URL", f"sqlite:///./data/automator.db")
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # SSL configuration
    SSL_ENABLED: bool = os.getenv("SSL_ENABLED", "False").lower() in ("true", "1", "t")
    
    # Default delay between database operations (in seconds)
    DEFAULT_OPERATION_DELAY: float = float(os.getenv("DEFAULT_OPERATION_DELAY", "1.0"))
    
    # Default batch size for operations (how many operations to perform in a batch)
    DEFAULT_BATCH_SIZE: int = int(os.getenv("DEFAULT_BATCH_SIZE", "1"))
    
    # Maximum number of operations to perform on a table (0 for unlimited)
    MAX_OPERATIONS: int = int(os.getenv("MAX_OPERATIONS", "0"))
    
    # Probability weights for each operation type (must sum to 1.0)
    INSERT_WEIGHT: float = float(os.getenv("INSERT_WEIGHT", "0.33"))
    UPDATE_WEIGHT: float = float(os.getenv("UPDATE_WEIGHT", "0.33"))
    DELETE_WEIGHT: float = float(os.getenv("DELETE_WEIGHT", "0.34"))
    
    class Config:
        env_file = ".env"


# Instantiate settings
settings = Settings()
