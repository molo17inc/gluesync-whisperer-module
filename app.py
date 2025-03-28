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

# JDBC drivers are used for all database connections
# No need for pyodbc or patching

import asyncio
import logging
import os
import ssl
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.router import router
from api.table_router import router as table_router
from routers.automation import router as automation_router
from routers.pillow_fight import router as pillow_fight_router
from config import settings, Settings
from database import Base, engine

# Initialize settings to ensure data directory exists
settings = Settings()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create the database tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Gluesync Whisperer",
    description="A specialized module for orchestrating controlled database operations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# Middleware to catch any uncaught exceptions
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Uncaught exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return RedirectResponse("/error", status_code=303)


app.middleware("http")(catch_exceptions_middleware)


# Include the API routers
app.include_router(router, prefix="/api")
app.include_router(table_router, prefix="/api")
app.include_router(automation_router)
app.include_router(pillow_fight_router)


@app.get("/", tags=["root"])
async def read_root():
    """Root endpoint that redirects to the API documentation."""
    return RedirectResponse(url="/docs")


@app.get("/api/docs", tags=["documentation"])
async def api_docs():
    """Redirect to API documentation to match the scheduler module."""
    return RedirectResponse(url="/docs")


@app.get("/docs/v1", tags=["documentation"])
async def docs_v1():
    """Redirect to API documentation - alternative path."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    ssl_enabled = settings.SSL_ENABLED
    
    if ssl_enabled:
        logger.info("Starting server with SSL enabled")
        
        # Check for SSL certificate paths in environment
        cert_file = os.getenv('SSL_CERT_FILE')
        key_file = os.getenv('SSL_KEY_FILE')
        
        if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
            # Use provided certificate files
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(cert_file, key_file)
            
            uvicorn.run(
                "app:app",
                host=settings.HOST,
                port=settings.PORT,
                reload=settings.DEBUG,
                ssl_keyfile=key_file,
                ssl_certfile=cert_file
            )
        else:
            logger.warning("SSL certificates not found, falling back to HTTP mode")
            uvicorn.run(
                "app:app",
                host=settings.HOST,
                port=settings.PORT,
                reload=settings.DEBUG
            )
    else:
        logger.info("Starting server in HTTP mode")
        uvicorn.run(
            "app:app",
            host=settings.HOST, 
            port=settings.PORT,
            reload=settings.DEBUG
        )
