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
from datetime import datetime
from typing import Any, Dict, List, Optional

from models import PillowFightJobStatus, PillowFightTableStatus


class PillowFightJobStore:
    """Persistence layer for pillow fight jobs and per-table stats."""

    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def create_job(
        self,
        job_id: str,
        connection_id: int,
        table_ids: List[int],
        operation_types: List[str],
        operation_delay: float,
        batch_size: int,
    ) -> None:
        now = self._now()
        self.db.execute(
            """
            INSERT INTO pillow_fight_jobs (
                job_id,
                connection_id,
                status,
                operation_types,
                operation_delay,
                batch_size,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                connection_id,
                PillowFightJobStatus.PENDING.value,
                json.dumps(operation_types),
                operation_delay,
                batch_size,
                now,
                now,
            ),
        )

        for table_id in table_ids:
            self.db.execute(
                """
                INSERT INTO pillow_fight_job_tables (
                    job_id,
                    table_config_id,
                    status
                ) VALUES (?, ?, ?)
                """,
                (
                    job_id,
                    table_id,
                    PillowFightTableStatus.PENDING.value,
                ),
            )

    def mark_job_started(self, job_id: str) -> None:
        now = self._now()
        self.db.execute(
            """
            UPDATE pillow_fight_jobs
            SET status = ?, 
                started_at = COALESCE(started_at, ?), 
                updated_at = ?, 
                last_heartbeat = ?
            WHERE job_id = ?
            """,
            (
                PillowFightJobStatus.RUNNING.value,
                now,
                now,
                now,
                job_id,
            ),
        )

    def update_job_status(self, job_id: str, status: PillowFightJobStatus, error_message: Optional[str] = None) -> None:
        now = self._now()
        self.db.execute(
            """
            UPDATE pillow_fight_jobs
            SET status = ?, updated_at = ?, completed_at = CASE WHEN ? IN ('completed', 'stopped', 'error') THEN ? ELSE completed_at END,
                error_message = ?
            WHERE job_id = ?
            """,
            (
                status.value,
                now,
                status.value,
                now,
                error_message,
                job_id,
            ),
        )

    def heartbeat(self, job_id: str) -> None:
        now = self._now()
        self.db.execute(
            """
            UPDATE pillow_fight_jobs
            SET last_heartbeat = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (now, now, job_id),
        )

    def update_table_status(
        self,
        job_id: str,
        table_id: int,
        status: PillowFightTableStatus,
        *,
        last_operation_at: Optional[str] = None,
        resume_cursor: Optional[str] = None,
        error_message: Optional[str] = None,
        warning_message: Optional[str] = None,
    ) -> None:
        now = self._now()
        self.db.execute(
            """
            UPDATE pillow_fight_job_tables
            SET status = ?, last_operation_at = COALESCE(?, last_operation_at),
                resume_cursor = COALESCE(?, resume_cursor),
                error_count = CASE WHEN ? THEN error_count + 1 ELSE error_count END,
                warning_count = CASE WHEN ? THEN COALESCE(warning_count, 0) + 1 ELSE warning_count END
            WHERE job_id = ? AND table_config_id = ?
            """,
            (
                status.value,
                last_operation_at,
                resume_cursor,
                True if error_message else False,
                True if warning_message else False,
                job_id,
                table_id,
            ),
        )

        if error_message:
            # update job level error message to keep history
            self.update_job_error(job_id, error_message)
        if warning_message:
            self.append_job_warning(job_id, warning_message)

    def append_job_warning(self, job_id: str, warning_message: str) -> None:
        """Append a warning to the job record (stored in error_message field for now)."""
        now = self._now()
        existing = self.db.query_one(
            "SELECT warning_message FROM pillow_fight_jobs WHERE job_id = ?",
            (job_id,),
        )
        combined = warning_message
        if existing and existing.get("warning_message"):
            combined = f"{existing['warning_message']}\n{warning_message}"

        self.db.execute(
            """
            UPDATE pillow_fight_jobs
            SET warning_message = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (combined, now, job_id),
        )

    def increment_operation(self, job_id: str, table_id: int, op_type: str, count: int = 1) -> None:
        op_column = {
            "insert": "insert_count",
            "update": "update_count",
            "delete": "delete_count",
        }.get(op_type.lower())

        if not op_column:
            return

        self.db.execute(
            f"""
            UPDATE pillow_fight_job_tables
            SET {op_column} = {op_column} + ?
            WHERE job_id = ? AND table_config_id = ?
            """,
            (count, job_id, table_id),
        )

    def mark_table_completed(self, job_id: str, table_id: int) -> None:
        self.update_table_status(
            job_id,
            table_id,
            PillowFightTableStatus.COMPLETED,
            last_operation_at=self._now(),
        )

    def update_job_error(self, job_id: str, error_message: str) -> None:
        now = self._now()
        existing = self.db.query_one(
            "SELECT error_message FROM pillow_fight_jobs WHERE job_id = ?",
            (job_id,),
        )
        combined = error_message
        if existing and existing.get("error_message"):
            combined = f"{existing['error_message']}\n{error_message}"

        self.db.execute(
            """
            UPDATE pillow_fight_jobs
            SET error_message = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (combined, now, job_id),
        )

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.db.query_one(
            "SELECT * FROM pillow_fight_jobs WHERE job_id = ?",
            (job_id,),
        )

    def get_job_tables(self, job_id: str) -> List[Dict[str, Any]]:
        return self.db.query(
            """
            SELECT * FROM pillow_fight_job_tables
            WHERE job_id = ?
            """,
            (job_id,),
        )

    def list_jobs(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        query = """
        SELECT * FROM pillow_fight_jobs
        ORDER BY created_at DESC
        """
        params: List[Any] = []
        if search:
            query = """
            SELECT * FROM pillow_fight_jobs
            WHERE job_id LIKE ? OR error_message LIKE ?
            ORDER BY created_at DESC
            """
            params = [f"%{search}%", f"%{search}%"]
        return self.db.query(query, params)

    def increment_error(self, job_id: str, table_id: int) -> None:
        self.db.execute(
            """
            UPDATE pillow_fight_job_tables
            SET error_count = error_count + 1
            WHERE job_id = ? AND table_config_id = ?
            """,
            (job_id, table_id),
        )

    def find_active_table_conflicts(self, table_ids: List[int]) -> List[int]:
        if not table_ids:
            return []

        placeholders = ",".join(["?"] * len(table_ids))
        rows = self.db.query(
            f"""
            SELECT jt.table_config_id
            FROM pillow_fight_job_tables jt
            JOIN pillow_fight_jobs j ON j.job_id = jt.job_id
            WHERE jt.table_config_id IN ({placeholders})
              AND jt.status IN ('pending', 'running')
              AND j.status IN ('pending', 'running')
            """,
            table_ids,
        )
        return [row["table_config_id"] for row in rows]

    def get_active_jobs_with_tables(self) -> List[Dict[str, Any]]:
        return self.db.query(
            """
            SELECT 
                j.job_id,
                j.connection_id,
                j.status,
                j.operation_types,
                j.operation_delay,
                j.batch_size,
                j.started_at,
                j.updated_at,
                jt.table_config_id,
                jt.status AS table_status,
                jt.insert_count,
                jt.update_count,
                jt.delete_count,
                jt.error_count,
                jt.last_operation_at
            FROM pillow_fight_jobs j
            JOIN pillow_fight_job_tables jt ON j.job_id = jt.job_id
            WHERE j.status IN ('pending', 'running')
            ORDER BY j.created_at ASC
            """
        )

    def reset_orphan_running_tables(self) -> None:
        """Ensure tables stuck in running status without an active job are marked pending."""
        self.db.execute(
            """
            UPDATE pillow_fight_job_tables
            SET status = 'pending'
            WHERE job_id IN (
                SELECT job_id FROM pillow_fight_jobs WHERE status IN ('pending', 'running')
            ) AND status = 'running'
            """
        )

    def get_jobs_with_tables(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        jobs = self.list_jobs(search)
        results: List[Dict[str, Any]] = []
        for job in jobs:
            tables = self.get_job_tables(job["job_id"])
            results.append(
                {
                    "job": job,
                    "tables": tables,
                }
            )
        return results

    def get_jobs_with_tables_by_status(
        self,
        statuses: List[str],
        table_statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not statuses:
            return []

        placeholders = ",".join(["?"] * len(statuses))
        jobs = self.db.query(
            f"""
            SELECT * FROM pillow_fight_jobs
            WHERE status IN ({placeholders})
            ORDER BY created_at ASC
            """,
            statuses,
        )

        results: List[Dict[str, Any]] = []
        for job in jobs:
            table_query = """
                SELECT * FROM pillow_fight_job_tables
                WHERE job_id = ?
            """
            params: List[Any] = [job["job_id"]]
            if table_statuses:
                table_placeholders = ",".join(["?"] * len(table_statuses))
                table_query += f" AND status IN ({table_placeholders})"
                params.extend(table_statuses)
            tables = self.db.query(table_query, params)
            results.append(
                {
                    "job": job,
                    "tables": tables,
                }
            )
        return results

    def get_active_job_for_table(self, connection_id: int, table_id: int) -> Optional[str]:
        row = self.db.query_one(
            """
            SELECT jt.job_id
            FROM pillow_fight_job_tables jt
            JOIN pillow_fight_jobs j ON j.job_id = jt.job_id
            WHERE j.connection_id = ?
              AND jt.table_config_id = ?
              AND j.status IN ('pending', 'running')
              AND jt.status IN ('pending', 'running')
            ORDER BY j.created_at DESC
            LIMIT 1
            """,
            (connection_id, table_id),
        )
        if row:
            return row["job_id"]
        return None
