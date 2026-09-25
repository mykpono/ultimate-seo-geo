"""google_auth.py: one Search Console sign-in per user, read by every copy of the skill.

Nothing here talks to Google. Tests that need the Google libraries skip when they are
absent (CI installs only the core requirements); the rest drive the stdlib paths.
"""

import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import google_auth as ga  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolated config dir and no credential env vars from the developer's shell."""
    for var in ("GOOGLE_APPLICATION_CREDENTIALS", "GSC_CREDENTIALS", "GSC_CLIENT_SECRETS",
                "ULTIMATE_SEO_GEO_OAUTH_CLIENT_ID", "ULTIMATE_SEO_GEO_OAUTH_CLIENT_SECRET",
                "XDG_CONFIG_HOME", ga._REEXEC_GUARD):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ULTIMATE_SEO_GEO_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(ga, "legacy_token_path", lambda: str(tmp_path / "skill" / "gsc-oauth-token.json"))
    monkeypatch.setattr(ga, "REPO_ROOT", str(tmp_path / "skill"))
    return tmp_path


def token_json(expiry_delta_minutes=60):
    expiry = (datetime.utcnow() + timedelta(minutes=expiry_delta_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"token": "access", "refresh_token": "refresh", "client_id": "cid", "client_secret": "cs",
            "token_uri": "https://oauth2.googleapis.com/token", "scopes": ga.GSC_SCOPES, "expiry": expiry}


# --- locations ---------------------------------------------------------------

def test_config_dir_precedence(monkeypatch, tmp_path):
    monkeypatch.delenv("ULTIMATE_SEO_GEO_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert ga.config_dir() == str(tmp_path / "xdg" / "ultimate-seo-geo")
    monkeypatch.setenv("ULTIMATE_SEO_GEO_HOME", str(tmp_path / "own"))
    assert ga.config_dir() == str(tmp_path / "own")


def test_token_lives_outside_the_skill_folder(home):
    assert ga.token_path().startswith(str(home / "cfg"))
    assert not ga.token_path().startswith(os.path.abspath(ROOT))


# --- credential order --------------------------------------------------------

def test_no_credentials_says_how_to_log_in(home):
    with pytest.raises(ga.AuthError, match="google_auth.py login"):
        ga.load_credentials()


def test_source_order(home, monkeypatch):
    login = home / "cfg" / "gsc-token.json"
    legacy = home / "skill" / "gsc-oauth-token.json"
    for path in (login, legacy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    assert [k for k, _ in ga.credential_sources()] == ["oauth_login", "oauth_legacy"]
    monkeypatch.setenv("GSC_CREDENTIALS", str(home / "env.json"))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(home / "sa.json"))
    assert [k for k, _ in ga.credential_sources()] == ["service_account", "oauth_env", "oauth_login", "oauth_legacy"]


def test_env_var_pointing_at_a_missing_file_is_named(home, monkeypatch):
    monkeypatch.setenv("GSC_CREDENTIALS", str(home / "nope.json"))
    with pytest.raises(ga.AuthError, match="GSC_CREDENTIALS points to a missing file"):
        ga.load_credentials()


# --- the OAuth client ----------------------------------------------------------

def test_no_bundled_client_is_a_clear_error(home, monkeypatch):
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_ID", "")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_SECRET", "")
    with pytest.raises(ga.AuthError, match="ships no OAuth client"):
        ga.client_config()


def test_bundled_client_becomes_an_installed_app_config(home, monkeypatch):
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_ID", "123.apps.googleusercontent.com")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_SECRET", "shh")
    cfg = ga.client_config()["installed"]
    assert cfg["client_id"] == "123.apps.googleusercontent.com"
    assert cfg["redirect_uris"] == ["http://localhost"]


def test_env_and_file_override_the_bundled_client(home, monkeypatch):
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_ID", "bundled")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_SECRET", "bundled")
    monkeypatch.setenv("ULTIMATE_SEO_GEO_OAUTH_CLIENT_ID", "env-id")
    monkeypatch.setenv("ULTIMATE_SEO_GEO_OAUTH_CLIENT_SECRET", "env-secret")
    assert ga.client_config()["installed"]["client_id"] == "env-id"
    own = home / "client.json"
    own.write_text(json.dumps({"installed": {"client_id": "file-id"}}))
    assert ga.client_config(str(own))["installed"]["client_id"] == "file-id"
    with pytest.raises(ga.AuthError, match="not found"):
        ga.client_config(str(home / "missing.json"))


