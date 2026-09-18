from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def reporting_bounds(year: int, month: int | None, property_timezone: str):
    zone = ZoneInfo(property_timezone)
    start = datetime(year, month or 1, 1, tzinfo=zone)
    if month is None or month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=zone)
    else:
        end = datetime(year, month + 1, 1, tzinfo=zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    year: int,
    month: int | None,
    property_timezone: str,
    db_session: AsyncSession,
) -> dict:
    start, end = reporting_bounds(year, month, property_timezone)
    result = await db_session.execute(text("""
        SELECT currency, SUM(total_amount) AS total_revenue,
               COUNT(*) AS reservations_count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
          AND check_in_date >= :start AND check_in_date < :end
        GROUP BY currency
        ORDER BY currency
    """), {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "start": start,
        "end": end,
    })
    return {
        "property_id": property_id,
        "year": year,
        "month": month,
        "timezone": property_timezone,
        "totals": [
            {
                "currency": row.currency,
                # Round the exact currency aggregate once, never individual bookings.
                "total_revenue": str(row.total_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "reservations_count": row.reservations_count,
            }
            for row in result
        ],
    }
