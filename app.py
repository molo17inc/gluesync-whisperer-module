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

import os
import ssl
import json
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import Settings
from api.router import router as api_router
from api.table_router import router as table_router
from routers.automation import router as automation_router
from routers.pillow_fight import router as pillow_fight_router
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
app.include_router(api_router)
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
async def serve_pwa_icon_192x192():
    """Serve PWA icon."""
    icon_path = os.path.join(static_dir, "web-app-manifest-192x192.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "PWA icon not found"})

# Serve any other static files from root static directory
@app.get("/favicon-96x96.png", include_in_schema=False)
async def serve_favicon_png():
    """Serve favicon PNG file."""
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
    """Handle SPA routing."""
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
