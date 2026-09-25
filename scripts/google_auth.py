#!/usr/bin/env python3
"""
Sign in to Google Search Console once, for every copy of this skill.

    python3 scripts/google_auth.py setup     # install the Google libraries into the skill's own venv
    python3 scripts/google_auth.py login     # a browser opens: sign in, allow read-only access
    python3 scripts/google_auth.py status    # who is signed in, which properties you can read
    python3 scripts/google_auth.py logout    # revoke the token and delete it

Login uses the skill's own OAuth client, so nobody needs a Google Cloud project.
The token is saved once per user, outside the skill folder, and every installed copy
reads it: ~/.config/ultimate-seo-geo/gsc-token.json ($XDG_CONFIG_HOME and
$ULTIMATE_SEO_GEO_HOME move it). Access is read-only (webmasters.readonly).

gsc_query.py, gsc_insights.py and gsc_export.py load credentials through this module.
The order is:
  1. GOOGLE_APPLICATION_CREDENTIALS (a service account JSON)
  2. GSC_CREDENTIALS (a saved OAuth token)
  3. the token saved by `login`
  4. gsc-oauth-token.json in the skill folder (the pre-1.21 location)

The Google libraries are optional for the rest of the toolkit. `setup` installs them
into ~/.config/ultimate-seo-geo/venv. When a Search Console script is run without them,
it re-runs itself with that venv's Python, so you never need to activate the venv.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import venv
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# The skill's own Desktop-app OAuth client. For installed apps, Google documents that the
# client secret is not treated as confidential: it names the app on the consent screen and
# is useless without the signed-in user's consent. ULTIMATE_SEO_GEO_OAUTH_CLIENT_ID and
# ULTIMATE_SEO_GEO_OAUTH_CLIENT_SECRET override it; --client-secrets takes a client JSON.
BUNDLED_CLIENT_ID = ""
BUNDLED_CLIENT_SECRET = ""

# Mirrors requirements-gsc.txt (tests/test_google_auth.py pins the two together). The
# plugin bundle does not ship the requirements file, so `setup` installs from this list.
GOOGLE_PACKAGES = [
    "google-auth>=2.29.0,<3",
    "google-auth-oauthlib>=1.2.0,<2",
    "google-api-python-client>=2.100.0,<3",
    "requests>=2.31",
]

_REEXEC_GUARD = "ULTIMATE_SEO_GEO_VENV_REEXEC"


class AuthError(Exception):
    """A credential problem the user can fix; the message says how."""


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def config_dir() -> str:
    explicit = os.environ.get("ULTIMATE_SEO_GEO_HOME")
    if explicit:
        return os.path.expanduser(explicit)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "ultimate-seo-geo")


def token_path() -> str:
    return os.path.join(config_dir(), "gsc-token.json")


def legacy_token_path() -> str:
    return os.path.join(REPO_ROOT, "gsc-oauth-token.json")


def venv_python() -> str:
    folder = "Scripts" if os.name == "nt" else "bin"
    exe = "python.exe" if os.name == "nt" else "python"
    return os.path.join(config_dir(), "venv", folder, exe)


def _cmd(sub: str) -> str:
    return f"python3 {os.path.join(SCRIPT_DIR, 'google_auth.py')} {sub}"


# ---------------------------------------------------------------------------
# Libraries
# ---------------------------------------------------------------------------

def _libs_missing() -> str | None:
    for module in ("google.oauth2.credentials", "google_auth_oauthlib.flow", "googleapiclient.discovery"):
        try:
            __import__(module)
        except ImportError:
            return module
    return None


def ensure_google_libs() -> None:
    """Import the Google libraries, or re-run this process with the skill's venv."""
    missing = _libs_missing()
    if not missing:
        return
    py = venv_python()
    running = os.path.realpath(sys.executable)
    if os.path.isfile(py) and os.path.realpath(py) != running and not os.environ.get(_REEXEC_GUARD):
        os.environ[_REEXEC_GUARD] = "1"
        script = os.path.abspath(sys.argv[0])
        os.execv(py, [py, script, *sys.argv[1:]])
    raise AuthError(
        f"The Google libraries are not installed ({missing}). Run once:\n  {_cmd('setup')}"
    )


