"""
YouTube Music OAuth Authentication Setup & Safe Diagnostic Tool for Animus.

Supports ytmusicapi v1.12+ OAuth 2.0 device flow using Google Cloud OAuth Client credentials.
Provides granular diagnostics for Google OAuth failure modes (invalid_client, unauthorized_client,
access_denied, API not enabled, network issues).
Stores credentials strictly under: D:\\AnimusSmartRoom\\server\\music_daemon\\secrets\\
NEVER requests, logs, or prints secrets, tokens, or Google passwords.
"""

import json
import logging
import os
import re
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import requests
import ytmusicapi
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.credentials import OAuthCredentials
from ytmusicapi.auth.oauth.exceptions import BadOAuthClient, UnauthorizedOAuthClient
from ytmusicapi.constants import OAUTH_CODE_URL, OAUTH_SCOPE, OAUTH_TOKEN_URL, OAUTH_USER_AGENT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("auth_setup")

SECRETS_DIR = Path(__file__).resolve().parent / "secrets"
OAUTH_CLIENT_FILE = SECRETS_DIR / "oauth_client.json"
OAUTH_TOKEN_FILE = SECRETS_DIR / "oauth.json"
HEADERS_AUTH_FILE = SECRETS_DIR / "headers_auth.json"
COOKIES_FILE = SECRETS_DIR / "cookies.txt"


@dataclass
class DiagnosticResult:
    is_valid_structure: bool
    status_code: Optional[int]
    error_code: Optional[str]
    error_description: Optional[str]
    remediation_hint: str


def ensure_secrets_dir():
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)


