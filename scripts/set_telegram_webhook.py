import argparse
import os
import sys

import requests
from dotenv import load_dotenv


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_webhook_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if not cleaned.startswith("https://"):
        raise RuntimeError("Webhook base URL must start with https://")
    return f"{cleaned}/telegram/webhook"


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def set_webhook(token: str, webhook_url: str, secret: str | None) -> dict:
    payload: dict[str, str] = {"url": webhook_url}
    if secret:
        payload["secret_token"] = secret
    response = requests.post(_api_url(token, "setWebhook"), json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def get_webhook_info(token: str) -> dict:
    response = requests.get(_api_url(token, "getWebhookInfo"), timeout=20)
    response.raise_for_status()
    return response.json()


def delete_webhook(token: str) -> dict:
    response = requests.post(_api_url(token, "deleteWebhook"), timeout=20)
    response.raise_for_status()
    return response.json()


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Set/verify Telegram webhook without shell escaping issues."
    )
    parser.add_argument(
        "--base-url",
        help="Public HTTPS base URL (for example: https://xxxx.ngrok-free.app).",
    )
    parser.add_argument(
        "--secret",
        help="Webhook secret token. Defaults to TELEGRAM_WEBHOOK_SECRET from env.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete webhook instead of setting it.",
    )
    parser.add_argument(
        "--info-only",
        action="store_true",
        help="Only print current webhook info.",
    )
    args = parser.parse_args()

    try:
        token = _require_env("TELEGRAM_BOT_TOKEN")

        if args.info_only:
            info = get_webhook_info(token)
            print(info)
            return 0

        if args.delete:
            result = delete_webhook(token)
            print(result)
            return 0

        if not args.base_url:
            raise RuntimeError("--base-url is required unless --info-only or --delete is used.")

        secret = args.secret if args.secret is not None else os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        webhook_url = _build_webhook_url(args.base_url)

        set_result = set_webhook(token, webhook_url, secret or None)
        info_result = get_webhook_info(token)

        print("setWebhook:")
        print(set_result)
        print("\ngetWebhookInfo:")
        print(info_result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
