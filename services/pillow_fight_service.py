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

import json
import logging
import random
import string
import threading
import time
import uuid
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models import (
    ConnectionStatus,
    DatabaseConnection,
    DatabaseType,
    OperationType,
    PillowFightJobStatus as JobStatus,
    PillowFightTableStatus,
    TableConfig,
)
from schemas import TableSchemaResponse
from services.database_service import DatabaseService
from services.pillow_fight_job_store import PillowFightJobStore
from services.table_service import TableService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global registry for active pillow fights
active_pillow_fights = {}

class PillowFightService:
    """Service to manage database pillow fights (automated operations)."""
    
    def __init__(self, db):
        """Initialize the pillow fight service."""
        self.db = db
        self.db_service = DatabaseService(db)
        self.table_service = TableService(db)
        self.job_store = PillowFightJobStore(db)
        self.stop_events = {}  # {(job_id, table_id): threading.Event}
        self.threads = {}  # {(job_id, table_id): threading.Thread}
        self.status = {}  # {(job_id, table_id): status_dict}
        self._job_threads: Dict[str, Dict[int, threading.Thread]] = {}
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._schema_cache: Dict[Tuple[int, str, Optional[str]], TableSchemaResponse] = {}
        self._resume_lock = threading.Lock()
        self._job_lock = threading.Lock()
        self._resumed = False
        self.error_threshold = int(os.getenv("PILLOW_FIGHT_TABLE_ERROR_THRESHOLD", "5"))
    
    def _ensure_jdbc_connection(self, engine):
        """Ensure a JDBC-based engine has an active connection and return it."""
        if not hasattr(engine, "connection"):
            return None
        if engine.connection:
            return engine.connection
        connect_method = getattr(engine, "connect", None)
        if callable(connect_method):
            connect_result = connect_method()
            if connect_result is False:
                raise RuntimeError("Unable to establish JDBC connection for pillow fight operation")
        if not engine.connection:
            raise RuntimeError("JDBC engine failed to expose a valid connection after connect()")
        return engine.connection
    
    def _execute_sqlalchemy(
        self,
        engine,
        stmt,
        params=None,
        fetch=False,
        fetchone=False,
        as_dict=False,
        return_result=False,
    ):
        """Execute a statement using a SQLAlchemy-style engine/connection."""
        if not hasattr(engine, "connect"):
            raise RuntimeError("Engine does not expose a SQLAlchemy-compatible connect() method")
        
        conn_candidate = engine.connect()
        if isinstance(conn_candidate, bool):
            raise RuntimeError(
                "Engine.connect() returned a boolean result. "
                "This likely indicates a JDBC connector path should be used instead."
            )
        
        if hasattr(conn_candidate, "__enter__"):
            with conn_candidate as conn:
                return self._run_sqlalchemy_statement(
                    conn,
                    stmt,
                    params,
                    fetch,
                    fetchone,
                    as_dict,
                    return_result,
                )
        
        conn = conn_candidate
        close_after = hasattr(conn, "close")
        try:
            return self._run_sqlalchemy_statement(
                conn,
                stmt,
                params,
                fetch,
                fetchone,
                as_dict,
                return_result,
            )
        finally:
            if close_after:
                try:
                    conn.close()
                except Exception:
                    pass
    
    def _run_sqlalchemy_statement(
        self,
        conn,
        stmt,
        params=None,
        fetch=False,
        fetchone=False,
        as_dict=False,
        return_result=False,
    ):
        """Execute a statement on an open SQLAlchemy connection."""
        bound_params = params or []
        result = conn.execute(stmt, bound_params)
        if return_result:
            return result
        if not fetch:
            return None
        
        keys = result.keys() if as_dict else None
        if fetchone:
            row = result.fetchone()
            if not row:
                return None
            if as_dict and keys:
                return {key: row[idx] for idx, key in enumerate(keys)}
            return row
        
        rows = result.fetchall()
        if as_dict and keys:
            return [
                {key: row[idx] for idx, key in enumerate(keys)}
                for row in rows
            ]
        return rows
    
    def _format_row(self, row, columns, as_dict):
        if not as_dict or not columns:
            return row
        return {
            str(columns[i]): row[i]
            for i in range(min(len(columns), len(row)))
        }
    
    def _execute_statement(
        self,
        engine,
        stmt,
        params=None,
        fetch=False,
        fetchone=False,
        as_dict=False,
        return_sqlalchemy_result=False,
    ):
        params = params or []
        if hasattr(engine, "execute_query") and callable(engine.execute_query):
            result = engine.execute_query(stmt, params)
            if fetchone:
                return result[0] if result else None
            if fetch:
                return result
            return None
        
        jdbc_conn = self._ensure_jdbc_connection(engine)
        if jdbc_conn:
            cursor = jdbc_conn.cursor()
            try:
                cursor.execute(stmt, params)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                if fetchone:
                    row = cursor.fetchone()
                    if not row:
                        return None
                    return self._format_row(row, columns, as_dict)
                if fetch:
                    rows = cursor.fetchall()
                    return [
                        self._format_row(row, columns, as_dict)
                        for row in rows
                    ]
                jdbc_conn.commit()
                return None
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass
        
        return self._execute_sqlalchemy(
            engine,
            stmt,
            params=params,
            fetch=fetch,
            fetchone=fetchone,
            as_dict=as_dict,
            return_result=return_sqlalchemy_result,
        )
    
    def _schema_cache_key(self, connection: DatabaseConnection, table: TableConfig) -> Tuple[int, str, Optional[str]]:
        return (connection.id, table.table_name, table.schema_name)

    def _schema_is_valid(self, schema: Optional[TableSchemaResponse]) -> bool:
        if not schema:
            return False
        columns = getattr(schema, "columns", None)
        return isinstance(columns, dict) and bool(columns)

    def _sanitize_schema(self, schema: TableSchemaResponse) -> TableSchemaResponse:
        columns = getattr(schema, "columns", {}) or {}
        if isinstance(columns, list):
            column_dict: Dict[str, Any] = {}
            for entry in columns:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    if name:
                        column_dict[str(name)] = entry
            columns = column_dict
        elif isinstance(columns, dict):
            columns = {str(name): definition for name, definition in columns.items()}
        schema.columns = columns  # type: ignore[assignment]
        schema.primary_keys = [str(pk) for pk in getattr(schema, "primary_keys", []) if pk is not None]  # type: ignore[assignment]
        return schema

    def _load_table_schema(self, connection: DatabaseConnection, table: TableConfig) -> TableSchemaResponse:
        cache_key = self._schema_cache_key(connection, table)
        schema = self._schema_cache.get(cache_key)
        if schema and not self._schema_is_valid(schema):
            logger.warning(
                f"Cached schema for {table.schema_name}.{table.table_name} is empty; refreshing from database"
            )
            self._schema_cache.pop(cache_key, None)
            schema = None
        if not schema:
            fresh_schema = self.db_service.get_table_schema(connection.id, table.table_name, table.schema_name)
            schema = self._sanitize_schema(fresh_schema)
            if not self._schema_is_valid(schema):
                raise ValueError(
                    f"Schema introspection returned no columns for {table.schema_name}.{table.table_name}"
                )
            self._schema_cache[cache_key] = schema
        return schema
    
    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Best-effort conversion of various integer-like objects (str, BigInteger, etc.) to int."""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(str(value))
            except Exception:
                return default
    
    def _coerce_value_for_column(self, column_info: Optional[Dict[str, Any]], value: Any) -> Any:
        """Return a best-effort typed value based on column metadata (used for PK comparisons)."""
        if value is None or not column_info:
            return value
        col_type = str(column_info.get("type", "")).lower()
        if any(token in col_type for token in ("int", "serial", "bigint", "smallint")):
            return self._safe_int(value, 0)
        return value
    
    @staticmethod
    def _first_non_none_value(row: Any) -> Optional[Any]:
        """Return the first non-None scalar value from supported row containers."""
        if row is None:
            return None
        if isinstance(row, dict):
            for value in row.values():
                if value is not None:
                    return value
            return None
        if isinstance(row, (list, tuple)):
            for value in row:
                if value is not None:
                    return value
            return None
        return row
    
    def _generate_sequential_primary_key(self, engine, table: TableConfig, column_name: str) -> int:
        """Generate a unique numeric primary key by querying MAX(column) and adding a delta."""
        table_name = table.table_name
        if table.schema_name:
            table_name = f"{table.schema_name}.{table_name}"
        max_query = f"SELECT MAX({column_name}) FROM {table_name}"
        max_value = 0
        try:
            if hasattr(engine, "execute_query") and callable(engine.execute_query):
                result = engine.execute_query(max_query)
                if result:
                    candidate = self._first_non_none_value(result[0])
                    if candidate is not None:
                        max_value = self._safe_int(candidate, 0)
            elif hasattr(engine, "connection") and engine.connection:
                cursor = engine.connection.cursor()
                cursor.execute(max_query)
                row = cursor.fetchone()
                cursor.close()
                if row and row[0] is not None:
                    max_value = self._safe_int(row[0], 0)
            elif hasattr(engine, "execute") and callable(engine.execute):
                result = engine.execute(max_query)
                row = result.fetchone()
                if row:
                    candidate = (
                        row[0]
                        if isinstance(row, (list, tuple))
                        else self._first_non_none_value(row)
                    )
                    if candidate is not None:
                        max_value = self._safe_int(candidate, 0)
        except Exception as e:
            logger.warning(f"Unable to determine max value for {table_name}.{column_name}: {e}")
        # Add random delta to reduce collisions when multiple threads insert concurrently
        return max_value + random.randint(1, 100)

    def _ensure_resumed(self):
        """Resume any pending/running jobs after a restart."""
        with self._resume_lock:
            if self._resumed:
                return
            try:
                self._resume_active_jobs()
            finally:
                self._resumed = True
    
    def _resume_active_jobs(self):
        """Reload jobs from persistence and restart table threads."""
        active_jobs = self.job_store.get_jobs_with_tables_by_status(
            [JobStatus.PENDING.value, JobStatus.RUNNING.value],
            table_statuses=[
                PillowFightTableStatus.PENDING.value,
                PillowFightTableStatus.RUNNING.value,
            ],
        )
        if not active_jobs:
            return
        
        logger.info(f"Resuming {len(active_jobs)} pillow fight jobs from persistent store")
        for entry in active_jobs:
            job = entry["job"]
            tables = entry["tables"]
            job_id = job["job_id"]
            try:
                connection = self._get_connection(job["connection_id"])
                operation_types = json.loads(job["operation_types"]) if job.get("operation_types") else []
                operation_delay = job.get("operation_delay", 1.0)
                batch_size = job.get("batch_size", 1)
                
                self._active_jobs[job_id] = {
                    "connection_id": job["connection_id"],
                    "operation_types": operation_types,
                    "operation_delay": operation_delay,
                    "batch_size": batch_size,
                }
                self._job_threads[job_id] = {}
                
                for table_entry in tables:
                    table_id = table_entry["table_config_id"]
                    table = self._get_table(table_id)
                    if not table:
                        logger.warning(f"Skipping resume for missing table {table_id}")
                        continue
                    
                    self._start_table_job(
                        job_id=job_id,
                        connection=connection,
                        table=table,
                        operation_types=operation_types,
                        operation_delay=operation_delay,
                        batch_size=batch_size,
                        resume=True,
                    )
                
                self.job_store.mark_job_started(job_id)
            except Exception as exc:
                logger.error(f"Failed to resume pillow fight job {job_id}: {exc}", exc_info=True)
    
    def start_pillow_fight(
        self,
        connection_id: int,
        table_ids: List[int],
        operation_types: List[str],
        operation_delay: float = 1.0,
        batch_size: int = 1,
    ) -> str:
        """Start a pillow fight job; returns job_id."""
        self._ensure_resumed()
        with self._job_lock:
            job_id = str(uuid.uuid4())
            logger.info(f"Starting pillow fight job {job_id} for connection {connection_id}")
            
            # Normalize operation types if ALL requested
            normalized_ops = self._normalize_operation_types(operation_types)
            
            # Validate tables and prevent conflicts
            available_tables = self.table_service.get_tables_by_connection(connection_id)
            available_ids = {table.id for table in available_tables}
            missing = [tid for tid in table_ids if tid not in available_ids]
            if missing:
                raise ValueError(f"Tables not found for connection {connection_id}: {missing}")
            
            conflicts = self.job_store.find_active_table_conflicts(table_ids)
            if conflicts:
                raise ValueError(
                    f"Tables already running in other jobs: {conflicts}. Stop them or wait until completion."
                )
            
            # Persist job record and table entries
            self.job_store.create_job(
                job_id=job_id,
                connection_id=connection_id,
                table_ids=table_ids,
                operation_types=normalized_ops,
                operation_delay=operation_delay,
                batch_size=batch_size,
            )
            
            connection = self._get_connection(connection_id)
            self._active_jobs[job_id] = {
                "connection_id": connection_id,
                "operation_types": normalized_ops,
                "operation_delay": operation_delay,
                "batch_size": batch_size,
            }
            self._job_threads[job_id] = {}
            
            for table_id in table_ids:
                table = self._get_table(table_id)
                if not table:
                    logger.warning(f"Skipping missing table {table_id} for job {job_id}")
                    continue
                self._start_table_job(
                    job_id=job_id,
                    connection=connection,
                    table=table,
                    operation_types=normalized_ops,
                    operation_delay=operation_delay,
                    batch_size=batch_size,
                )
            
            self.job_store.mark_job_started(job_id)
            return job_id

    def _normalize_operation_types(self, operation_types: List[str]) -> List[str]:
        """Normalize requested operations; expand ALL to concrete operations."""
        if not operation_types:
            return [
                OperationType.INSERT.value,
                OperationType.UPDATE.value,
                OperationType.DELETE.value,
            ]
        normalized = [op.lower() for op in operation_types]
        if OperationType.ALL.value in normalized or "all" in normalized:
            return [
                OperationType.INSERT.value,
                OperationType.UPDATE.value,
                OperationType.DELETE.value,
            ]
        valid_ops = {op.value for op in OperationType if op is not OperationType.ALL}
        invalid = [op for op in normalized if op not in valid_ops]
        if invalid:
            raise ValueError(f"Invalid operation types requested: {invalid}")
        return normalized

    def _get_connection(self, connection_id: int) -> DatabaseConnection:
        connection = self.db_service.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection with ID {connection_id} not found")
        return connection

    def _get_table(self, table_id: int) -> Optional[TableConfig]:
        return self.table_service.get_table(table_id)

    def _start_table_job(
        self,
        job_id: str,
        connection: DatabaseConnection,
        table: TableConfig,
        operation_types: List[str],
        operation_delay: float,
        batch_size: int,
        resume: bool = False,
    ) -> None:
        key = (job_id, table.id)
        stop_event = self.stop_events.get(key)
        if not stop_event:
            stop_event = threading.Event()
            self.stop_events[key] = stop_event
        
        self.status[key] = {
            "job_id": job_id,
            "connection_id": connection.id,
            "table_id": table.id,
            "table_name": table.table_name,
            "operation_types": operation_types,
            "operation_delay": operation_delay,
            "batch_size": batch_size,
            "start_time": datetime.now().isoformat(),
            "last_operation_time": None,
            "status": "running" if resume else "pending",
            "operations": {
                "insert": 0,
                "update": 0,
                "delete": 0,
                "errors": 0,
            },
        }
        
        self.job_store.update_table_status(job_id, table.id, PillowFightTableStatus.RUNNING)
        thread = threading.Thread(
            target=self._run_table_job,
            args=(
                job_id,
                connection,
                table,
                operation_types,
                operation_delay,
                batch_size,
                stop_event,
                key,
            ),
            daemon=True,
        )
        self.threads[key] = thread
        self._job_threads.setdefault(job_id, {})[table.id] = thread
        thread.start()
    
    def _serialize_job(self, job: Dict[str, Any], tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert raw DB rows into API-friendly job payload."""
        raw_ops = job.get("operation_types")
        operation_types: List[str] = []
        if isinstance(raw_ops, list):
            operation_types = [str(op).lower() for op in raw_ops]
        elif isinstance(raw_ops, str):
            try:
                parsed = json.loads(raw_ops)
                if isinstance(parsed, list):
                    operation_types = [str(op).lower() for op in parsed]
                elif parsed:
                    operation_types = [str(parsed).lower()]
            except json.JSONDecodeError:
                operation_types = [raw_ops.lower()]
        elif raw_ops:
            operation_types = [str(raw_ops).lower()]
        if not operation_types:
            operation_types = [
                OperationType.INSERT.value,
                OperationType.UPDATE.value,
                OperationType.DELETE.value,
            ]
        
        serialized_tables: List[Dict[str, Any]] = []
        for table_row in tables:
            table_config = self.table_service.get_table(table_row["table_config_id"])
            serialized_tables.append(
                {
                    "job_id": job["job_id"],
                    "table_id": table_row["table_config_id"],
                    "table_name": table_config.table_name if table_config else None,
                    "schema_name": table_config.schema_name if table_config else None,
                    "status": table_row.get("status"),
                    "insert_count": table_row.get("insert_count", 0),
                    "update_count": table_row.get("update_count", 0),
                    "delete_count": table_row.get("delete_count", 0),
                    "error_count": table_row.get("error_count", 0),
                    "last_operation_at": table_row.get("last_operation_at"),
                    "resume_cursor": table_row.get("resume_cursor"),
                }
            )
        
        return {
            "job_id": job["job_id"],
            "connection_id": job["connection_id"],
            "status": job.get("status"),
            "operation_types": operation_types,
            "operation_delay": job.get("operation_delay", 1.0),
            "batch_size": job.get("batch_size", 1),
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "last_heartbeat": job.get("last_heartbeat"),
            "error_message": job.get("error_message"),
            "tables": serialized_tables,
        }
    
    def _refresh_job_status(self, job_id: str) -> None:
        """Evaluate aggregate table statuses and update job record."""
        job = self.job_store.get_job(job_id)
        if not job:
            return
        table_rows = self.job_store.get_job_tables(job_id)
        if not table_rows:
            return
        
        statuses = [row.get("status") for row in table_rows]
        new_status: JobStatus
        if any(status == PillowFightTableStatus.ERROR.value for status in statuses):
            new_status = JobStatus.ERROR
        elif any(status == PillowFightTableStatus.RUNNING.value for status in statuses):
            new_status = JobStatus.RUNNING
        elif all(status == PillowFightTableStatus.COMPLETED.value for status in statuses):
            new_status = JobStatus.COMPLETED
        elif all(status == PillowFightTableStatus.STOPPED.value for status in statuses):
            new_status = JobStatus.STOPPED
        elif all(status == PillowFightTableStatus.PENDING.value for status in statuses):
            new_status = JobStatus.PENDING
        else:
            new_status = JobStatus.RUNNING
        
        self.job_store.update_job_status(job_id, new_status)
        if new_status in {JobStatus.COMPLETED, JobStatus.STOPPED, JobStatus.ERROR}:
            self._active_jobs.pop(job_id, None)
            self._job_threads.pop(job_id, None)

    def _stop_table(self, job_id: str, table_id: int, *, mark_stopped: bool = True) -> None:
        key = (job_id, table_id)
        stop_event = self.stop_events.get(key)
        if stop_event:
            stop_event.set()
        thread = self.threads.get(key)
        if thread and thread.is_alive():
            thread.join(timeout=5)
        if mark_stopped:
            self.job_store.update_table_status(
                job_id,
                table_id,
                PillowFightTableStatus.STOPPED,
                last_operation_at=datetime.utcnow().isoformat(),
            )
        self.stop_events.pop(key, None)
        self.threads.pop(key, None)
        self.status.pop(key, None)
        if job_id in self._job_threads and table_id in self._job_threads[job_id]:
            del self._job_threads[job_id][table_id]
        if job_id in self._job_threads and not self._job_threads[job_id]:
            self._job_threads.pop(job_id, None)
        self._refresh_job_status(job_id)
    
    def stop_pillow_fight(self, connection_id: int, table_id: int) -> None:
        """Stop a pillow fight for a connection and table (legacy helper)."""
        job_id = self.job_store.get_active_job_for_table(connection_id, table_id)
        if not job_id:
            logger.info(f"No active pillow fight job found for connection {connection_id} and table {table_id}")
            return
        self._stop_table(job_id, table_id)
        logger.info(f"Stopped pillow fight for job {job_id}, connection {connection_id}, table {table_id}")
    
    def stop_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Stop an entire pillow fight job."""
        self._ensure_resumed()
        job = self.job_store.get_job(job_id)
        if not job:
            return None
        tables = self.job_store.get_job_tables(job_id)
        for table_row in tables:
            if table_row.get("status") in (
                PillowFightTableStatus.PENDING.value,
                PillowFightTableStatus.RUNNING.value,
            ):
                self._stop_table(job_id, table_row["table_config_id"])
        self.job_store.update_job_status(job_id, JobStatus.STOPPED)
        self._active_jobs.pop(job_id, None)
        self._job_threads.pop(job_id, None)
        return self.get_job_status(job_id)
    
    def stop_table_job(self, job_id: str, table_id: int) -> Optional[Dict[str, Any]]:
        """Stop a single table inside a job and return updated job status."""
        job = self.job_store.get_job(job_id)
        if not job:
            return None
        self._stop_table(job_id, table_id)
        return self.get_job_status(job_id)
    
    def list_jobs(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List pillow fight jobs with tables."""
        self._ensure_resumed()
        jobs_with_tables = self.job_store.get_jobs_with_tables(search)
        serialized: List[Dict[str, Any]] = []
        for entry in jobs_with_tables:
            serialized.append(self._serialize_job(entry["job"], entry["tables"]))
        return serialized
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a single pillow fight job status."""
        job = self.job_store.get_job(job_id)
        if not job:
            return None
        tables = self.job_store.get_job_tables(job_id)
        return self._serialize_job(job, tables)
    
    def get_status(self, connection_id: int, table_id: int) -> Optional[Dict[str, Any]]:
        """Get the status of a pillow fight."""
        key = (connection_id, table_id)
        
        # Check if a pillow fight is running for this table
        if key not in self.status:
            return None
        
        # Check if the thread is still alive
        if key in self.threads and not self.threads[key].is_alive():
            self.status[key]["status"] = "stopped"
            self.status[key]["duration"] = (
                datetime.now() - datetime.fromisoformat(self.status[key]["start_time"])
            ).total_seconds()
        
        return self.status[key]
    
    def _run_table_job(
        self,
        job_id: str,
        connection: DatabaseConnection,
        table: TableConfig,
        operation_types: List[str],
        operation_delay: float,
        batch_size: int,
        stop_event: threading.Event,
        key: tuple,
    ) -> None:
        """Run the pillow fight loop for a single table inside a job."""
        logger.info(f"Starting pillow fight job {job_id} table {table.table_name}")
        
        engine = None
        operations_performed = 0
        
        while not stop_event.is_set():
            try:
                if engine is None:
                    logger.info(f"Creating database engine for connection {connection.id}")
                    if connection.db_type in [DatabaseType.AS400, DatabaseType.MSSQL] or (
                        isinstance(connection.db_type, str)
                        and connection.db_type.upper() in ["AS400", "MSSQL"]
                    ):
                        from utils.db_connector import DatabaseConnector
                        
                        connector_db_type = connection.db_type
                        if isinstance(connection.db_type, str):
                            try:
                                connector_db_type = DatabaseType[connection.db_type.upper()]
                            except (KeyError, AttributeError):
                                logger.warning(f"Unknown database type string: {connection.db_type}")
                        
                        database_name = connection.database
                        db_connector = DatabaseConnector(
                            db_type=connector_db_type,
                            host=connection.host,
                            port=connection.port,
                            database=database_name,
                            username=connection.username,
                            password=connection.password,
                        )
                        db_connector.connect()
                        if not db_connector.connection or not hasattr(db_connector.connection, "cursor"):
                            raise Exception(f"Failed to establish a valid connection to {connection.db_type} database")
                        engine = db_connector
                        logger.info(f"Created direct JDBC connection for {connection.db_type} database")
                    else:
                        engine = self.db_service.get_engine(connection)
                        logger.info(f"Using DatabaseService engine for {connection.db_type}")
                    
                    status_entry = self.status.get(key)
                    if status_entry:
                        status_entry["status"] = PillowFightTableStatus.RUNNING.value
                    self.job_store.update_table_status(
                        job_id,
                        table.id,
                        PillowFightTableStatus.RUNNING,
                        last_operation_at=datetime.utcnow().isoformat(),
                    )
                
                batch_operations = 0
                for _ in range(batch_size):
                    if stop_event.is_set():
                        break
                    
                    op_type = random.choice(operation_types)
                    op_type_upper = op_type.upper()
                    try:
                        if op_type_upper == "INSERT":
                            self._perform_insert(engine, connection, table)
                            self.status[key]["operations"]["insert"] += 1
                            self.job_store.increment_operation(job_id, table.id, "insert")
                        elif op_type_upper == "UPDATE":
                            self._perform_update(engine, connection, table)
                            self.status[key]["operations"]["update"] += 1
                            self.job_store.increment_operation(job_id, table.id, "update")
                        elif op_type_upper == "DELETE":
                            self._perform_delete(engine, connection, table)
                            self.status[key]["operations"]["delete"] += 1
                            self.job_store.increment_operation(job_id, table.id, "delete")
                        
                        now_iso = datetime.utcnow().isoformat()
                        self.status[key]["last_operation_time"] = now_iso
                        self.job_store.update_table_status(
                            job_id,
                            table.id,
                            PillowFightTableStatus.RUNNING,
                            last_operation_at=now_iso,
                        )
                        operations_performed += 1
                        batch_operations += 1
                    except Exception as op_exc:
                        logger.error(f"Error performing {op_type_upper} on {table.table_name}: {op_exc}")
                        self.status[key]["operations"]["errors"] += 1
                        self.job_store.increment_error(job_id, table.id)
                        self.job_store.update_table_status(
                            job_id,
                            table.id,
                            PillowFightTableStatus.RUNNING,
                            last_operation_at=datetime.utcnow().isoformat(),
                            error_message=str(op_exc),
                        )
                        error_count = self.status[key]["operations"]["errors"]
                        if error_count >= self.error_threshold:
                            threshold_message = (
                                f"Reached error threshold ({self.error_threshold}) for "
                                f"{table.schema_name}.{table.table_name}. Last error: {op_exc}"
                            )
                            logger.error(threshold_message)
                            self.status[key]["status"] = PillowFightTableStatus.ERROR.value
                            self.status[key]["error"] = threshold_message
                            self.job_store.update_table_status(
                                job_id,
                                table.id,
                                PillowFightTableStatus.ERROR,
                                last_operation_at=datetime.utcnow().isoformat(),
                                error_message=threshold_message,
                            )
                            self.job_store.update_job_status(
                                job_id,
                                JobStatus.ERROR,
                                error_message=threshold_message,
                            )
                            stop_event.set()
                            break
                
                self.job_store.heartbeat(job_id)
                if stop_event.is_set():
                    break
                time.sleep(operation_delay)
            except Exception as loop_exc:
                logger.error(
                    f"Error in pillow fight thread job {job_id} connection {connection.id} table {table.id}: {loop_exc}",
                    exc_info=True,
                )
                self.status[key]["status"] = PillowFightTableStatus.ERROR.value
                self.status[key]["error"] = str(loop_exc)
                self.job_store.update_table_status(
                    job_id,
                    table.id,
                    PillowFightTableStatus.ERROR,
                    last_operation_at=datetime.utcnow().isoformat(),
                    error_message=str(loop_exc),
                )
                self.job_store.update_job_status(job_id, JobStatus.ERROR, error_message=str(loop_exc))
                engine = None
                time.sleep(5)
        
        status_entry = self.status.get(key)
        end_time = datetime.utcnow()
        if status_entry:
            status_entry["duration"] = (
                end_time - datetime.fromisoformat(status_entry["start_time"])
            ).total_seconds()
        
        if status_entry and status_entry.get("status") == PillowFightTableStatus.ERROR.value:
            logger.info(f"Pillow fight job {job_id} table {table.id} ended with error")
            self._refresh_job_status(job_id)
            return
        
        if stop_event.is_set():
            self.job_store.update_table_status(
                job_id,
                table.id,
                PillowFightTableStatus.STOPPED,
                last_operation_at=end_time.isoformat(),
            )
            if status_entry:
                status_entry["status"] = PillowFightTableStatus.STOPPED.value
        else:
            self.job_store.mark_table_completed(job_id, table.id)
            if status_entry:
                status_entry["status"] = PillowFightTableStatus.COMPLETED.value
        logger.info(
            f"Pillow fight job {job_id} completed {operations_performed} operations for table {table.table_name}"
        )
        self._refresh_job_status(job_id)
    
    def _build_insert_payload(
        self,
        engine,
        connection: DatabaseConnection,
        table: TableConfig,
        columns_dict: Dict[str, Any],
        primary_keys: List[str],
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for col_name, col_info in columns_dict.items():
            is_primary = col_name in primary_keys or col_info.get("primary_key", False)
            is_auto_increment = col_info.get("auto_increment", False)

            if is_primary and is_auto_increment:
                logger.info(f"Skipping auto-increment primary key column: {col_name}")
                continue

            column_type = col_info.get("type")
            if hasattr(column_type, "__dict__"):
                column_type._col_name = col_name

            if is_primary and not is_auto_increment:
                logger.info(f"Generating value for non auto-increment primary key: {col_name}")
                value = self._generate_sequential_primary_key(engine, table, col_name)
            else:
                value = self._generate_random_data(column_type)

            data[col_name] = value
        return data

    def _perform_insert(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform an insert operation on a table."""
        try:
            logger.info(f"Starting insert operation for table {table.table_name}")

            if engine is None:
                error_msg = f"Could not establish connection to database for {table.schema_name}.{table.table_name}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info(
                f"Getting table schema for connection ID {connection.id}, table {table.table_name}, schema {table.schema_name}"
            )
            try:
                cache_key = (connection.id, table.table_name, table.schema_name)
                if cache_key in self._schema_cache:
                    logger.info(f"Using cached schema for {table.schema_name}.{table.table_name}")
                    schema_info = self._schema_cache[cache_key]
                else:
                    logger.info(
                        f"Schema cache miss for {table.schema_name}.{table.table_name}, retrieving from database"
                    )
                    schema_info = self.db_service.get_table_schema(
                        connection.id, table.table_name, table.schema_name
                    )
                    self._schema_cache[cache_key] = schema_info

                logger.info(f"Schema info received: {schema_info}")
                columns_dict = schema_info.columns
                primary_keys = schema_info.primary_keys
                logger.info(f"Found {len(columns_dict)} columns and {len(primary_keys)} primary keys")
            except Exception as e:
                logger.error(f"Error getting table schema for {table.schema_name}.{table.table_name}: {str(e)}")
                raise

            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"

            placeholders = ", ".join(["?" for _ in range(len(columns_dict))])
            stmt_template = f"INSERT INTO {table_name} ({{columns}}) VALUES ({placeholders})"

            max_attempts = 5
            last_error: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                data = self._build_insert_payload(engine, connection, table, columns_dict, primary_keys)

                if not data:
                    logger.info(f"No columns to insert data for in {table.table_name}")
                    return

                stmt = stmt_template.format(columns=", ".join(data.keys()))
                params = list(data.values())

                logger.info(f"Prepared insert statement: {stmt}")
                logger.info(f"With values: {params}")

                try:
                    self._execute_statement(
                        engine,
                        stmt,
                        params=params,
                    )
                    logger.info(f"Successfully inserted record into {table.table_name}")
                    return
                except Exception as exc:
                    last_error = exc
                    error_message = str(exc).lower()
                    is_duplicate = any(
                        keyword in error_message for keyword in ["duplicate", "sql0803", "key duplicata"]
                    )
                    if is_duplicate and attempt < max_attempts:
                        logger.warning(
                            f"Duplicate primary key detected for {table.schema_name}.{table.table_name}. "
                            f"Retrying insert attempt {attempt}/{max_attempts} with regenerated values."
                        )
                        time.sleep(0.1)
                        continue
                    raise

            if last_error:
                raise last_error

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error performing insert on {table.table_name}: {error_message}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

            if any(
                keyword in error_message.lower()
                for keyword in ["foreign key constraint", "constraint", "reference", "fk"]
            ):
                import re

                table_match = re.search(r'table "([^"]+)"', error_message) or re.search(r"table ([^,]+),", error_message)
                column_match = re.search(r'column "([^"]+)"', error_message) or re.search(r"column '([^']+)'", error_message)

                referenced_table = table_match.group(1) if table_match else "referenced table"
                referenced_column = column_match.group(1) if column_match else "referenced column"

                logger.warning(f"Foreign key constraint violation detected on {table.table_name}")
                logger.warning("The operation failed because a foreign key constraint prevents the action.")
                logger.warning(f"Referenced table: {referenced_table}, Column: {referenced_column}")
                logger.warning("To fix this issue, you can:")
                logger.warning(
                    f"1. Enable cascade_delete for the {table.table_name} table in your configuration"
                )
                logger.warning(
                    f"2. Ensure the referenced records in {referenced_table} exist before inserting into {table.table_name}"
                )
                logger.warning("3. Use the update_cascade_delete.py script to update your configuration")

                if hasattr(table, "id"):
                    logger.warning(f"You can run: python update_cascade_delete.py --table_id {table.id} --enable True")

            raise
    
    def _perform_update(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform an update operation on a table."""
        try:
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return
                
            # Get the table schema with caching
            try:
                # Check if schema is in cache
                cache_key = (connection.id, table.table_name, table.schema_name)
                if cache_key in self._schema_cache:
                    logger.info(f"Using cached schema for {table.schema_name}.{table.table_name}")
                    schema_info = self._schema_cache[cache_key]
                else:
                    logger.info(f"Schema cache miss for {table.schema_name}.{table.table_name}, retrieving from database")
                    schema_info = self.db_service.get_table_schema(connection.id, table.table_name, table.schema_name)
                    # Cache the schema
                    self._schema_cache[cache_key] = schema_info
                
                # Access columns and primary_keys as attributes of the TableSchemaResponse object
                columns_dict = schema_info.columns
                primary_keys = schema_info.primary_keys
            except Exception as e:
                logger.error(f"Error getting table schema for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # First, get a random existing record
            try:
                existing_record = self._get_random_record(engine, table)
                
                if not existing_record:
                    logger.info(f"No records found in {table.table_name} for update")
                    return
            except Exception as e:
                logger.error(f"Error getting random record for {table.schema_name}.{table.table_name}: {str(e)}")
                raise
            
            # Generate random data for each column, excluding primary keys
            data = {}
            for col_name, col_info in columns_dict.items():
                if col_name not in primary_keys:
                    # Generate random data based on column type and name
                    column_type = col_info["type"]
                    # Add column name as an attribute to the column_type if it's an object
                    if hasattr(column_type, '__dict__'):
                        column_type._col_name = col_name
                    data[col_name] = self._generate_random_data(column_type)
            
            # If no data to update (all columns are primary keys), return
            if not data:
                logger.info(f"No columns to update in {table.table_name}")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_values = []
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = ?")
                    pk_info = columns_dict.get(pk)
                    where_values.append(self._coerce_value_for_column(pk_info, existing_record[pk]))
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table.table_name}")
                return
            
            # Build the update statement
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # For MS SQL Server, we need to handle the parameter placeholders differently
            is_mssql = connection.db_type.lower() == 'mssql'
            
            set_clauses = [f"{col} = ?" for col in data.keys()]
            
            stmt = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
            
            logger.info(f"Prepared update statement: {stmt}")
            logger.info(f"With set values: {list(data.values())} and where values: {where_values}")
            
            self._execute_statement(
                engine,
                stmt,
                params=list(data.values()) + where_values,
            )
            
            logger.info(f"Updated record in {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing update on {table.table_name}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _perform_delete(self, engine, connection: DatabaseConnection, table: TableConfig) -> None:
        """Perform a delete operation on a table."""
        try:
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return
                
            # Get the table schema with caching
            try:
                # Check if schema is in cache
                cache_key = (connection.id, table.table_name, table.schema_name)
                if cache_key in self._schema_cache:
                    logger.info(f"Using cached schema for {table.schema_name}.{table.table_name}")
                    schema_info = self._schema_cache[cache_key]
                else:
                    logger.info(f"Schema cache miss for {table.schema_name}.{table.table_name}, retrieving from database")
                    schema_info = self.db_service.get_table_schema(connection.id, table.table_name, table.schema_name)
                    # Cache the schema
                    self._schema_cache[cache_key] = schema_info
                
                # Access schema attributes
                columns_dict = schema_info.columns
                primary_keys = schema_info.primary_keys
            except Exception as e:
                logger.error(f"Error getting table schema for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # First, get a random existing record
            try:
                existing_record = self._get_random_record(engine, table)
                
                if not existing_record:
                    logger.info(f"No records found in {table.table_name} for delete")
                    return
            except Exception as e:
                logger.error(f"Error getting random record for {table.schema_name}.{table.table_name}: {str(e)}")
                return
            
            # Build the where clause for the primary keys
            where_clauses = []
            where_values = []
            for pk in primary_keys:
                if pk in existing_record:
                    where_clauses.append(f"{pk} = ?")
                    where_values.append(existing_record[pk])
            
            if not where_clauses:
                logger.error(f"No primary key values found for record in {table.table_name}")
                return
            
            # Build the delete statement
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # For MS SQL Server, we need to handle the parameter placeholders differently
            is_mssql = connection.db_type.lower() == 'mssql'
            
            # Check if cascade_delete is enabled
            cascade_option = ""
            if hasattr(table, 'cascade_delete') and table.cascade_delete:
                logger.info(f"Cascade delete enabled for {table_name}")
                # For MS SQL Server, we need to use a different approach for cascade deletes
                if is_mssql:
                    # We'll need to disable foreign key constraints temporarily
                    # or use a different approach like using a stored procedure
                    # For now, we'll log that cascade delete is enabled but not fully implemented for MS SQL
                    logger.warning(f"Cascade delete for MS SQL Server is handled through special SQL statements")
                    
                    # For MS SQL Server, we need to use a transaction with multiple statements
                    # First, get all foreign key constraints that reference this table
                    try:
                        # This is a simplified approach - in a real implementation, we would need to
                        # recursively find all related tables and delete from them in the correct order
                        logger.info(f"Using cascade delete approach for MS SQL Server")
                    except Exception as e:
                        logger.error(f"Error setting up cascade delete for MS SQL Server: {str(e)}")
            
            stmt = f"DELETE FROM {table_name} WHERE {' AND '.join(where_clauses)}"
            
            logger.info(f"Prepared delete statement: {stmt}")
            logger.info(f"With where values: {where_values}")
            
            if hasattr(engine, "connection") and engine.connection and hasattr(table, "cascade_delete") and table.cascade_delete and is_mssql:
                try:
                    try:
                        engine.execute_query("EXEC sp_MSforeachtable @command1='ALTER TABLE ? NOCHECK CONSTRAINT ALL'", [])
                    except Exception as e:
                        logger.warning(f"Error disabling constraints: {str(e)}")
                    
                    try:
                        engine.execute_query(stmt, where_values)
                        return
                    except Exception as e:
                        logger.error(f"Error executing cascade delete statement: {str(e)}")
                        raise
                    finally:
                        try:
                            engine.execute_query("EXEC sp_MSforeachtable @command1='ALTER TABLE ? CHECK CONSTRAINT ALL'", [])
                        except Exception as e:
                            logger.warning(f"Error re-enabling constraints: {str(e)}")
                except Exception:
                    logger.exception(f"Failed cascade delete path for {table_name}; falling back to standard execution")
            
            try:
                self._execute_statement(
                    engine,
                    stmt,
                    params=where_values,
                )
            except Exception as e:
                error_str = str(e).lower()
                if 'foreign key' in error_str or 'reference constraint' in error_str or 'constraint' in error_str:
                    logger.warning(f"Foreign key constraint error detected for {table_name}. Consider enabling cascade_delete for this table.")
                    return
                raise
            
            logger.info(f"Deleted record from {table.table_name}")
        
        except Exception as e:
            logger.error(f"Error performing delete on {table.table_name}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _get_random_record(self, engine, table: TableConfig) -> Optional[Dict[str, Any]]:
        """Get a random record from a table."""
        try:
            # Verify the engine is valid
            if engine is None:
                logger.error(f"Could not establish connection to database for {table.schema_name}.{table.table_name}")
                return None
                
            table_name = table.table_name
            if table.schema_name:
                table_name = f"{table.schema_name}.{table_name}"
            
            # Check if we're using JDBC engine (has execute_query method)
            is_jdbc = hasattr(engine, 'execute_query')
            logger.debug(f"Using JDBC engine: {is_jdbc} for table {table_name}")
            
            # Handle differently based on engine type
            if is_jdbc:
                try:
                    # For JDBC engines, use execute_query method
                    # First, count the total number of records
                    count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
                    logger.debug(f"Executing count query: {count_stmt}")
                    
                    # Make sure we have a connection
                    if not engine.connection:
                        logger.info(f"No active connection, attempting to connect for {table_name}")
                        engine.connect()
                        
                    if not engine.connection:
                        logger.error(f"Failed to establish connection for {table_name}")
                        return None
                    
                    # Execute count query using execute_query method
                    count_result = engine.execute_query(count_stmt)
                except Exception as e:
                    logger.error(f"Error executing count query for {table_name}: {str(e)}")
                    return None
                if count_result:
                    # For JDBC, count_result is already a list of dictionaries
                    if len(count_result) > 0:
                        # Extract count value from the first row
                        count_value = self._safe_int(count_result[0].get('cnt', 0), 0)
                        
                        if count_value <= 0:
                            logger.info(f"No records found in {table_name}")
                            return None
                        
                        # Generate a random offset for LIMIT/OFFSET queries
                        offset = random.randint(0, count_value - 1)
                        logger.debug(f"Generated random offset: {offset} for table {table_name} with {count_value} records")
                        
                        # Get a random record - PostgreSQL and other databases use LIMIT/OFFSET
                        if hasattr(engine, 'db_type') and engine.db_type == DatabaseType.POSTGRESQL:
                            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                        elif hasattr(engine, 'db_type') and engine.db_type == DatabaseType.MSSQL:
                            select_stmt = f"SELECT TOP 1 * FROM {table_name} ORDER BY NEWID()"
                        else:
                            # For other databases, try LIMIT/OFFSET first, fallback to TOP if needed
                            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                        
                        logger.debug(f"Executing select query: {select_stmt}")
                        result = engine.execute_query(select_stmt)
                        
                        if result and len(result) > 0:
                            # Result is already a list of dictionaries
                            return result[0]
                    else:
                        logger.info(f"No records found in {table_name}")
                        return None
                
                return None
            else:
                # For JDBC engines with execute method (no db_connector attribute)
                # Check if engine has execute method directly
                try:
                    # Check if we have a db_connector object (JDBC connection)
                    if hasattr(engine, 'db_connector') and engine.db_connector:
                        # Use db_connector directly for JDBC connections
                        db_connector = engine.db_connector
                        logger.debug(f"Using db_connector directly for {table_name}")
                        
                        # Make sure we have a connection
                        if not db_connector.connection:
                            logger.info(f"No active connection, attempting to connect for {table_name}")
                            db_connector.connect()
                            
                        if not db_connector.connection:
                            logger.error(f"Failed to establish connection for {table_name}")
                            return None
                        
                        # First, count the total number of records
                        count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
                        
                        try:
                            cursor = db_connector.connection.cursor()
                            cursor.execute(count_stmt)
                            row = cursor.fetchone()
                            count_value = self._safe_int(row[0] if row else 0, 0)
                            cursor.close()
                        except Exception as e:
                            logger.error(f"Error executing count query for {table_name}: {str(e)}")
                            return None
                        
                        if count_value <= 0:
                            logger.info(f"No records found in {table_name}")
                            return None
                        
                        # Generate a random offset for LIMIT/OFFSET queries
                        offset = random.randint(0, count_value - 1)
                        
                        # Get a random record - PostgreSQL and other databases use LIMIT/OFFSET
                        if db_connector.db_type == DatabaseType.POSTGRESQL:
                            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                        elif db_connector.db_type == DatabaseType.MSSQL:
                            # For MS SQL Server
                            select_stmt = f"SELECT TOP 1 * FROM {table_name} ORDER BY NEWID()"
                        else:
                            # For other databases
                            select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                        
                        try:
                            cursor = db_connector.connection.cursor()
                            cursor.execute(select_stmt)
                            row = cursor.fetchone()
                            
                            if row:
                                # Get column names
                                column_names = [column[0] for column in cursor.description]
                                # Convert row to dict
                                result_dict = {column_names[i]: value for i, value in enumerate(row)}
                                cursor.close()
                                return result_dict
                            cursor.close()
                        except Exception as e:
                            logger.error(f"Error executing select query for {table_name}: {str(e)}")
                            return None
                    
                    # Fallback to engine.execute if available
                    elif hasattr(engine, 'execute') and callable(engine.execute):
                        # Engine has direct execute method
                        logger.debug(f"Using engine with execute method for {table_name}")
                        
                        # First, count the total number of records
                        count_stmt = f"SELECT COUNT(*) as cnt FROM {table_name}"
                        
                        try:
                            count_result = engine.execute(count_stmt)
                        except Exception as e:
                            logger.error(f"Error executing count query for {table_name}: {str(e)}")
                            return None
                        
                        if count_result:
                            row = count_result.fetchone()
                            if row:
                                # Extract count value - might be at index 0 or might have a name 'cnt'
                                raw_count = row[0] if isinstance(row, (list, tuple)) else row.get('cnt', 0)
                                count_value = self._safe_int(raw_count, 0)
                                
                                if count_value <= 0:
                                    logger.info(f"No records found in {table_name}")
                                    return None
                                
                                # Generate a random offset for LIMIT/OFFSET queries
                                offset = random.randint(0, count_value - 1)
                                
                                # Query a random record based on database type
                                if hasattr(engine, 'db_connector') and engine.db_connector.db_type == DatabaseType.POSTGRESQL:
                                    # For PostgreSQL
                                    select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                                elif hasattr(engine, 'db_connector') and engine.db_connector.db_type == DatabaseType.MSSQL:
                                    # For MS SQL Server
                                    select_stmt = f"SELECT TOP 1 * FROM {table_name} ORDER BY NEWID()"
                                else:
                                    # For other databases
                                    select_stmt = f"SELECT * FROM {table_name} LIMIT 1 OFFSET {offset}"
                                
                                try:
                                    result = engine.execute(select_stmt)
                                    if result:
                                        row = result.fetchone()
                                        if row:
                                            # Convert row to dict
                                            try:
                                                return {k: v for k, v in zip(result.keys(), row)}
                                            except Exception:
                                                # Fallback if keys() method is not available
                                                return {f"col_{i}": v for i, v in enumerate(row)}
                                except Exception as e:
                                    logger.error(f"Error executing select query for {table_name}: {str(e)}")
                                    return None
                    else:
                        logger.error(f"Engine does not have execute method or db_connector for {table_name}")
                        return None
                except Exception as e:
                    logger.error(f"Error in JDBC execution for {table_name}: {str(e)}")
                    return None
                
                return None
        
        except Exception as e:
            logger.error(f"Error getting random record from {table.table_name}: {str(e)}")
            return None
    
    def _generate_random_data(self, column_type: Any) -> Any:
        """Generate random data based on column type using Faker for more realistic data."""
        # Initialize Faker if not already done
        if not hasattr(self, '_faker'):
            from faker import Faker
            self._faker = Faker()
            logger.info("Initialized Faker for generating realistic test data")
        
        # Convert Java String to Python string if needed
        try:
            # Check if it's a Java String or other Java object
            if hasattr(column_type, 'toString'):
                column_type = str(column_type)
            # Check if it's some other non-string type
            elif not isinstance(column_type, str):
                column_type = str(column_type)
                
            # Now we should have a Python string
            column_type = column_type.lower()
        except Exception as e:
            # If anything goes wrong, log it and default to a string type
            logger.error(f"Error converting column type {type(column_type)}: {str(e)}")
            column_type = 'varchar'
        
        # Generate data based on column type
        if 'int' in column_type:
            return random.randint(1, 1000)
        elif 'float' in column_type or 'double' in column_type or 'real' in column_type:
            return round(random.uniform(1, 1000), 2)
        elif 'bool' in column_type:
            return random.choice([True, False])
        elif 'date' in column_type:
            # Use Faker for realistic dates in the last 3 years
            return self._faker.date_between(start_date='-3y', end_date='today').strftime('%Y-%m-%d')
        elif 'time' in column_type and 'timestamp' not in column_type:
            # Use Faker for realistic time
            return self._faker.time()
        elif 'timestamp' in column_type or 'datetime' in column_type:
            # Use Faker for realistic datetime in the last 3 years
            return self._faker.date_time_between(start_date='-3y', end_date='now').isoformat()
        elif 'char' in column_type or 'text' in column_type or 'string' in column_type:
            # Determine max length for the string
            length = 100
            if 'varchar' in column_type or 'character varying' in column_type:
                # Extract length from varchar(N)
                import re
                match = re.search(r'\((\d+)\)', column_type)
                if match:
                    length = min(int(match.group(1)), 100)  # Cap at 100 chars
            
            # Use different Faker providers based on column name hints (if available)
            col_name = getattr(column_type, '_col_name', '').lower() if hasattr(column_type, '_col_name') else ''
            
            # If we don't have column name info, use a generic approach
            if not col_name:
                # Generate different types of realistic data based on length
                if length < 10:
                    return self._faker.lexify('?' * min(length, 5))
                elif length < 20:
                    return self._faker.word()[:length]
                elif length < 50:
                    return self._faker.sentence(nb_words=5)[:length]
                else:
                    return self._faker.paragraph(nb_sentences=3)[:length]
            
            # Use column name hints to generate appropriate data
            if any(name in col_name for name in ['name', 'customer', 'person', 'user']):
                return self._faker.name()[:length]
            elif any(name in col_name for name in ['email', 'mail']):
                return self._faker.email()[:length]
            elif any(name in col_name for name in ['phone', 'tel', 'mobile']):
                return self._faker.phone_number()[:length]
            elif any(name in col_name for name in ['address', 'addr', 'street']):
                return self._faker.address()[:length]
            elif any(name in col_name for name in ['city', 'town']):
                return self._faker.city()[:length]
            elif any(name in col_name for name in ['country']):
                return self._faker.country()[:length]
            elif any(name in col_name for name in ['company', 'business', 'org']):
                return self._faker.company()[:length]
            elif any(name in col_name for name in ['job', 'position', 'title', 'role']):
                return self._faker.job()[:length]
            elif any(name in col_name for name in ['desc', 'description', 'comment', 'note']):
                return self._faker.text(max_nb_chars=length)
            elif any(name in col_name for name in ['id', 'code', 'number', 'num']):
                return self._faker.bothify('#' * min(8, length))[:length]
            else:
                # Default to a sentence or paragraph based on length
                if length < 30:
                    return self._faker.sentence(nb_words=3)[:length]
                else:
                    return self._faker.paragraph(nb_sentences=2)[:length]
        else:
            # Default to a word for unknown types
            return self._faker.word()[:30]