def load_client_credentials(secrets_dir: Optional[Path] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Loads client_id and client_secret from:
    1. Environment variables: YTM_CLIENT_ID and YTM_CLIENT_SECRET
    2. Local untracked JSON: secrets/oauth_client.json
    """
    client_id = os.environ.get("YTM_CLIENT_ID")
    client_secret = os.environ.get("YTM_CLIENT_SECRET")
    if client_id and client_secret:
        return client_id.strip(), client_secret.strip()

    base_dir = secrets_dir or SECRETS_DIR
    client_file = base_dir / "oauth_client.json"
    if client_file.is_file():
        try:
            with open(client_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "installed" in data:
                    data = data["installed"]
                elif "web" in data:
                    data = data["web"]
                cid = data.get("client_id")
                csec = data.get("client_secret")
                if cid and csec:
                    return str(cid).strip(), str(csec).strip()
        except Exception as e:
            logger.warning(f"Could not parse oauth_client.json: {e}")

    return None, None


def validate_client_id_structure(client_id: Optional[str]) -> bool:
    """
    Checks if client_id matches the standard Google Cloud OAuth client format:
    e.g. 123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com
    """
    if not client_id:
        return False
    pattern = re.compile(r"^\d+-[a-zA-Z0-9_\-]+\.apps\.googleusercontent\.com$")
    return bool(pattern.match(client_id.strip()))


def diagnose_google_oauth_endpoint(client_id: str, client_secret: str) -> DiagnosticResult:
    """
    Safely probes the Google YouTube OAuth device code endpoint with the provided credentials.
    Captures exact HTTP status code and OAuth error payload without printing raw credentials.
    """
    session = requests.Session()
    payload = {
        "client_id": client_id,
        "scope": OAUTH_SCOPE
    }
    headers = {"User-Agent": OAUTH_USER_AGENT}

    try:
        resp = session.post(OAUTH_CODE_URL, data=payload, headers=headers, timeout=10)
        status_code = resp.status_code

        if status_code == 200:
            return DiagnosticResult(
                is_valid_structure=True,
                status_code=200,
                error_code=None,
                error_description="Google OAuth device code endpoint accepted client_id successfully.",
                remediation_hint="Client credentials are fully valid and ready for authorization."
            )

        # Parse JSON error from Google
        try:
            err_json = resp.json()
            error_code = err_json.get("error", "unknown_error")
            error_desc = err_json.get("error_description", "")
        except Exception:
            error_code = f"HTTP_{status_code}"
            error_desc = resp.text[:200]

        remediation = "Unknown OAuth issue. Check Google Cloud Console."
        if error_code == "invalid_client":
            remediation = (
                "Google rejected the Client ID / Client Secret.\n"
                "  1. Ensure 'YouTube Data API v3' is ENABLED in your Google Cloud Project.\n"
                "  2. Verify OAuth Client Application Type is 'TVs and Limited Input devices' (or 'Desktop app').\n"
                "  3. Verify client_id matches client_secret in Google Cloud Console."
            )
        elif error_code == "unauthorized_client":
            remediation = (
                "Client is unauthorized for device code flow.\n"
                "  -> In Google Cloud Console, ensure Client ID application type is 'TVs and Limited Input devices' or 'Desktop app'."
            )
        elif error_code == "access_denied":
            remediation = (
                "Access was denied.\n"
                "  -> Ensure your Google account is added as a 'Test User' under 'OAuth consent screen'."
            )
        elif "api" in str(error_desc).lower() or "not enabled" in str(error_desc).lower():
            remediation = (
                "YouTube Data API v3 is not enabled in this Google Cloud project.\n"
                "  -> Go to: https://console.cloud.google.com/apis/library/youtube.googleapis.com and click 'ENABLE'."
            )

        return DiagnosticResult(
            is_valid_structure=validate_client_id_structure(client_id),
            status_code=status_code,
            error_code=error_code,
            error_description=error_desc,
            remediation_hint=remediation
        )

    except requests.RequestException as e:
        return DiagnosticResult(
            is_valid_structure=validate_client_id_structure(client_id),
            status_code=None,
            error_code="network_error",
            error_description=f"Connection to Google OAuth failed: {str(e)}",
            remediation_hint="Check your internet connection or proxy settings."
        )


def run_diagnostics(secrets_dir: Optional[Path] = None):
    """
    Executes a comprehensive, safe diagnostic scan of YouTube Music OAuth configuration.
    """
    base_dir = secrets_dir or SECRETS_DIR
    oauth_client_path = base_dir / "oauth_client.json"
    oauth_token_path = base_dir / "oauth.json"

    client_id, client_secret = load_client_credentials(secrets_dir=base_dir)

    print("\n" + "=" * 70)
    print("      ANIMUS YOUTUBE MUSIC OAUTH SAFE DIAGNOSTIC SUITE")
    print("=" * 70)
    print(f" ytmusicapi version:      {ytmusicapi.__version__}")
    print(f" Secrets directory:       {base_dir}")
    print(f" oauth_client.json:       {'EXISTS' if oauth_client_path.is_file() else 'MISSING'}")
    print(f" Client ID configured:    {'YES' if client_id else 'NO'}")
    print(f" Client ID valid format:  {'YES' if validate_client_id_structure(client_id) else 'NO/INVALID'}")
    print(f" Client Secret configured:{'YES' if client_secret else 'NO'}")
    print(f" oauth.json (token):      {'EXISTS' if oauth_token_path.is_file() else 'NOT FOUND'}")
    print("-" * 70)

    if not client_id or not client_secret:
        print("\n [!] DIAGNOSIS: Missing Client Credentials")
        print(" Remediation:")
        print("  1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth Client ID ('TVs and Limited Input devices')")
        print(f"  3. Save credentials in '{oauth_client_path}' as:")
        print('     {"client_id": "...", "client_secret": "..."}\n')
        return

    print(" Probing Google OAuth endpoint...")
    diag = diagnose_google_oauth_endpoint(client_id, client_secret)
    print(f" HTTP Status:             {diag.status_code if diag.status_code else 'N/A'}")
    print(f" OAuth Error Code:        {diag.error_code if diag.error_code else 'NONE (SUCCESS)'}")
    if diag.error_description:
        print(f" Error Detail:            {diag.error_description}")
    print("-" * 70)
    print(f" REMEDIATION / STATUS:\n{diag.remediation_hint}\n" + "=" * 70 + "\n")


def setup_ytm_oauth(client_id_arg: Optional[str] = None, client_secret_arg: Optional[str] = None):
    """
    Executes the interactive OAuth 2.0 device authorization flow with rich diagnostics on failure.
    """
    ensure_secrets_dir()
    print("\n" + "=" * 65)
    print("      ANIMUS YOUTUBE MUSIC OAUTH SETUP (PASSWORDLESS)")
    print("=" * 65)
    print("This utility authorizes Animus to connect to your YouTube Music account.")
    print("Google account passwords are NEVER requested, handled, or stored.\n")

    client_id = client_id_arg
    client_secret = client_secret_arg

    if not client_id or not client_secret:
        client_id, client_secret = load_client_credentials()

    if not client_id or not client_secret:
        print(" [!] Google Cloud OAuth Client credentials not found.")
        print("\n Run 'python auth_setup.py diagnose' or follow instructions:")
        print(" 1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials")
        print(" 2. Enable 'YouTube Data API v3': https://console.cloud.google.com/apis/library/youtube.googleapis.com")
        print(" 3. Create OAuth Client ID ('TVs and Limited Input devices')")
        print(f" 4. Save to: {OAUTH_CLIENT_FILE}\n")

        try:
            input_cid = input(" Client ID: ").strip()
            if not input_cid:
                print(" Setup cancelled.")
                return
            input_csec = input(" Client Secret: ").strip()
            if not input_csec:
                print(" Setup cancelled.")
                return

            client_id = input_cid
            client_secret = input_csec

            with open(OAUTH_CLIENT_FILE, "w", encoding="utf-8") as f:
                json.dump({"client_id": client_id, "client_secret": client_secret}, f, indent=2)
            print(f" Saved client credentials to: {OAUTH_CLIENT_FILE}")
        except EOFError:
            print("\n Non-interactive environment detected. Run 'python auth_setup.py diagnose'.")
            return

    # Pre-flight probe
    diag = diagnose_google_oauth_endpoint(client_id, client_secret)
    if diag.status_code != 200:
        print(f"\n [ERROR] Google OAuth Pre-flight check failed (Status {diag.status_code}: {diag.error_code})")
        print(f" Detail: {diag.error_description}")
        print(f"\n Remediation:\n{diag.remediation_hint}")
        return

    print("\n Starting Google OAuth device authorization...")
    try:
        creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
        code = creds.get_code()
        url = f"{code['verification_url']}?user_code={code['user_code']}"
        print("-" * 65)
        print(f" Pair Code:        {code['user_code']}")
        print(f" Verification URL: {url}")
        print("-" * 65)
        print(" Opening browser to verification page...")
        webbrowser.open(url)

        input("\n Finish the sign-in flow in your browser, then press Enter here to complete setup... ")

        raw_token = creds.token_from_code(code["device_code"])
        expires_in = raw_token.get("refresh_token_expires_in", raw_token.get("expires_in", 3600))
        token_data = {
            "scope": raw_token.get("scope", OAUTH_SCOPE),
            "token_type": raw_token.get("token_type", "Bearer"),
            "access_token": raw_token["access_token"],
            "refresh_token": raw_token["refresh_token"],
            "expires_in": expires_in,
            "expires_at": int(raw_token.get("expires_at", 0))
        }

        with open(OAUTH_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

        print("\n" + "=" * 65)
        print(f" SUCCESS: Authenticated session token stored at:\n  {OAUTH_TOKEN_FILE}")
        print("=" * 65)

        # Verification
        ytm = YTMusic(auth=str(OAUTH_TOKEN_FILE), oauth_credentials=creds)
        print(" Verification: Authenticated YouTube Music session active!")

    except BadOAuthClient as e:
        print(f"\n [ERROR] Bad OAuth Client: {e}")
        print(" Remediation: Verify 'YouTube Data API v3' is enabled and client_id/secret match.")
    except UnauthorizedOAuthClient as e:
        print(f"\n [ERROR] Unauthorized OAuth Client: {e}")
    except Exception as e:
        print(f"\n [ERROR] OAuth setup failed: {e}")


def status_auth(secrets_dir: Optional[Path] = None):
    """
    Reports status of authentication credentials without printing secrets.
    """
    base_dir = secrets_dir or SECRETS_DIR
    oauth_client_path = base_dir / "oauth_client.json"
    oauth_token_path = base_dir / "oauth.json"
    headers_path = base_dir / "headers_auth.json"
    cookies_path = base_dir / "cookies.txt"

    client_id, client_secret = load_client_credentials(secrets_dir=base_dir)

    print("\n" + "=" * 65)
    print("      ANIMUS YOUTUBE MUSIC AUTHENTICATION STATUS")
    print("=" * 65)
    print(f" Secrets directory: {base_dir}\n")

    print(f" [1] Client Credentials: {'CONFIGURED' if (client_id and client_secret) else 'NOT FOUND'}")
    print(f" [2] OAuth Token:        {'PRESENT' if oauth_token_path.is_file() else 'NOT FOUND'}")
    print(f" [3] Headers Auth:       {'PRESENT' if headers_path.is_file() else 'NOT FOUND'}")
    print(f" [4] Cookies File:       {'PRESENT' if cookies_path.is_file() else 'NOT FOUND'}\n")

    if oauth_token_path.is_file() and client_id and client_secret:
        try:
            oauth_creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
            ytm = YTMusic(auth=str(oauth_token_path), oauth_credentials=oauth_creds)
            print(" -> Active authenticated OAuth session verified successfully.")
            return
        except Exception as e:
            print(f" -> OAuth token verification failed: {e}")
            print(" -> Daemon will fall back to GUEST MODE.")
            return

    if headers_path.is_file():
        try:
            ytm = YTMusic(str(headers_path))
            print(" -> Active authenticated session verified via headers_auth.json.")
            return
        except Exception as e:
            print(f" -> headers_auth.json verification failed: {e}")

    print(" -> No active authenticated session. Animus PC Music Daemon is running in GUEST MODE.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "setup":
            setup_ytm_oauth()
        elif cmd in ("diagnose", "diagnostic"):
            run_diagnostics()
        else:
            status_auth()
    else:
        status_auth()
