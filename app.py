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

# JDBC drivers are used for all database connections directly

import asyncio
import logging
import os
import ssl
import json
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.router import router
from api.table_router import router as table_router
from routers.automation import router as automation_router
from routers.pillow_fight import router as pillow_fight_router
from config import settings, Settings
from database import init_db

# Initialize settings to ensure data directory exists
settings = Settings()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Initialize the database
init_db()

# Create the FastAPI app
app = FastAPI(
    title="Gluesync Whisperer",
    description="API for Gluesync Whisperer",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=True,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handling middleware
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return RedirectResponse(url="/error")

app.middleware("http")(catch_exceptions_middleware)

# Don't mount static files at all - serve everything through routes
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Include routers (API routes)
app.include_router(router)
app.include_router(table_router)
app.include_router(automation_router)
app.include_router(pillow_fight_router)

# Serve assets directly from the assets route
@app.get("/assets/{path:path}", include_in_schema=False)
async def serve_assets(path: str):
    """Serve asset files directly."""
    if not os.path.exists(static_dir):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Static directory not found"})
    
    asset_path = os.path.join(static_dir, "assets", path)
    if os.path.exists(asset_path) and os.path.isfile(asset_path):
        return FileResponse(asset_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    else:
        # Return 404 if asset not found
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Asset not found"})

# Serve favicon and other static files from root
@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon_ico():
    """Serve favicon.ico file."""
    favicon_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Favicon not found"})

@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon_svg():
    """Serve favicon.svg file."""
    favicon_path = os.path.join(static_dir, "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Favicon not found"})

@app.get("/apple-touch-icon.png", include_in_schema=False)
async def serve_apple_touch_icon():
    """Serve apple-touch-icon.png file."""
    icon_path = os.path.join(static_dir, "apple-touch-icon.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Icon not found"})

# Serve other static files from root static directory
@app.get("/web-app-manifest-192x192.png", include_in_schema=False)
async def serve_pwa_icon_192():
    """Serve PWA icon 192x192."""
    icon_path = os.path.join(static_dir, "web-app-manifest-192x192.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "PWA icon not found"})

# Serve any other static files from root static directory
@app.get("/favicon-96x96.png", include_in_schema=False)
async def serve_favicon_png():
    """Serve favicon-96x96.png file."""
    favicon_path = os.path.join(static_dir, "favicon-96x96.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Favicon PNG not found"})

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the React frontend."""
    if not os.path.exists(static_dir):
        return RedirectResponse(url="/docs")
        
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        # Fallback to API docs if frontend not built
        return RedirectResponse(url="/docs")

# Catch-all route for SPA routing (must be last)
@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    """Handle SPA routing by serving index.html for frontend routes."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        # Fallback to API docs if frontend not built
        return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )
