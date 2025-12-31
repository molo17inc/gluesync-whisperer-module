#!/bin/bash
# This file is part of Gluesync Whisperer.
#
# Gluesync Whisperer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gluesync Whisperer is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gluesync Whisperer.  If not, see <http://www.gnu.org/licenses/>.

set -e

# Create data directory if it doesn't exist
mkdir -p /app/data

# Adjust frontend bundle paths according to FRONTEND_BASE_PATH at runtime
STATIC_DIR="/app/static"
if [ -d "$STATIC_DIR" ]; then
    python3 <<'PY'
import json
import os
import re
from pathlib import Path

static_dir = Path("/app/static")
base_path = os.environ.get("FRONTEND_BASE_PATH", "/") or "/"
base_path = base_path.strip()
if not base_path:
    base_path = "/"
if not base_path.startswith("/"):
    base_path = "/" + base_path
if len(base_path) > 1 and base_path.endswith("/"):
    base_path = base_path[:-1]

def ensure_template(path: Path) -> Path | None:
    if not path.exists():
        return None
    template_path = path.with_suffix(path.suffix + ".template")
    if not template_path.exists():
        template_path.write_text(path.read_text())
    return template_path

def apply_html(path: Path):
    template = ensure_template(path)
    if template is None:
        return
    html = template.read_text()
    if base_path == "/":
        path.write_text(html)
        return

    pattern = re.compile(r'(?P<attr>(?:href|src)=)"(?P<path>/[^" >]*)"')

    def repl(match: re.Match):
        original_path = match.group("path")
        if original_path.startswith("//"):
            return match.group(0)
        new_path = f"{base_path}{original_path}"
        return f'{match.group("attr")}"{new_path}"'

    path.write_text(pattern.sub(repl, html))

def apply_manifest(path: Path):
    template = ensure_template(path)
    if template is None:
        return
    if base_path == "/":
        path.write_text(template.read_text())
        return

    data = json.loads(template.read_text())

    def rewrite(value):
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, str) and value.startswith("/") and not value.startswith("//"):
            return f"{base_path}{value}"
        return value

    path.write_text(json.dumps(rewrite(data), indent=2))

index_file = static_dir / "index.html"
if index_file.exists():
    apply_html(index_file)

manifest_file = static_dir / "site.webmanifest"
if manifest_file.exists():
    apply_manifest(manifest_file)
PY
fi

# Wait for CoreHub to be available if CORE_HUB_URL is set
if [ -n "$CORE_HUB_URL" ]; then
    echo "Waiting for CoreHub to be available at $CORE_HUB_URL..."
    timeout=30
    counter=0
    until curl -s --head --fail "$CORE_HUB_URL" >/dev/null 2>&1 || [ $counter -eq $timeout ]; do
        echo "Waiting for CoreHub to become available... ($counter/$timeout)"
        counter=$((counter + 1))
        sleep 1
    done

    if [ $counter -eq $timeout ]; then
        echo "CoreHub did not become available in time, but continuing anyway..."
    else
        echo "CoreHub is available!"
    fi
fi

# Run database migrations if needed
echo "Initializing database..."
python3 -c "from database import get_db; db = get_db(); print('Database initialized successfully!')"

# Start the application
echo "Starting Gluesync Whisperer..."
exec python3 app.py
