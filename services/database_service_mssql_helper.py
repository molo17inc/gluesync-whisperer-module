#!/usr/bin/env python3
"""
 * This file is part of Gluesync Whisperer.
 *
 * Gluesync Whisperer is dual-licensed under the following licenses:
 *
 * 1. GNU Affero General Public License (AGPL) v3.0
 *    See the LICENSE.AGPL file in the project root for more information.
 *
 * 2. Commercial License
 *    For commercial licensing, please contact the authors.
 *
 * This file may be used under the terms of either license.
"""

import logging
from typing import Dict, List, Any, Optional
from schemas import TableSchemaResponse

logger = logging.getLogger(__name__)

def get_mssql_table_schema_direct(db_connection, table_name, schema_name=None) -> TableSchemaResponse:
    """Get table schema for MS SQL Server using direct JDBC metadata calls."""
    from utils.db_connector import DatabaseConnector
    from models import DatabaseType
    
    # Default schema to 'dbo' if not provided
    schema = schema_name or 'dbo'
    logger.info(f"Using direct JDBC metadata approach for {schema}.{table_name}")
    
    # Create a database connector
    connector_db_type = db_connection.db_type
    if isinstance(connector_db_type, str):
        try:
            connector_db_type = DatabaseType[connector_db_type.upper()]
        except (KeyError, AttributeError):
            logger.warning(f"Unknown database type string: {connector_db_type}")
    
    db_connector = DatabaseConnector(
        db_type=connector_db_type,
        host=db_connection.host,
        port=db_connection.port,
        database=db_connection.database,
        username=db_connection.username,
        password=db_connection.password
    )
    
    # Connect to the database
    try:
        conn = db_connector.connect()
        logger.info(f"Connected to MS SQL Server database for direct schema retrieval")
        
        # Get JDBC metadata
        metadata = conn.jconn.getMetaData()
        
        # Try different case variations for the table name
        columns = {}
        primary_keys = []
        
        # First, get all tables to check if our table exists
        all_tables = []
        try:
            rs_tables = metadata.getTables(None, schema, "%", ["TABLE"])
            while rs_tables.next():
                table_schema = rs_tables.getString("TABLE_SCHEM")
                table_name_found = rs_tables.getString("TABLE_NAME")
                all_tables.append(f"{table_schema}.{table_name_found}")
            rs_tables.close()
            logger.info(f"Found {len(all_tables)} tables in database: {', '.join(all_tables)}")
        except Exception as e:
            logger.error(f"Error listing all tables: {str(e)}")
        
        # Try to find our table in the list
        found_table = None
        found_schema = None
        for table_entry in all_tables:
            parts = table_entry.split('.')
            if len(parts) == 2:
                table_schema, table_name_found = parts
                if table_name_found.upper() == table_name.upper():
                    found_table = table_name_found
                    found_schema = table_schema
                    logger.info(f"Found matching table: {found_schema}.{found_table}")
                    break
        
        # If table found, use the exact case for further queries
        if found_table:
            # Get columns
            try:
                logger.info(f"Getting columns for {found_schema}.{found_table}")
                rs_columns = metadata.getColumns(None, found_schema, found_table, "%")
                column_count = 0
                
                while rs_columns.next():
                    column_count += 1
                    column_name = rs_columns.getString("COLUMN_NAME")
                    column_type = rs_columns.getString("TYPE_NAME")
                    nullable = rs_columns.getString("IS_NULLABLE").upper() == "YES"
                    
                    try:
                        column_size = rs_columns.getInt("COLUMN_SIZE")
                    except:
                        column_size = 0
                        
                    try:
                        decimal_digits = rs_columns.getInt("DECIMAL_DIGITS")
                    except:
                        decimal_digits = 0
                    
                    # Add to columns dictionary
                    columns[column_name] = {
                        "name": column_name,
                        "type": column_type,
                        "nullable": nullable,
                        "default": None,  # Will be updated if available
                        "primary_key": False  # Will be updated later
                    }
                    
                    # Try to get default value
                    try:
                        columns[column_name]["default"] = rs_columns.getString("COLUMN_DEF")
                    except:
                        pass
                    
                    logger.info(f"Found column: {column_name} ({column_type})")
                
                rs_columns.close()
                logger.info(f"Retrieved {column_count} columns for {found_schema}.{found_table}")
            except Exception as e:
                logger.error(f"Error getting columns: {str(e)}")
            
            # Get primary keys
            try:
                logger.info(f"Getting primary keys for {found_schema}.{found_table}")
                rs_pk = metadata.getPrimaryKeys(None, found_schema, found_table)
                pk_count = 0
                
                while rs_pk.next():
                    pk_count += 1
                    pk_name = rs_pk.getString("COLUMN_NAME")
                    primary_keys.append(pk_name)
                    
                    # Mark as primary key in columns dictionary
                    if pk_name in columns:
                        columns[pk_name]["primary_key"] = True
                    
                    logger.info(f"Found primary key: {pk_name}")
                
                rs_pk.close()
                logger.info(f"Retrieved {pk_count} primary keys for {found_schema}.{found_table}")
            except Exception as e:
                logger.error(f"Error getting primary keys: {str(e)}")
                
                # If JDBC metadata approach fails, try direct SQL query
                try:
                    logger.info("Falling back to direct SQL query for primary keys")
                    cursor = conn.cursor()
                    pk_query = """
                    SELECT 
                        c.name AS column_name
                    FROM 
                        sys.indexes i
                    INNER JOIN 
                        sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                    INNER JOIN 
                        sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                    INNER JOIN 
                        sys.tables t ON i.object_id = t.object_id
                    INNER JOIN 
                        sys.schemas s ON t.schema_id = s.schema_id
                    WHERE 
                        i.is_primary_key = 1
                        AND t.name = ?
                        AND s.name = ?
                    ORDER BY 
                        ic.key_ordinal
                    """
                    cursor.execute(pk_query, [found_table, found_schema])
                    pk_rows = cursor.fetchall()
                    
                    for pk_row in pk_rows:
                        pk_name = pk_row[0]
                        primary_keys.append(pk_name)
                        
                        # Mark as primary key in columns dictionary
                        if pk_name in columns:
                            columns[pk_name]["primary_key"] = True
                        
                        logger.info(f"Found primary key from SQL query: {pk_name}")
                    
                    cursor.close()
                except Exception as e2:
                    logger.error(f"Error getting primary keys via SQL: {str(e2)}")
            
            # If still no columns, try direct SQL query
            if not columns:
                try:
                    logger.info("No columns retrieved from JDBC metadata, trying direct SQL query")
                    cursor = conn.cursor()
                    columns_query = """
                    SELECT 
                        c.name AS column_name,
                        c.column_id AS ordinal_position,
                        t.name AS data_type,
                        c.max_length AS length,
                        c.scale AS numeric_scale,
                        c.is_nullable AS is_nullable,
                        d.definition AS default_value,
                        CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
                    FROM 
                        sys.columns c
                    INNER JOIN 
                        sys.types t ON c.user_type_id = t.user_type_id
                    INNER JOIN 
                        sys.tables tbl ON c.object_id = tbl.object_id
                    INNER JOIN 
                        sys.schemas s ON tbl.schema_id = s.schema_id
                    LEFT JOIN 
                        sys.default_constraints d ON c.default_object_id = d.object_id
                    LEFT JOIN (
                        SELECT 
                            ic.column_id,
                            ic.object_id
                        FROM 
                            sys.indexes i
                        INNER JOIN 
                            sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                        WHERE 
                            i.is_primary_key = 1
                    ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
                    WHERE 
                        tbl.name = ?
                        AND s.name = ?
                    ORDER BY 
                        c.column_id
                    """
                    cursor.execute(columns_query, [found_table, found_schema])
                    column_rows = cursor.fetchall()
                    
                    for column_row in column_rows:
                        column_name = column_row[0]
                        data_type = column_row[2]
                        is_nullable = column_row[5] == 1
                        default_value = column_row[6]
                        is_primary_key = column_row[7] == 1
                        
                        columns[column_name] = {
                            "name": column_name,
                            "type": data_type,
                            "nullable": is_nullable,
                            "default": default_value,
                            "primary_key": is_primary_key
                        }
                        
                        if is_primary_key and column_name not in primary_keys:
                            primary_keys.append(column_name)
                        
                        logger.info(f"Found column from SQL query: {column_name} ({data_type})")
                    
                    cursor.close()
                except Exception as e:
                    logger.error(f"Error getting columns via SQL: {str(e)}")
        else:
            logger.error(f"Table {table_name} not found in any schema")
            
            # Try a more general approach - list all tables and columns
            try:
                cursor = conn.cursor()
                all_tables_query = """
                SELECT 
                    t.name AS table_name,
                    s.name AS schema_name
                FROM 
                    sys.tables t
                INNER JOIN 
                    sys.schemas s ON t.schema_id = s.schema_id
                ORDER BY 
                    s.name, t.name
                """
                cursor.execute(all_tables_query)
                all_tables_result = cursor.fetchall()
                logger.info(f"All tables in database: {all_tables_result}")
                cursor.close()
            except Exception as e:
                logger.error(f"Error listing all tables: {str(e)}")
        
        # Close the connection
        conn.close()
        
        return TableSchemaResponse(table_name=table_name, columns=columns, primary_keys=primary_keys)
    except Exception as e:
        logger.error(f"Error in direct JDBC metadata approach: {str(e)}")
        return TableSchemaResponse(table_name=table_name, columns={}, primary_keys=[])
