"""Auth contract coverage: login, refresh rotation + reuse detection, /me,
role permissions on protected endpoints, TOTP MFA + backup codes, password
reset, and API-key/machine parity."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import PasswordResetToken, User
from app.services import security
from tests.conftest import HEADERS, make_plan

AUTH = "/api/v1/auth"
PASSWORD = "orion-demo"


def login(client, email, password=PASSWORD):
    return client.post(f"{AUTH}/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class TestLogin:
    def test_happy_path_and_me(self, client):
        body = login(client, "kenji.ito@msad.example").json()
        assert body["token_type"] == "bearer"
        assert body["mfa_required"] is False
        assert body["expires_in_seconds"] == 900

        me = client.get(f"{AUTH}/me", headers=bearer(body["access_token"])).json()
        assert me["display_name"] == "Kenji Ito"
        assert me["role"] == "group_admin"
        assert "admin:reset" in me["permissions"]
        assert me["review"] is None

    def test_wrong_password_is_401(self, client):
        assert login(client, "kenji.ito@msad.example", "nope").status_code == 401

    def test_unknown_email_is_401(self, client):
        assert login(client, "ghost@msad.example").status_code == 401

    def test_reviewer_profile_flags_review(self, client):
        token = login(client, "casey.reid@partner.example").json()["access_token"]
        me = client.get(f"{AUTH}/me", headers=bearer(token)).json()
        assert me["review"] is True
        assert me["permissions"] == ["dashboard:read"]

    def test_underwriter_carries_entity_scope(self, client):
        token = login(client, "rin.nakamura@msad.example").json()["access_token"]
        me = client.get(f"{AUTH}/me", headers=bearer(token)).json()
        assert me["entity_scope"] == "MSRE"

    def test_garbage_bearer_is_401(self, client):
        assert client.get(f"{AUTH}/me", headers=bearer("not.a.token")).status_code == 401


class TestRefreshRotation:
    def test_rotation_and_reuse_burns_family(self, client):
        pair = login(client, "amara.osei@msad.example").json()

        rotated = client.post(
            f"{AUTH}/refresh", json={"refresh_token": pair["refresh_token"]}
        ).json()
        assert rotated["refresh_token"] != pair["refresh_token"]

        # New access token works.
        me = client.get(f"{AUTH}/me", headers=bearer(rotated["access_token"]))
        assert me.status_code == 200

        # Replaying the rotated-out token is reuse -> 401 and the family burns.
        replay = client.post(f"{AUTH}/refresh", json={"refresh_token": pair["refresh_token"]})
        assert replay.status_code == 401
        burned = client.post(
            f"{AUTH}/refresh", json={"refresh_token": rotated["refresh_token"]}
        )
        assert burned.status_code == 401

    def test_logout_revokes(self, client):
        pair = login(client, "amara.osei@msad.example").json()
        assert client.post(
            f"{AUTH}/logout", json={"refresh_token": pair["refresh_token"]}
        ).status_code == 204
        assert client.post(
            f"{AUTH}/refresh", json={"refresh_token": pair["refresh_token"]}
        ).status_code == 401


class TestPermissions:
    def test_reviewer_can_read_dashboards_but_not_ingest(self, client):
        token = login(client, "casey.reid@partner.example").json()["access_token"]
        assert client.get(
            "/api/v1/dashboard/executive", headers=bearer(token)
        ).status_code == 200

        denied = client.post(
            "/api/v1/entity-plans", json={"records": [make_plan()]}, headers=bearer(token)
        )
        assert denied.status_code == 403
        assert "ingest:write" in denied.json()["detail"]

        assert client.post(
            "/api/v1/admin/reset", headers=bearer(token)
        ).status_code == 403

    def test_broker_relations_can_ingest(self, client):
        token = login(client, "amara.osei@msad.example").json()["access_token"]
        report = client.post(
            "/api/v1/entity-plans", json={"records": [make_plan()]}, headers=bearer(token)
        )
        assert report.status_code == 200

    def test_admin_can_reset(self, client):
        token = login(client, "kenji.ito@msad.example").json()["access_token"]
        assert client.post("/api/v1/admin/reset", headers=bearer(token)).status_code == 200

    def test_machine_api_key_still_has_full_access(self, client):
        assert client.post(
            "/api/v1/entity-plans", json={"records": [make_plan()]}, headers=HEADERS
        ).status_code == 200


class TestMFA:
    def test_setup_verify_challenge_and_backup_codes(self, client):
        token = login(client, "keiko.tanaka@msad.example").json()["access_token"]

        setup = client.post(f"{AUTH}/mfa/setup", headers=bearer(token)).json()
        assert setup["otpauth_uri"].startswith("otpauth://totp/ORION:")

        # Wrong code rejected; correct TOTP enables MFA.
        assert client.post(
            f"{AUTH}/mfa/verify", json={"code": "000000"}, headers=bearer(token)
        ).status_code == 401
        good = security.totp_code(setup["secret"])
        assert client.post(
            f"{AUTH}/mfa/verify", json={"code": good}, headers=bearer(token)
        ).status_code == 200

        codes = client.post(
            f"{AUTH}/mfa/backup-codes", headers=bearer(token)
        ).json()["codes"]
        assert len(codes) == 8

        # Next login now challenges: /me is fenced until verify passes.
        challenged = login(client, "keiko.tanaka@msad.example").json()
        assert challenged["mfa_required"] is True
        fenced = client.get(f"{AUTH}/me", headers=bearer(challenged["access_token"]))
        assert fenced.status_code == 401

        # A backup code passes the challenge — once.
        used = codes[0]
        assert client.post(
            f"{AUTH}/mfa/verify", json={"code": used},
            headers=bearer(challenged["access_token"]),
        ).status_code == 200
        assert client.get(
            f"{AUTH}/me", headers=bearer(challenged["access_token"])
        ).status_code == 200

        again = login(client, "keiko.tanaka@msad.example").json()
        assert client.post(
            f"{AUTH}/mfa/verify", json={"code": used},
            headers=bearer(again["access_token"]),
        ).status_code == 401
        # Clean up the challenge with a real TOTP so later tests aren't fenced.
        assert client.post(
            f"{AUTH}/mfa/verify", json={"code": security.totp_code(setup["secret"])},
            headers=bearer(again["access_token"]),
        ).status_code == 200


class TestPasswordReset:
    def test_round_trip(self, client):
        # Request never enumerates.
        assert client.post(
            f"{AUTH}/password/reset-request", json={"email": "ghost@msad.example"}
        ).status_code == 204
        assert client.post(
            f"{AUTH}/password/reset-request", json={"email": "rin.nakamura@msad.example"}
        ).status_code == 204

        # The demo has no mailer; the token is only logged. Recover it by
        # hash from the DB and confirm with a fresh token value is impossible,
        # so mint one directly for the confirm step.
        from datetime import datetime, timedelta, timezone

        token = security.new_refresh_token()
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "rin.nakamura@msad.example"))
            db.add(
                PasswordResetToken(
                    token_sha256=security.token_hash(token),
                    user_id=user.user_id,
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    + timedelta(minutes=10),
                )
            )
            db.commit()

        assert client.post(
            f"{AUTH}/password/reset-confirm",
            json={"token": token, "new_password": "new-password-1"},
        ).status_code == 204

        assert login(client, "rin.nakamura@msad.example").status_code == 401
        assert login(client, "rin.nakamura@msad.example", "new-password-1").status_code == 200

        # Token is single-use.
        assert client.post(
            f"{AUTH}/password/reset-confirm",
            json={"token": token, "new_password": "another-pass-2"},
        ).status_code == 400

        # Restore the demo password for other tests.
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "rin.nakamura@msad.example"))
            user.password_hash = security.hash_password(PASSWORD)
            db.commit()


class TestSSOStubs:
    def test_sso_endpoints_are_501(self, client):
        assert client.get(f"{AUTH}/sso/msad").status_code == 501
        assert client.post(f"{AUTH}/sso/callback").status_code == 501
