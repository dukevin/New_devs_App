import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1 import dashboard
from app.config import settings
from app.core.auth import authenticate_request
from app.core.database_pool import db_pool
from app.models.auth import AuthenticatedUser
from app.services import cache


class DashboardIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        url = make_url(settings.database_url).set(drivername="postgresql+asyncpg")
        self.engine = create_async_engine(url)
        self.connection = await self.engine.connect()
        self.transaction = await self.connection.begin()
        self.original_factory = db_pool.session_factory
        db_pool.session_factory = async_sessionmaker(
            bind=self.connection, expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.addAsyncCleanup(self.close_database)
        self.values = {}

        async def store(key, ttl, value):
            self.values[key] = value

        self.redis = AsyncMock()
        self.redis.get.side_effect = self.values.get
        self.redis.setex.side_effect = store
        redis_patch = patch.object(cache, "redis_client", self.redis)
        redis_patch.start()
        self.addCleanup(redis_patch.stop)
        self.tenant = "tenant-a"
        app = FastAPI()
        app.include_router(dashboard.router, prefix="/api/v1")

        def identity():
            return AuthenticatedUser(
                id="test-user", email="test@example.com", tenant_id=self.tenant,
                permissions=[], cities=[], is_admin=False,
            )

        app.dependency_overrides[authenticate_request] = identity
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def close_database(self):
        db_pool.session_factory = self.original_factory
        await self.transaction.rollback()
        await self.connection.close()
        await self.engine.dispose()

    async def summary(self, property_id="prop-001", year=2024, month=3):
        params = {"property_id": property_id, "year": year}
        if month is not None:
            params["month"] = month
        return await self.client.get("/api/v1/dashboard/summary", params=params)

    async def test_seed_totals_and_owned_property_names(self):
        expected = {
            "tenant-a": {"prop-001": ("2250.00", 4), "prop-002": ("4975.50", 4),
                         "prop-003": ("6100.50", 2)},
            "tenant-b": {"prop-001": None, "prop-004": ("1776.50", 4),
                         "prop-005": ("3256.00", 3)},
        }
        for tenant, properties in expected.items():
            self.tenant = tenant
            response = await self.client.get("/api/v1/dashboard/properties")
            self.assertEqual(response.status_code, 200)
            owned = {item["id"]: item for item in response.json()}
            self.assertEqual(set(owned), set(properties))
            if tenant == "tenant-b":
                self.assertEqual(owned["prop-001"]["name"], "Mountain Lodge Beta")
            for property_id, total in properties.items():
                response = await self.summary(property_id)
                self.assertEqual(response.status_code, 200, response.text)
                expected_totals = [] if total is None else [{
                    "currency": "USD", "total_revenue": total[0],
                    "reservations_count": total[1],
                }]
                self.assertEqual(response.json()["totals"], expected_totals)

    async def test_cache_isolates_tenant_and_reporting_period_in_both_orders(self):
        for order in [("tenant-a", "tenant-b"), ("tenant-b", "tenant-a")]:
            self.values.clear()
            for tenant in order * 2:
                self.tenant = tenant
                march = await self.summary()
                self.assertEqual(march.status_code, 200)
                self.assertEqual(bool(march.json()["totals"]), tenant == "tenant-a")
                april = await self.summary(month=4)
                self.assertEqual(april.json()["totals"], [])
                annual = await self.summary(month=None)
                self.assertEqual(annual.json()["totals"], march.json()["totals"])
            self.assertEqual(len(self.values), 6)

    async def test_foreign_property_rejected_even_with_warm_cache(self):
        self.assertEqual((await self.summary("prop-002")).status_code, 200)
        self.tenant = "tenant-b"
        calls_before = self.redis.get.await_count
        self.assertEqual((await self.summary("prop-002")).status_code, 404)
        self.assertEqual(self.redis.get.await_count, calls_before)

    async def test_invalid_reporting_periods_rejected(self):
        for year, month in [(0, 3), (9999, 3), (2024, 0), (2024, 13)]:
            self.assertEqual((await self.summary(year=year, month=month)).status_code, 422)
        response = await self.client.get(
            "/api/v1/dashboard/summary", params={"property_id": "prop-001"}
        )
        self.assertEqual(response.status_code, 422)

    async def test_boundaries_currency_and_rounding_use_real_postgresql(self):
        property_id = "test-" + uuid4().hex
        await self.connection.execute(text("""
            INSERT INTO properties (id, tenant_id, name, timezone)
            VALUES (:id, 'tenant-a', 'Transaction-only test property', 'Europe/Paris')
        """), {"id": property_id})
        fixtures = [
            ("2024-02-29T22:59:59+00:00", "5.000", "USD"),
            ("2024-02-29T23:00:00+00:00", "1.005", "USD"),
            ("2024-03-31T21:59:59+00:00", "0.005", "USD"),
            ("2024-03-31T22:00:00+00:00", "9.000", "USD"),
            ("2024-03-15T12:00:00+00:00", "2.675", "EUR"),
        ]
        for when, amount, currency in fixtures:
            check_in = datetime.fromisoformat(when)
            await self.connection.execute(text("""
                INSERT INTO reservations
                    (id, property_id, tenant_id, check_in_date, check_out_date,
                     total_amount, currency)
                VALUES (:id, :property_id, 'tenant-a', :check_in, :check_out,
                        :amount, :currency)
            """), {"id": uuid4().hex, "property_id": property_id,
                   "check_in": check_in, "check_out": check_in + timedelta(days=2),
                   "amount": Decimal(amount), "currency": currency})
        response = await self.summary(property_id)
        self.assertEqual(response.status_code, 200, response.text)
        totals = {row["currency"]: row for row in response.json()["totals"]}
        self.assertEqual(totals, {
            "USD": {"currency": "USD", "total_revenue": "1.01", "reservations_count": 2},
            "EUR": {"currency": "EUR", "total_revenue": "2.68", "reservations_count": 1},
        })
        annual = (await self.summary(property_id, month=None)).json()
        usd = next(row for row in annual["totals"] if row["currency"] == "USD")
        self.assertEqual(usd["total_revenue"], "15.01")
        self.assertEqual(usd["reservations_count"], 4)


if __name__ == "__main__":
    unittest.main()
