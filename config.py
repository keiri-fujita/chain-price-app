import json
import os

from dotenv import load_dotenv

# ローカル開発時に .env を読む
load_dotenv()


class Config:
    # Flask セッション用
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # 共通ログインパスワード
    APP_PASSWORD = os.getenv("APP_PASSWORD", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # Google スプレッドシートID
    MASTER_SPREADSHEET_ID = os.getenv("MASTER_SPREADSHEET_ID", "")

    # Render では環境変数に JSON文字列 を入れる想定
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    # 使用するシート名
    SHEET_CHAIN_MASTER = "chain_master"
    SHEET_LABOR_MASTER = "labor_master"
    SHEET_PARTS_MASTER = "parts_master"
    SHEET_MARKET_MASTER = "market_master"
    SHEET_APP_SETTINGS = "app_settings"

    # このアプリで扱う素材は固定
    ALLOWED_MATERIALS = ["Pt850", "K18YG"]

    # セッションキー名
    LOGIN_SESSION_KEY = "logged_in"


def get_service_account_info() -> dict:
    """
    環境変数の JSON文字列 を dict に変換して返す。
    """
    raw = Config.GOOGLE_SERVICE_ACCOUNT_JSON
    if not raw:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません。")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON のJSON形式が不正です。") from exc