# --- token file ----------------------------------------------------------------

class FakeCreds:
    def to_json(self):
        return json.dumps({"token": "t"})


def test_save_token_is_private(home):
    path = ga.save_token(FakeCreds())
    assert json.loads(open(path).read()) == {"token": "t"}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert not os.path.exists(path + ".tmp")


# --- libraries -----------------------------------------------------------------

def test_missing_libs_without_a_venv_says_run_setup(home, monkeypatch):
    monkeypatch.setattr(ga, "_libs_missing", lambda: "googleapiclient.discovery")
    with pytest.raises(ga.AuthError, match="google_auth.py setup"):
        ga.ensure_google_libs()


def test_missing_libs_with_the_venv_reexecs_once(home, monkeypatch):
    monkeypatch.setattr(ga, "_libs_missing", lambda: "googleapiclient.discovery")
    py = ga.venv_python()
    os.makedirs(os.path.dirname(py))
    open(py, "w").close()
    calls = []
    monkeypatch.setattr(ga.os, "execv", lambda exe, argv: calls.append((exe, argv)))
    monkeypatch.setattr(sys, "argv", ["/skill/scripts/gsc_query.py", "sc-domain:x.com", "--json"])
    with pytest.raises(ga.AuthError):  # execv is faked, so control falls through to the error
        ga.ensure_google_libs()
    assert calls == [(py, [py, "/skill/scripts/gsc_query.py", "sc-domain:x.com", "--json"])]
    # the guard stops a second re-exec (a venv whose install failed would loop forever)
    with pytest.raises(ga.AuthError):
        ga.ensure_google_libs()
    assert len(calls) == 1


def test_setup_packages_match_requirements_gsc():
    with open(os.path.join(ROOT, "requirements-gsc.txt")) as f:
        pinned = {line.strip() for line in f if line.strip() and not line.startswith("#")}
    assert pinned <= set(ga.GOOGLE_PACKAGES)
    assert set(ga.GOOGLE_PACKAGES) - pinned == {p for p in ga.GOOGLE_PACKAGES if p.startswith("requests")}


# --- commands without Google libraries ----------------------------------------

def test_status_when_signed_out(home):
    out = ga.status()
    assert out["signed_in"] is False and "login" in out["next"]


def test_logout_revokes_and_deletes(home, monkeypatch):
    path = ga.save_token(FakeCreds())
    with open(path, "w") as f:
        json.dump({"token": "a", "refresh_token": "r"}, f)
    seen = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        seen["body"] = request.data
        return Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = ga.logout()
    assert out["revoked"] is True and seen["body"] == b"token=r"
    assert not os.path.exists(path)
    assert ga.logout()["removed"] is None


def _clean_env(tmp_path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GOOGLE_APPLICATION_CREDENTIALS", "GSC_CREDENTIALS")}
    env["ULTIMATE_SEO_GEO_HOME"] = str(tmp_path / "cfg")
    return env


def test_gsc_query_without_sign_in_points_to_login(tmp_path):
    if os.path.isfile(os.path.join(ROOT, "gsc-oauth-token.json")):
        pytest.skip("a legacy token sits in this checkout")
    run = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gsc_query.py"), "sc-domain:x.com", "--json"],
                         capture_output=True, text=True, env=_clean_env(tmp_path))
    assert run.returncode == 1
    assert "google_auth.py login" in json.loads(run.stdout)["error"]


def test_gsc_export_without_sign_in_points_to_login(tmp_path):
    if os.path.isfile(os.path.join(ROOT, "gsc-oauth-token.json")):
        pytest.skip("a legacy token sits in this checkout")
    run = subprocess.run([sys.executable, os.path.join(SCRIPTS, "gsc_export.py"), "--list-properties"],
                         capture_output=True, text=True, env=_clean_env(tmp_path))
    assert run.returncode == 1
    assert "google_auth.py login" in run.stderr


