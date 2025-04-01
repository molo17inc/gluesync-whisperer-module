# Gluesync Whisperer

A specialized module for orchestrating database operations. This application enables you to connect to various database types and perform controlled insert, update, and delete operations based on user-defined configurations, creating a "pillow fight" of database activity.

## Features

- Connect to multiple database types (MySQL, PostgreSQL, SQLite, MSSQL, Oracle, AS400)
- Configure tables for automated operations
- Control operation types (insert, update, delete, or all)
- Set delay between operations and batch sizes
- View operation logs and connection status
- REST API for configuration and control
- Execute custom SQL queries against configured database connections
- Robust parameter handling for all database types
- Automatic transaction management for data modification operations
- Cross-platform support for AS400/DB2 databases on both x86_64 and ARM architectures
- Cascade delete support for handling foreign key constraints during delete operations

## AS400 Specific Improvements

### Latest Enhancements

- **Cross-platform Support**: Replaced architecture-specific `ibm_db` libraries with a universal JDBC-based implementation using `jaydebeapi`
- **Better Schema Support**: Improved schema detection and qualified table name handling for AS400 databases
- **Optimized Metadata Retrieval**: Streamlined metadata detection with AS400-specific catalog queries
- **Foreign Key Handling**: Intelligently skips foreign key checks on AS400 to reduce unnecessary operations and warnings
- **MAX ID Query Optimization**: Enhanced MAX ID queries with AS400-compatible syntax and dynamic column name detection
- **DELETE Operations**: Fixed deletion support with proper error handling for AS400 databases

## MS SQL Server Specific Improvements

### Latest Enhancements

- **JDBC Implementation**: Replaced ODBC with JDBC for better cross-platform compatibility
- **Metadata Retrieval**: Enhanced schema and table retrieval for MS SQL Server
- **Primary Key Handling**: Added unique primary key value generation for insert operations
- **Cascade Delete Support**: Added option to handle foreign key constraints during delete operations by temporarily disabling constraints, performing the delete, and then re-enabling constraints

## Software Installation

### Database Driver Requirements

Gluesync Whisperer supports multiple database types, each requiring specific Python drivers:

| Database Type | Required Driver Packages | Notes |
|--------------|--------------------------|-------|
| MySQL | `pymysql` | Included in requirements.txt |
| PostgreSQL | `psycopg2-binary` | Included in requirements.txt |
| SQLite | Built-in SQLAlchemy support | No additional packages needed |
| MSSQL | `jaydebeapi` with MS SQL JDBC driver | **Cross-platform compatible** - Works on both x86_64 and ARM-based platforms (M1/M2 Macs) |
| Oracle | `cx_Oracle` | May require Oracle client libraries |
| AS400/DB2 | `jaydebeapi` with JT400 JDBC driver | **Cross-platform compatible** - Works on both x86_64 and ARM-based platforms (M1/M2 Macs) |

All required drivers are included in the Dockerfile for containerized deployment. Both AS400/DB2 and MS SQL Server connections now use JDBC drivers via `jaydebeapi`, making them fully compatible with both x86_64 and ARM-based platforms (including M1/M2 Macs). The ODBC dependency has been completely removed for better cross-platform compatibility.

