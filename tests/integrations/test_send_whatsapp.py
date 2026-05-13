from __future__ import annotations

import base64
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"


def local_secret(name: str) -> str:
    if not LOCAL_SECRETS_FILE.exists():
        return ""
    for line in LOCAL_SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def secret(name: str) -> str:
    return os.environ.get(name, "").strip() or local_secret(name)


def required_secret(name: str) -> str:
    value = secret(name)
    if not value:
        raise RuntimeError(f"Missing required secret: {name}")
    return value


def whatsapp_number(value: str) -> str:
    cleaned = value.strip()
    return cleaned if cleaned.startswith("whatsapp:") else f"whatsapp:{cleaned}"


def send_whatsapp(body: str) -> dict:
    account_sid = required_secret("TWILIO_ACCOUNT_SID")
    auth_token = required_secret("TWILIO_AUTH_TOKEN")
    from_number = whatsapp_number(required_secret("TWILIO_WHATSAPP_FROM"))
    to_number = whatsapp_number(required_secret("WHATSAPP_TO"))

    payload = urllib.parse.urlencode(
        {
            "From": from_number,
            "To": to_number,
            "Body": body,
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "my-dashboard-whatsapp-test/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a Twilio WhatsApp test message.")
    parser.add_argument("--body", default="hellow world", help="Message body to send.")
    args = parser.parse_args()

    try:
        result = send_whatsapp(args.body)
    except Exception as error:
        print(f"Failed to send WhatsApp message: {error}", file=sys.stderr)
        return 1
    print(f"Sent WhatsApp message: {result.get('sid', 'unknown sid')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
