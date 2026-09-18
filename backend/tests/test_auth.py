import asyncio
import time
import unittest
from datetime import datetime
from unittest.mock import patch

import jwt
import httpx
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1.login import LoginRequest, login
from app.config import settings
from app.core import auth
from app.database import supabase


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        auth.clear_auth_cache()

    def token(self, **claims):
        payload = {
            "id": "user-test",
            "email": "unknown@example.com",
            "app_metadata": {"tenant_id": "tenant-b"},
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
            **claims,
        }
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")

    async def authenticate(self, token):
        return await auth.authenticate_request(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    async def test_supplied_credentials_and_password_rejection(self):
        for name, password, tenant in (
            ("sunset", "client_a_2024", "tenant-a"),
            ("ocean", "client_b_2024", "tenant-b"),
        ):
            response = await login(LoginRequest(email=f"{name}@propertyflow.com", password=password))
            user = await self.authenticate(response.access_token)
            self.assertEqual(user.tenant_id, tenant)
            self.assertFalse(user.is_admin)

        for email, password in (
            ("candidate@propertyflow.com", "anything"),
            ("sunset@propertyflow.com", "wrong"),
            ("ocean@propertyflow.com", "client_b_2024 "),
        ):
            with self.subTest(email=email), self.assertRaises(HTTPException) as error:
                await login(LoginRequest(email=email, password=password))
            self.assertEqual(error.exception.status_code, 401)

    async def test_unverified_and_expired_tokens_fail_in_both_auth_paths(self):
        claims = {
            "id": "candidate",
            "email": "candidate@propertyflow.com",
            "app_metadata": {"role": "admin", "tenant_id": "tenant-a"},
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        invalid_tokens = [
            "mock-token-123",
            jwt.encode(claims, "", algorithm="none"),
            jwt.encode(claims, "not-the-signing-key", algorithm="HS256"),
            self.token(exp=int(time.time()) - 60),
            self.token(aud="wrong-audience"),
        ]
        for field in ("exp", "aud"):
            missing_claim = {key: value for key, value in claims.items() if key != field}
            invalid_tokens.append(jwt.encode(missing_claim, settings.secret_key, algorithm="HS256"))

        for token in invalid_tokens:
            with self.subTest(token_kind=invalid_tokens.index(token)):
                self.assertIsNone(supabase.auth.get_user(token).user)
                with self.assertRaises(HTTPException) as error:
                    await self.authenticate(token)
                self.assertEqual(error.exception.status_code, 401)
                self.assertIsNone(await auth.verify_token_ws(token))

    async def test_tenant_comes_only_from_verified_server_claims(self):
        for claims in (
            {"app_metadata": {}},
            {"email": "sunset@propertyflow.com", "app_metadata": {}},
            {"app_metadata": {}, "user_metadata": {"tenant_id": "tenant-a"}},
        ):
            with self.subTest(claims=claims), self.assertRaises(HTTPException) as error:
                await self.authenticate(self.token(**claims))
            self.assertEqual(error.exception.status_code, 403)

        root_user = await self.authenticate(self.token(app_metadata={}, tenant_id="tenant-a"))
        self.assertEqual(root_user.tenant_id, "tenant-a")
        metadata_user = await self.authenticate(self.token(tenant_id="tenant-a", user_metadata={"tenant_id": "tenant-a"}))
        self.assertEqual(metadata_user.tenant_id, "tenant-b")

    async def test_cached_authentication_does_not_outlive_token(self):
        expires_at = int(time.time()) + 30
        token = self.token(exp=expires_at)
        await self.authenticate(token)
        self.assertEqual(len(auth.auth_cache), 1)
        with patch.object(auth, "datetime") as clock:
            clock.now.return_value = datetime.fromtimestamp(expires_at + 1)
            with self.assertRaises(HTTPException) as error:
                await self.authenticate(token)
            self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(auth.auth_cache, {})

    async def test_expiry_through_full_application_middleware(self):
        from app.main import app

        expires_at = int(time.time()) + 2
        headers = {"Authorization": "Bearer " + self.token(exp=expires_at)}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            self.assertEqual((await client.get("/api/v1/auth/me", headers=headers)).status_code, 200)
            deadline = time.monotonic() + 15
            while time.time() <= expires_at:
                self.assertLess(time.monotonic(), deadline, "System clock did not reach token expiry")
                await asyncio.sleep(0.1)
            self.assertEqual((await client.get("/api/v1/auth/me", headers=headers)).status_code, 401)


if __name__ == "__main__":
    unittest.main()