# --- with the Google libraries ----------------------------------------------------

def test_saved_login_token_loads(home):
    pytest.importorskip("google.oauth2.credentials")
    path = home / "cfg" / "gsc-token.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(token_json()))
    creds, source = ga.load_credentials()
    assert source == {"kind": "oauth_login", "path": str(path)}
    assert creds.valid and creds.token == "access"


def test_expired_token_refreshes_and_is_saved_back(home, monkeypatch):
    creds_mod = pytest.importorskip("google.oauth2.credentials")
    path = home / "cfg" / "gsc-token.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(token_json(-60)))

    def fake_refresh(self, request):
        self.token = "fresh"
        self.expiry = datetime.utcnow() + timedelta(hours=1)

    monkeypatch.setattr(creds_mod.Credentials, "refresh", fake_refresh)
    creds, _ = ga.load_credentials()
    assert creds.token == "fresh"
    assert json.loads(path.read_text())["token"] == "fresh"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_revoked_token_asks_for_a_new_login(home, monkeypatch):
    creds_mod = pytest.importorskip("google.oauth2.credentials")
    from google.auth.exceptions import RefreshError
    path = home / "cfg" / "gsc-token.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(token_json(-60)))

    def fail(self, request):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(creds_mod.Credentials, "refresh", fail)
    with pytest.raises(ga.AuthError, match="expired or was revoked"):
        ga.load_credentials()


def test_login_saves_the_token_and_lists_properties(home, monkeypatch):
    flow_mod = pytest.importorskip("google_auth_oauthlib.flow")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_ID", "cid")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_SECRET", "cs")
    seen = {}

    class FakeFlow:
        def run_local_server(self, **kwargs):
            seen.update(kwargs)
            return FakeCreds()

    def from_client_config(config, scopes):
        seen["client_id"] = config["installed"]["client_id"]
        seen["scopes"] = scopes
        return FakeFlow()

    monkeypatch.setattr(flow_mod.InstalledAppFlow, "from_client_config", staticmethod(from_client_config))
    monkeypatch.setattr(ga, "list_properties", lambda creds: [{"siteUrl": "sc-domain:x.com", "permissionLevel": "siteOwner"}])
    out = ga.login(no_browser=True)
    assert out["ok"] and out["token"] == ga.token_path()
    assert out["properties"][0]["siteUrl"] == "sc-domain:x.com"
    assert seen["scopes"] == ["https://www.googleapis.com/auth/webmasters.readonly"]
    assert seen["open_browser"] is False and seen["port"] == 0
    assert seen["client_id"] == "cid"


def test_login_reports_a_failed_property_listing(home, monkeypatch):
    flow_mod = pytest.importorskip("google_auth_oauthlib.flow")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_ID", "cid")
    monkeypatch.setattr(ga, "BUNDLED_CLIENT_SECRET", "cs")

    class FakeFlow:
        def run_local_server(self, **kwargs):
            return FakeCreds()

    monkeypatch.setattr(flow_mod.InstalledAppFlow, "from_client_config", staticmethod(lambda c, s: FakeFlow()))

    def boom(creds):
        raise RuntimeError("403 Search Console API has not been used in project")

    monkeypatch.setattr(ga, "list_properties", boom)
    out = ga.login()
    assert out["ok"] and out["properties"] == []
    assert "403" in out["properties_error"]


def test_rejected_sign_in_is_recognised():
    assert ga.is_sign_in_error("('invalid_client: The OAuth client was not found.', {...})")
    assert ga.is_sign_in_error(RuntimeError("invalid_grant: Token has been expired or revoked."))
    assert not ga.is_sign_in_error(RuntimeError("403 User does not have sufficient permission for site"))


def test_status_with_a_rejected_token_is_not_signed_in(home, monkeypatch):
    path = ga.save_token(FakeCreds())
    monkeypatch.setattr(ga, "load_credentials", lambda: (object(), {"kind": "oauth_login", "path": path}))

    def rejected(creds):
        raise RuntimeError("('invalid_grant: Token has been expired or revoked.', {})")

    monkeypatch.setattr(ga, "list_properties", rejected)
    out = ga.status()
    assert out["signed_in"] is False and "login" in out["next"]
