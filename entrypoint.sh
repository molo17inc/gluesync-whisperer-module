#!/bin/bash
# This file is part of Gluesync Whisperer.
#
# Gluesync Whisperer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Database Automator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gluesync Whisperer.  If not, see <http://www.gnu.org/licenses/>.

set -e

# Create data directory if it doesn't exist
mkdir -p /app/data

# Wait for CoreHub to be available if CORE_HUB_URL is set
if [ -n "$CORE_HUB_URL" ]; then
    echo "Waiting for CoreHub to be available at $CORE_HUB_URL..."
    timeout=30
    counter=0
    until curl -s --head --fail "$CORE_HUB_URL" > /dev/null 2>&1 || [ $counter -eq $timeout ]; do
        echo "Waiting for CoreHub to become available... ($counter/$timeout)"
        counter=$((counter+1))
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
python3 -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"

# Start the application
echo "Starting Gluesync Whisperer..."
exec python3 app.py
