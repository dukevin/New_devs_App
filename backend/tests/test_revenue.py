import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from redis.exceptions import ConnectionError

from app.api.v1.dashboard import get_dashboard_summary
from app.services import cache
from app.services.reservations import reporting_bounds


class RevenueTests(unittest.IsolatedAsyncioTestCase):
    def test_local_month_and_year_boundaries(self):
        cases = [
            (2024, 3, "Europe/Paris", "2024-02-29T23:00:00+00:00", "2024-03-31T22:00:00+00:00"),
            (2024, 3, "America/New_York", "2024-03-01T05:00:00+00:00", "2024-04-01T04:00:00+00:00"),
            (2024, 12, "Europe/Paris", "2024-11-30T23:00:00+00:00", "2024-12-31T23:00:00+00:00"),
            (2024, None, "America/New_York", "2024-01-01T05:00:00+00:00", "2025-01-01T05:00:00+00:00"),
        ]
        for year, month, zone, start, end in cases:
            with self.subTest(month=month, zone=zone):
                self.assertEqual(
                    reporting_bounds(year, month, zone),
                    (datetime.fromisoformat(start), datetime.fromisoformat(end)),
                )

    async def test_redis_outage_returns_calculated_data_and_never_caches_database_failure(self):
        calculated = {"totals": [{"currency": "USD", "total_revenue": "1.01", "reservations_count": 1}]}
        redis = AsyncMock()
        redis.get.side_effect = ConnectionError("unavailable")
        redis.setex.side_effect = ConnectionError("unavailable")
        with patch.object(cache, "redis_client", redis), patch.object(
            cache, "calculate_total_revenue", AsyncMock(return_value=calculated)
        ) as calculate:
            result = await cache.get_revenue_summary("prop-001", "tenant-a", 2024, 3, "Europe/Paris", None)
            self.assertEqual(result, calculated)
            calculate.assert_awaited_once()
            redis.setex.reset_mock()
            calculate.side_effect = OSError("database unavailable")
            with self.assertRaises(OSError):
                await cache.get_revenue_summary("prop-001", "tenant-a", 2024, 3, "Europe/Paris", None)
            redis.setex.assert_not_awaited()

    async def test_database_outage_returns_explicit_service_unavailable(self):
        session = AsyncMock()
        session.execute.side_effect = OSError("database unavailable")
        with self.assertRaises(HTTPException) as raised:
            await get_dashboard_summary(
                "prop-001", 2024, 3, SimpleNamespace(tenant_id="tenant-a"), session
            )
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
