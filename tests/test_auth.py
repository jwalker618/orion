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

# Role coverage shouldn't depend on the live account roster, so the reviewer
# and entity-scoped-underwriter cases run against dedicated fixture users.
ROLE_FIXTURE_USERS = [
    {
        "user_id": "usr-t-rev", "email": "reviewer.fixture@test.example",
        "display_name": "Reviewer Fixture", "role": "reviewer",
    },
    {
        "user_id": "usr-t-uw", "email": "underwriter.fixture@test.example",
        "display_name": "Underwriter Fixture", "role": "entity_underwriter",
        "entity_scope": "MSRE",
    },
]


@pytest.fixture(autouse=True, scope="module")
def role_fixture_users(client):
    with SessionLocal() as db:
        existing = set(db.scalars(select(User.email)))
        for spec in ROLE_FIXTURE_USERS:
            if spec["email"] not in existing:
                db.add(User(**spec, password_hash=security.hash_password(PASSWORD)))
        db.commit()
    yield


def login(client, email, password=PASSWORD):
    return client.post(f"{AUTH}/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class TestLogin:
    def test_happy_path_and_me(self, client):
        body = login(client, "john.walker@msamlin.com").json()
        assert body["token_type"] == "bearer"
        assert body["mfa_required"] is False
        assert body["expires_in_seconds"] == 900

        me = client.get(f"{AUTH}/me", headers=bearer(body["access_token"])).json()
        assert me["display_name"] == "John Walker"
        assert me["role"] == "group_admin"
        assert "admin:reset" in me["permissions"]
        assert me["review"] is None

    def test_wrong_password_is_401(self, client):
        assert login(client, "john.walker@msamlin.com", "nope").status_code == 401

    def test_unknown_email_is_401(self, client):
        assert login(client, "ghost@msad.example").status_code == 401

    def test_reviewer_profile_flags_review(self, client):
        token = login(client, "reviewer.fixture@test.example").json()["access_token"]
        me = client.get(f"{AUTH}/me", headers=bearer(token)).json()
        assert me["review"] is True
        assert me["permissions"] == ["dashboard:read"]

    def test_underwriter_carries_entity_scope(self, client):
        token = login(client, "underwriter.fixture@test.example").json()["access_token"]
        me = client.get(f"{AUTH}/me", headers=bearer(token)).json()
        assert me["entity_scope"] == "MSRE"

    def test_generic_demo_login(self, client):
        me_token = login(client, "demo.user@msinternational.com").json()["access_token"]
        me = client.get(f"{AUTH}/me", headers=bearer(me_token)).json()
        assert me["display_name"] == "Demo User"
        assert me["organisation"] == "MS International"
        assert "dashboard:read" in me["permissions"]

    def test_retired_demo_identities_are_deactivated(self, client):
        assert login(client, "kenji.ito@msad.example").status_code == 401

    def test_garbage_bearer_is_401(self, client):
        assert client.get(f"{AUTH}/me", headers=bearer("not.a.token")).status_code == 401


class TestRefreshRotation:
    def test_rotation_and_reuse_burns_family(self, client):
        pair = login(client, "takeshi.doi@msigcs.co.uk").json()

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
        pair = login(client, "takeshi.doi@msigcs.co.uk").json()
        assert client.post(
            f"{AUTH}/logout", json={"refresh_token": pair["refresh_token"]}
        ).status_code == 204
        assert client.post(
            f"{AUTH}/refresh", json={"refresh_token": pair["refresh_token"]}
        ).status_code == 401


class TestPermissions:
    def test_reviewer_can_read_dashboards_but_not_ingest(self, client):
        token = login(client, "reviewer.fixture@test.example").json()["access_token"]
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
        token = login(client, "takeshi.doi@msigcs.co.uk").json()["access_token"]
        report = client.post(
            "/api/v1/entity-plans", json={"records": [make_plan()]}, headers=bearer(token)
        )
        assert report.status_code == 200

    def test_admin_can_reset(self, client):
        token = login(client, "john.walker@msamlin.com").json()["access_token"]
        assert client.post("/api/v1/admin/reset", headers=bearer(token)).status_code == 200

    def test_machine_api_key_still_has_full_access(self, client):
        assert client.post(
            "/api/v1/entity-plans", json={"records": [make_plan()]}, headers=HEADERS
        ).status_code == 200


class TestMFA:
    def test_setup_verify_challenge_and_backup_codes(self, client):
        token = login(client, "eric_schaap@msig-asia.com").json()["access_token"]

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
        challenged = login(client, "eric_schaap@msig-asia.com").json()
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

        again = login(client, "eric_schaap@msig-asia.com").json()
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
            f"{AUTH}/password/reset-request", json={"email": "demo.user@msinternational.com"}
        ).status_code == 204

        # The demo has no mailer; the token is only logged. Recover it by
        # hash from the DB and confirm with a fresh token value is impossible,
        # so mint one directly for the confirm step.
        from datetime import datetime, timedelta, timezone

        token = security.new_refresh_token()
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo.user@msinternational.com"))
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

        assert login(client, "demo.user@msinternational.com").status_code == 401
        assert login(client, "demo.user@msinternational.com", "new-password-1").status_code == 200

        # Token is single-use.
        assert client.post(
            f"{AUTH}/password/reset-confirm",
            json={"token": token, "new_password": "another-pass-2"},
        ).status_code == 400

        # Restore the demo password for other tests.
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo.user@msinternational.com"))
            user.password_hash = security.hash_password(PASSWORD)
            db.commit()


class TestSSOStubs:
    def test_sso_endpoints_are_501(self, client):
        assert client.get(f"{AUTH}/sso/msad").status_code == 501
        assert client.post(f"{AUTH}/sso/callback").status_code == 501


class TestLoginNotify:
    def test_login_posts_to_slack_webhook(self, client, monkeypatch):
        from app.config import get_settings
        from app.services import notify

        sent = []
        monkeypatch.setattr(
            notify.httpx, "post",
            lambda url, json=None, timeout=None: sent.append((url, json)),
        )
        monkeypatch.setattr(
            get_settings(), "login_notify_webhook_url",
            "https://hooks.slack.example/services/T0/B0/x",
        )
        assert login(client, "takeshi.doi@msigcs.co.uk").status_code == 200
        assert len(sent) == 1
        url, payload = sent[0]
        assert url.startswith("https://hooks.slack.example/")
        assert "ORION login" in payload["text"]
        assert "Takeshi Doi (takeshi.doi@msigcs.co.uk)" in payload["text"]
        assert "broker_relations · MSIG Corporate Solutions (UK)" in payload["text"]

    def test_unset_webhook_is_a_noop(self, client, monkeypatch):
        from app.config import get_settings
        from app.services import notify

        sent = []
        monkeypatch.setattr(
            notify.httpx, "post",
            lambda *a, **k: sent.append(a),
        )
        monkeypatch.setattr(get_settings(), "login_notify_webhook_url", "")
        assert login(client, "takeshi.doi@msigcs.co.uk").status_code == 200
        assert sent == []

    def test_slack_failure_never_breaks_login(self, client, monkeypatch):
        from app.config import get_settings
        from app.services import notify

        def boom(*a, **k):
            raise RuntimeError("slack is down")

        monkeypatch.setattr(notify.httpx, "post", boom)
        monkeypatch.setattr(
            get_settings(), "login_notify_webhook_url",
            "https://hooks.slack.example/services/T0/B0/x",
        )
        assert login(client, "takeshi.doi@msigcs.co.uk").status_code == 200
