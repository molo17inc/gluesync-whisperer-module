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

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from database import get_db
from models import OperationType
from schemas import (
    PillowFightJobRequest,
    PillowFightJobStatus,
    PillowFightJobStatusResponse,
)
from services.pillow_fight_service import PillowFightService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pillow-fight", tags=["pillow-fight"])

# Single shared service instance to track running jobs/threads
pillow_fight_service = PillowFightService(get_db())


def _resolve_operation_types(job_request: PillowFightJobRequest) -> List[str]:
    """Normalize incoming operation selection to a list of strings."""
    if job_request.operation_types:
        return [
            op.value if isinstance(op, OperationType) else str(op)
            for op in job_request.operation_types
        ]
    if job_request.operation_type:
        return [
            job_request.operation_type.value
            if isinstance(job_request.operation_type, OperationType)
            else str(job_request.operation_type)
        ]
    return [OperationType.ALL.value]


@router.post(
    "/jobs",
    response_model=PillowFightJobStatus,
    status_code=status.HTTP_201_CREATED,
)
def create_pillow_fight_job(job_request: PillowFightJobRequest) -> PillowFightJobStatus:
    """Create a new pillow fight job for the selected tables."""
    try:
        job_id = pillow_fight_service.start_pillow_fight(
            connection_id=job_request.connection_id,
            table_ids=job_request.table_ids,
            operation_types=_resolve_operation_types(job_request),
            operation_delay=job_request.operation_delay,
            batch_size=job_request.batch_size,
        )
        job_status = pillow_fight_service.get_job_status(job_id)
        if not job_status:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Pillow fight job created but status is unavailable.",
            )
        return job_status
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Error creating pillow fight job")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating pillow fight job: {exc}",
        ) from exc


@router.get("/jobs", response_model=PillowFightJobStatusResponse)
def list_pillow_fight_jobs(search: Optional[str] = None) -> PillowFightJobStatusResponse:
    """List pillow fight jobs and their table statuses."""
    try:
        jobs = pillow_fight_service.list_jobs(search)
        return PillowFightJobStatusResponse(jobs=jobs)
    except Exception as exc:
        logger.exception("Error listing pillow fight jobs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing pillow fight jobs: {exc}",
        ) from exc


@router.get("/jobs/{job_id}", response_model=PillowFightJobStatus)
def get_pillow_fight_job(job_id: str) -> PillowFightJobStatus:
    """Retrieve a single pillow fight job."""
    job = pillow_fight_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pillow fight job {job_id} not found",
        )
    return job


@router.post("/jobs/{job_id}/stop", response_model=PillowFightJobStatus)
def stop_pillow_fight_job(job_id: str) -> PillowFightJobStatus:
    """Stop an entire pillow fight job."""
    job = pillow_fight_service.stop_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pillow fight job {job_id} not found",
        )
    return job


@router.post("/jobs/{job_id}/tables/{table_id}/stop", response_model=PillowFightJobStatus)
def stop_pillow_fight_table(job_id: str, table_id: int) -> PillowFightJobStatus:
    """Stop a single table inside a pillow fight job."""
    job = pillow_fight_service.stop_table_job(job_id, table_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pillow fight job {job_id} or table {table_id} not found",
        )
    return job