### Local Installation

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
   See the [LICENSE-GPL](LICENSE-GPL) file or [GPL v3 license](http://www.gnu.org/licenses/gpl-3.0.html) for details.  
   This option is available at no cost, but any derivative works must also be licensed under GPL v3.

2. **MOLO17 Commercial License**  
   Alternatively, you may use this software under the MOLO17 Commercial License,  
   which includes a warranty and permits proprietary use. Contact MOLO17 at [info@molo17.com](mailto:info@molo17.com)  
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

### SQL Query Execution

- `POST /api/v1/automation/connections/{connection_id}/query`: Execute a SQL query against a database connection
  - Request body: `{"query": "SELECT * FROM your_table", "schema_name": "optional_schema", "params": ["optional_parameters"], "max_rows": 100}`
  - Returns: Query results with column names and row data

### Table Configuration

- `POST /api/tables`: Create a new table configuration
- `GET /api/tables`: List all table configurations
- `GET /api/connections/{connection_id}/tables`: List table configurations for a connection

#### Table Configuration Options

| Option | Description | Default |
|--------|-------------|--------|
| `table_name` | Name of the table to configure | Required |
| `schema_name` | Database schema name | Optional |
| `operation_type` | Type of operations to perform (INSERT, UPDATE, DELETE, ALL) | ALL |
| `operation_delay` | Delay between operations in seconds | 1.0 |
| `batch_size` | Number of operations to perform in each batch | 1 |
| `enabled` | Whether the table is enabled for operations | true |
| `cascade_delete` | Whether to cascade deletes for foreign key constraints | false |

#### Table API Endpoints

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

#### Primary Operations API (Recommended)

- `POST /api/operations`: Start automated operations on tables
  - Request body:

    ```json
    {
      "connection_id": 1,
      "table_ids": [1, 2, 3],
      "operation_type": "ALL",
      "operation_delay": 1.0,
      "batch_size": 1
    }
    ```

  - The `connection_id` is the ID of the database connection
  - The `table_ids` is an array of table configuration IDs to operate on
  - The `operation_type` can be one of: `INSERT`, `UPDATE`, `DELETE`, `ALL`
  - `operation_delay` is in seconds (minimum 0.1)
  - `batch_size` is the number of operations to perform in a batch (minimum 1)

#### Alternative Automation API

- `POST /api/v1/automation/start`: Start automated operations on tables
  - Request body should contain connection ID, operation parameters, and table names

- `POST /api/v1/automation/stop/{connection_id}/{table_name}`: Stop automation for a specific table
  - Path parameters:
    - `connection_id`: ID of the database connection
    - `table_name`: Name of the table to stop automation for

### PillowFight (Load Testing)

PillowFight is a specialized testing and load generation feature designed to simulate high-volume database operations for system resilience testing.

#### What is PillowFight?

Unlike regular operations that are meant for actual data synchronization, PillowFight is specifically designed for:

- Stress testing your database systems
- Simulating high-volume operation scenarios
- Validating system performance under load
- Testing error handling and recovery mechanisms

PillowFight can run multiple operation types concurrently (INSERT, UPDATE, DELETE) and maintains detailed statistics about the operations performed.

#### PillowFight API

- `POST /api/v1/pillow-fight/start`: Start a PillowFight test
  - Request body:

    ```json
    {
      "connection_id": 1,
      "table_ids": [1, 2, 3],
      "operation_type": "ALL",
      "operation_delay": 0.1,
      "batch_size": 10
    }
    ```

  - The `connection_id` is the ID of the database connection
  - The `table_ids` is an array of table configuration IDs to operate on
  - The `operation_type` determines which operations to include in the test:
    - `INSERT`: Only perform inserts
    - `UPDATE`: Only perform updates
    - `DELETE`: Only perform deletes
    - `ALL`: Perform all three operation types concurrently
  - `operation_delay` is in seconds (lower values create more intensive tests)
  - `batch_size` is the number of operations to perform in a batch (higher values increase load)

- `GET /api/v1/pillow-fight/status`: Get status of active PillowFight tests
  - Returns a list of all active PillowFight tests with statistics on operations performed

- `POST /api/v1/pillow-fight/stop/{connection_id}/{table_id}`: Stop a PillowFight test
  - Path parameters:
    - `connection_id`: ID of the database connection
    - `table_id`: ID of the table to stop testing

#### When to Use PillowFight vs. Regular Operations

| Feature | PillowFight | Regular Operations |
|---------|------------|--------------------|
| **Purpose** | Testing and stress simulation | Actual data synchronization |
| **Operation Types** | Can run multiple types concurrently | One operation type at a time |
| **Data Integrity** | Generates test data that may need cleanup | Creates legitimate synchronized data |
| **Performance Impact** | Designed to push system limits | Optimized for production use |
| **Monitoring** | Detailed statistics for test analysis | Basic operation logging |

#### Example Use Case

Before deploying a new database schema or application version to production, use PillowFight to:

1. Validate that your system can handle the expected operation volume
2. Identify potential bottlenecks under high load
3. Test recovery procedures if operations fail
4. Measure performance metrics for different operation types

## Docker Usage

### Basic Docker Build

1. Build the Docker image:

   ```bash
   docker build -t gluesync-whisperer .
   ```

2. Run the container:

   ```bash
   docker run -d -p 1717:1717 --name whisperer gluesync-whisperer
   ```

### Multi-Architecture Docker Build

Gluesync Whisperer supports multi-architecture Docker builds for both ARM64 (Apple Silicon/M1/M2) and AMD64 (Intel/x86_64) platforms.

#### Platform-Specific Support Notes

- **x86_64/AMD64**: Full support for all database types, including AS400/DB2 and MS SQL Server
- **ARM64/Apple Silicon**: Full support for all database types, including AS400/DB2 and MS SQL Server (uses JDBC drivers for cross-platform compatibility)

#### Using the Multi-Architecture Build Script

1. Use the provided build script to create a multi-architecture image:

   ```bash
   ./build-multiarch.sh
   ```

2. Run using Docker Compose:

   ```bash
   docker-compose up -d
   ```

3. Check the logs:

   ```bash
   docker-compose logs -f
   ```

The Docker image will automatically detect the platform it's running on and enable or disable AS400 support accordingly.
