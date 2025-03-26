# Gluesync Whisperer

A specialized module for orchestrating database operations. This application enables you to connect to various database types and perform controlled insert, update, and delete operations based on user-defined configurations, creating a "pillow fight" of database activity.

## Features

- Connect to multiple database types (MySQL, PostgreSQL, SQLite, MSSQL, Oracle, AS400)
- Configure tables for automated operations
- Control operation types (insert, update, delete, or all)
- Set delay between operations and batch sizes
- View operation logs and connection status
- REST API for configuration and control
- Robust parameter handling for all database types
- Automatic transaction management for data modification operations

## Installation

1. Clone the repository with its submodules:

   ```bash
   git clone --recursive https://gitlab.com/molo17-public/gluesync/gluesync-whisperer-module.git
   cd gluesync-whisperer-module
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:

   ```bash
   python3 init_db.py
   ```

## Usage

### Start the server

```bash
python3 app.py
```

The API server will start on <http://0.0.0.0:1717> by default.

### Using Docker

You can also run the application using Docker:

```bash
# Build the Docker image
docker build -t gluesync-whisperer .

# Run the container
docker run -d -p 1717:1717 --name whisperer gluesync-whisperer
```

### API Documentation

Once the server is running, access the API documentation at:

- Swagger UI: <http://localhost:1717/docs>
- ReDoc: <http://localhost:1717/redoc>

## License

Gluesync Whisperer (Gluesync Whisperer) is dual-licensed under the following licenses:

1. **GNU General Public License (GPL) Version 3**  
   You may use, modify, and distribute this software under the terms of the GPL v3.  
   See the [LICENSE-GPL](LICENSE-GPL) file or <http://www.gnu.org/licenses/gpl-3.0.html> for details.  
   This option is available at no cost, but any derivative works must also be licensed under GPL v3.

2. **MOLO17 Commercial License**  
   Alternatively, you may use this software under the MOLO17 Commercial License,  
   which includes a warranty and permits proprietary use. Contact MOLO17 at info@molo17.com  
   for licensing terms and conditions.

You must choose one of these licenses to use this software. Using this software implies
acceptance of one of these licenses.

Copyright (C) 2025 MOLO17. All rights reserved.

## Configuration

### Environment Variables

You can configure the application using the following environment variables:

- `DB_URL`: Database URL for whisperer's own database (default: `sqlite:///./data/whisperer.db`)
- `HOST`: Server host (default: `0.0.0.0`)
- `PORT`: Server port (default: `1717`)
- `DEBUG`: Enable debug mode (default: `False`)
- `SSL_ENABLED`: Enable SSL (default: `False`)
- `SSL_CERT_FILE`: Path to SSL certificate file
- `SSL_KEY_FILE`: Path to SSL private key file
- `DEFAULT_OPERATION_DELAY`: Default delay between operations in seconds (default: `1.0`)
- `DEFAULT_BATCH_SIZE`: Default batch size for operations (default: `1`)
- `MAX_OPERATIONS`: Maximum number of operations per table (0 for unlimited, default: `0`)
- `INSERT_WEIGHT`: Probability weight for insert operations (default: `0.33`)
- `UPDATE_WEIGHT`: Probability weight for update operations (default: `0.33`)
- `DELETE_WEIGHT`: Probability weight for delete operations (default: `0.34`)

## API Endpoints

### Connection Management

- `POST /api/connections`: Create a new database connection
- `GET /api/connections`: List all connections
- `GET /api/connections/{connection_id}`: Get connection details
- `PUT /api/connections/{connection_id}`: Update a connection
- `DELETE /api/connections/{connection_id}`: Delete a connection
- `POST /api/connections/{connection_id}/test`: Test a connection
- `GET /api/connections/{connection_id}/tables?schema={schema}`: List tables in the database (schema parameter required)
- `PUT /api/connections/{connection_id}/status`: Update connection status (start/stop/pause)

### Table Configuration

- `POST /api/tables`: Create a new table configuration
- `GET /api/tables`: List all table configurations
- `GET /api/connections/{connection_id}/tables`: List table configurations for a connection
- `GET /api/tables/{table_id}`: Get table configuration details
- `PUT /api/tables/{table_id}`: Update a table configuration
- `DELETE /api/tables/{table_id}`: Delete a table configuration
- `GET /api/connections/{connection_id}/tables/{table_name}/schema?schema={schema}`: Get table schema (schema parameter required)

## Database Support

### Supported Database Types

Gluesync Whisperer supports the following database types with their specific parameter handling:

#### MySQL

- Uses `%s` placeholders in SQL queries
- Automatically handles parameter escaping and quoting
- Properly commits transactions for data modification operations

#### PostgreSQL

- Uses named parameters (`:param`) in SQL queries
- Works well with standard SQLAlchemy parameter binding

#### Oracle

- Uses named parameters (`:param`) in SQL queries
- Properly handles schema and table name parameters

#### SQL Server (MSSQL)

- Uses named parameters (`:param`) in SQL queries
- Works with SQLAlchemy's parameter binding

#### SQLite

- Supports both named parameters (`:param`) and question mark (`?`) placeholders
- All operations are automatically committed

#### AS400/DB2

- Supports both named parameters and question mark placeholders depending on configuration
- Parameter binding adapted for AS400's specific requirements

### Transaction Management

The application automatically handles transactions for all database types:

- Data modification operations (INSERT, UPDATE, DELETE) are automatically committed when successful
- Transactions are automatically rolled back in case of errors
- Read operations (SELECT) don't require transaction management

### Parameter Binding and Security

Parameter binding is implemented securely for all database types to prevent SQL injection:

- Parameters are properly escaped and quoted based on their type
- MySQL parameter handling avoids the double-escaping issue
- Named parameters are correctly mapped for all database types
- Positional parameters are converted to the appropriate format for each database

## Troubleshooting

### Common Issues

#### Connection Issues

- Verify database credentials and connection parameters
- Check that the database server is accessible from the application
- Ensure proper database driver is installed

#### Parameter Binding Errors

- Make sure to provide schema parameter for all operations that require it
- Check SQL statement syntax for compatibility with your database
- Verify parameter types match the column types in your database

#### Transaction Not Committed

- The application now automatically handles transaction commits
- If you still encounter issues, check database permissions
- Some databases may have autocommit settings that conflict with application settings

#### Schema Requirements

- Most API endpoints requiring table access now explicitly require a schema parameter
- This prevents ambiguity and ensures correct data retrieval
- For example: `/api/connections/{connection_id}/tables?schema=your_schema`

### Operations

- `POST /api/operations`: Start automated operations on tables

## Docker Usage

1. Build the Docker image:

   ```bash
   docker build -t gluesync-whisperer .
   ```

2. Run the container:

   ```bash
   docker run -d -p 1717:1717 --name whisperer gluesync-whisperer
   ```
