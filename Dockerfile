# Build stage for SDK installation
FROM python:3.11-slim AS builder

WORKDIR /build

# Set environment variables for Python and dependency installation
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    python3-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy only the SDK submodule (if available)
COPY ./gluesync-sdk ./gluesync-sdk

# Install specific websockets version first to avoid compatibility issues
RUN pip install websockets==11.0.3

# Check SDK directory and create wheels directory
RUN pip install wheel && \
    mkdir -p /wheels && \
    if [ -d "./gluesync-sdk" ] && [ -f "./gluesync-sdk/setup.py" ]; then \
        cd ./gluesync-sdk && \
        pip wheel -w /wheels .; \
    fi

# Frontend build stage
FROM node:18-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend source
COPY ./frontend/package*.json ./
COPY ./frontend/ ./

# Install dependencies and build
RUN npm ci && npm run build

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Create Gluesync default directories and app data directory
RUN mkdir -p /opt/gluesync/data && \
    mkdir -p /app/data && \
    chmod 777 /app/data

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Core Hub settings \
    CORE_HUB_URL= \
    ENTITY_START_TIMEOUT=2 \
    # API Server settings \
    HOST=0.0.0.0 \
    PORT=1717 \
    DEBUG=False \
    # Database settings \
    DATA_DIR=/app/data \
    DB_URL=sqlite:///./data/whisperer.db \
    # CORS settings \
    ALLOWED_ORIGINS=* \
    # Whisperer settings \
    DEFAULT_OPERATION_DELAY=1.0 \
    DEFAULT_BATCH_SIZE=1 \
    MAX_OPERATIONS=1000 \
    # Gluesync SDK settings using default paths \
    GLUESYNC_LICENSE_FILE=/opt/gluesync/data/gs-license.dat \
    SSL_ENABLED=False \
    GLUESYNC_SECURITY_CONFIG=/opt/gluesync/data/security-config.json \
    SSL_SKIP_VERIFY=True \
    # Java settings for JDBC \
    JAVA_HOME=/usr/lib/jvm/zulu21-ca-amd64

# Install system dependencies for database drivers and runtime requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    openssl \
    # Dependencies for IBM DB2/AS400 driver
    wget \
    unzip \
    apt-transport-https \
    gnupg \
    ca-certificates \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Zulu JDK 21 for JDBC support
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget apt-transport-https gnupg ca-certificates && \
    # Add Azul's public key
    wget -qO - https://repos.azul.com/azul-repo.key | gpg --dearmor -o /usr/share/keyrings/azul.gpg && \
    # Add Azul's apt repository
    echo "deb [signed-by=/usr/share/keyrings/azul.gpg] https://repos.azul.com/zulu/deb stable main" > /etc/apt/sources.list.d/zulu.list && \
    apt-get update && \
    apt-get install -y zulu21-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Ensure JAVA_HOME is correctly set
ENV JAVA_HOME=/usr/lib/jvm/zulu21-ca-amd64

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Copy only necessary application files
COPY ./requirements.txt .

# Wait for the SDK installation step below
COPY ./entrypoint.sh .
COPY ./app.py .
COPY ./config.py .
COPY ./models.py .
COPY ./schemas.py .
COPY ./database.py .
COPY ./utils ./utils
COPY ./api ./api
COPY ./routers ./routers
COPY ./services ./services
# Copy JDBC drivers for AS400, MS SQL Server, PostgreSQL, MySQL, and Oracle support
# Download PostgreSQL JDBC driver
RUN wget -O /app/jdbc_drivers/postgresql.jar https://jdbc.postgresql.org/download/postgresql-42.7.8.jar
COPY ./jdbc_drivers ./jdbc_drivers
COPY ./run_auto_operations.py .

# Copy built frontend files to static directory
COPY --from=frontend-builder /frontend/dist ./static

# Create logs directory
RUN mkdir -p /app/logs

# Make entrypoint script executable
RUN if [ -f "/app/entrypoint.sh" ]; then chmod +x /app/entrypoint.sh; fi

# Install specific websockets version first to avoid compatibility issues
RUN pip install websockets==11.0.3

# Install the SDK from the wheel if exists
RUN if [ -d "/wheels" ] && [ "$(ls -A /wheels)" ]; then pip install /wheels/*; else echo "No SDK wheels found, continuing without SDK"; fi

# Install all Python dependencies including database drivers
RUN pip install --no-cache-dir -r requirements.txt

# We're not using IBM DB2 native drivers anymore, using JDBC for all architectures
# JDBC drivers are already copied in the jdbc_drivers directory

# Expose port
EXPOSE 1717

# Command to run the application
CMD ["python3", "app.py"]