def setup() -> dict:
    """Create the skill's venv and install the Google libraries into it."""
    home = config_dir()
    target = os.path.join(home, "venv")
    if not os.path.isfile(venv_python()):
        os.makedirs(home, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(target)
    result = subprocess.run(
        [venv_python(), "-m", "pip", "install", "-q", "--disable-pip-version-check", *GOOGLE_PACKAGES],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AuthError(f"pip install failed in {target}:\n{result.stderr.strip()[-2000:]}")
    return {"ok": True, "venv": target, "packages": GOOGLE_PACKAGES, "next": _cmd("login")}


# ---------------------------------------------------------------------------
# Client and tokens
# ---------------------------------------------------------------------------

def client_config(client_secrets: str | None = None) -> dict:
    """The OAuth client to sign in with: a JSON file, the env override, or the bundled one."""
    path = client_secrets or os.environ.get("GSC_CLIENT_SECRETS")
    if not path:
        legacy = os.path.join(REPO_ROOT, "gsc-client-secrets.json")
        path = legacy if os.path.isfile(legacy) else None
    if path:
        if not os.path.isfile(path):
            raise AuthError(f"OAuth client file not found: {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    client_id = os.environ.get("ULTIMATE_SEO_GEO_OAUTH_CLIENT_ID") or BUNDLED_CLIENT_ID
    secret = os.environ.get("ULTIMATE_SEO_GEO_OAUTH_CLIENT_SECRET") or BUNDLED_CLIENT_SECRET
    if not client_id or not secret:
        raise AuthError(
            "This copy of the skill ships no OAuth client yet. Update the skill, or pass "
            "--client-secrets with a Desktop-app client JSON from Google Cloud."
        )
    return {"installed": {
        "client_id": client_id,
        "client_secret": secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}


def save_token(creds, path: str | None = None) -> str:
    """Write the token readable by this user only; atomic so a crash never leaves half a file."""
    path = path or token_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    os.replace(tmp, path)
    return path


def credential_sources(token_env: str = "GSC_CREDENTIALS") -> list[tuple[str, str]]:
    """(kind, path) candidates in priority order; only files that exist."""
    out = []
    sa = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa:
        out.append(("service_account", sa))
    env_token = os.environ.get(token_env)
    if env_token:
        out.append(("oauth_env", env_token))
    for kind, path in (("oauth_login", token_path()), ("oauth_legacy", legacy_token_path())):
        if os.path.isfile(path):
            out.append((kind, path))
    return out


def load_credentials(scopes: list[str] | None = None, token_env: str = "GSC_CREDENTIALS"):
    """Return (credentials, {"kind", "path"}) or raise AuthError with the next step."""
    scopes = scopes or GSC_SCOPES
    sources = credential_sources(token_env)
    if not sources:
        raise AuthError(f"Not signed in to Search Console. Run:\n  {_cmd('login')}")
    kind, path = sources[0]
    if not os.path.isfile(path):
        raise AuthError(f"{'GOOGLE_APPLICATION_CREDENTIALS' if kind == 'service_account' else token_env} "
                        f"points to a missing file: {path}")
    ensure_google_libs()
    if kind == "service_account":
        from google.oauth2 import service_account
        try:
            creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
        except (ValueError, OSError) as e:
            raise AuthError(f"Service account file {path} could not be read: {e}") from e
        return creds, {"kind": kind, "path": path}

    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    try:
        creds = Credentials.from_authorized_user_file(path, scopes)
    except (ValueError, OSError) as e:
        raise AuthError(f"Saved token {path} could not be read ({e}). Run:\n  {_cmd('login')}") from e
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise AuthError(f"The saved sign-in expired or was revoked ({e}). Run:\n  {_cmd('login')}") from e
        if kind == "oauth_login":
            save_token(creds, path)
    if not creds.valid:
        raise AuthError(f"The saved sign-in at {path} is not usable. Run:\n  {_cmd('login')}")
    return creds, {"kind": kind, "path": path}


def list_properties(creds) -> list[dict]:
    from google.auth.transport.requests import AuthorizedSession
    response = AuthorizedSession(creds).get(SITES_URL, timeout=30)
    response.raise_for_status()
    return [{"siteUrl": s.get("siteUrl"), "permissionLevel": s.get("permissionLevel")}
            for s in response.json().get("siteEntry") or []]


def is_sign_in_error(error) -> bool:
    """True when Google rejected the saved sign-in itself (revoked, expired, unknown client)."""
    text = f"{type(error).__name__} {error}"
    return any(k in text for k in ("RefreshError", "invalid_grant", "invalid_client", "unauthorized_client"))


def _properties(creds) -> dict:
    """Properties for the login/status output; a failed listing is reported, not raised."""
    try:
        found = list_properties(creds)
    except Exception as e:  # requests HTTPError, transport and auth errors all land here
        out = {"properties": [], "properties_error": f"{type(e).__name__}: {e}"}
        if is_sign_in_error(e):
            out.update(sign_in_valid=False, next=_cmd("login"))
        return out
    out = {"properties": found}
    if not found:
        out["note"] = ("This Google account has no Search Console properties. Sign in with the "
                       "account that owns or was added to the property, or ask its owner to add you.")
    return out


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def login(client_secrets: str | None = None, no_browser: bool = False, token: str | None = None) -> dict:
    config = client_config(client_secrets)
    ensure_google_libs()
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_config(config, GSC_SCOPES)
    # run_console() (copy-paste codes) was removed from google-auth-oauthlib 1.x with Google's
    # out-of-band flow; without a browser here, print the URL and keep the local redirect.
    creds = flow.run_local_server(
        port=0,
        open_browser=not no_browser,
        authorization_prompt_message="Sign in to Google Search Console at:\n{url}\n",
        success_message="Signed in to Search Console. You can close this tab.",
    )
    path = save_token(creds, token)
    return {"ok": True, "token": path, "scopes": GSC_SCOPES, **_properties(creds)}


def status() -> dict:
    sources = credential_sources()
    out = {"signed_in": False, "config_dir": config_dir(),
           "sources": [{"kind": k, "path": p} for k, p in sources]}
    if not sources:
        out["next"] = _cmd("login")
        return out
    creds, source = load_credentials()
    listing = _properties(creds)
    out.update(signed_in=listing.get("sign_in_valid", True), using=source, **listing)
    expiry = getattr(creds, "expiry", None)
    if expiry:
        out["access_token_expires"] = expiry.replace(tzinfo=timezone.utc).isoformat()
    return out


def logout() -> dict:
    path = token_path()
    if not os.path.isfile(path):
        return {"ok": True, "removed": None, "note": "No saved sign-in."}
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    revoked = None
    token = saved.get("refresh_token") or saved.get("token")
    if token:
        import urllib.error
        import urllib.parse
        import urllib.request
        body = urllib.parse.urlencode({"token": token}).encode()
        request = urllib.request.Request(REVOKE_URL, data=body, method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(request, timeout=15) as r:
                revoked = r.status == 200
        except urllib.error.HTTPError as e:
            revoked = f"Google answered {e.code}; the token may already be revoked"
        except urllib.error.URLError as e:
            revoked = f"not revoked: {e.reason}. Remove access at https://myaccount.google.com/permissions"
    os.remove(path)
    return {"ok": True, "removed": path, "revoked": revoked,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sign in to Google Search Console for this skill.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_login = sub.add_parser("login", help="Open a browser, sign in, save a read-only token")
    p_login.add_argument("--client-secrets", help="Use your own Desktop-app OAuth client JSON instead")
    p_login.add_argument("--no-browser", action="store_true", help="Print the sign-in URL instead of opening it")
    sub.add_parser("status", help="Show the credential in use and the properties it can read")
    sub.add_parser("logout", help="Revoke and delete the saved sign-in")
    sub.add_parser("setup", help="Install the Google libraries into the skill's own venv")
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            out = login(args.client_secrets, args.no_browser)
        elif args.command == "status":
            out = status()
        elif args.command == "logout":
            out = logout()
        else:
            out = setup()
    except AuthError as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
