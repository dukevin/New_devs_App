import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import authenticate_request as get_current_user
from app.core.database_pool import get_db_session
from app.services.cache import get_revenue_summary

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user=Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    try:
        result = await db_session.execute(text("""
            SELECT id, name, timezone FROM properties
            WHERE tenant_id = :tenant_id ORDER BY id
        """), {"tenant_id": current_user.tenant_id})
        return [dict(row) for row in result.mappings()]
    except (SQLAlchemyError, OSError) as exc:
        logger.exception("Property lookup failed")
        raise HTTPException(status_code=503, detail="Property data is temporarily unavailable") from exc


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    year: int = Query(..., ge=1, le=9998),
    month: int | None = Query(None, ge=1, le=12),
    current_user=Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await db_session.execute(text("""
            SELECT timezone FROM properties
            WHERE id = :property_id AND tenant_id = :tenant_id
        """), {"property_id": property_id, "tenant_id": current_user.tenant_id})
        property_timezone = result.scalar_one_or_none()
        if property_timezone is None:
            raise HTTPException(status_code=404, detail="Property not found")
        return await get_revenue_summary(
            property_id, current_user.tenant_id, year, month, property_timezone, db_session
        )
    except OverflowError as exc:
        raise HTTPException(
            status_code=422, detail="Reporting period is outside the supported date range"
        ) from exc
    except (SQLAlchemyError, OSError) as exc:
        logger.exception("Revenue query failed")
        raise HTTPException(status_code=503, detail="Revenue data is temporarily unavailable") from exc
