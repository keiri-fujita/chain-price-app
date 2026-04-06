from __future__ import annotations

from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from config import Config, get_service_account_info


class SheetsService:
    """
    Googleスプレッドシートから各マスタを読むためのサービス。
    まずは「読むだけ」に責務を限定する。
    """

    def __init__(self, spreadsheet_id: str | None = None):
        self.spreadsheet_id = spreadsheet_id or Config.MASTER_SPREADSHEET_ID
        self._spreadsheet = None

    def _get_client(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds_info = get_service_account_info()
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(credentials)

    def _get_spreadsheet(self):
        if self._spreadsheet is None:
            client = self._get_client()
            self._spreadsheet = client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def _get_records(self, sheet_name: str) -> list[dict[str, Any]]:
        """
        シートをヘッダー付きレコード一覧として取得する。
        空行は除外する。
        """
        worksheet = self._get_spreadsheet().worksheet(sheet_name)
        records = worksheet.get_all_records()

        cleaned = []
        for row in records:
            # 全列空の行は捨てる
            if not any(str(v).strip() for v in row.values()):
                continue
            cleaned.append(row)
        return cleaned

    @staticmethod
    def _is_active(row: dict[str, Any]) -> bool:
        """
        active列がある場合のみ有効判定する。
        TRUE / True / true / 1 を有効とみなす。
        active列が無いシートは有効扱い。
        """
        if "active" not in row:
            return True

        value = str(row.get("active", "")).strip().lower()
        return value in {"true", "1", "yes"}

    def get_chain_master(self) -> list[dict[str, Any]]:
        rows = self._get_records(Config.SHEET_CHAIN_MASTER)
        return [row for row in rows if self._is_active(row)]

    def get_labor_master(self) -> list[dict[str, Any]]:
        rows = self._get_records(Config.SHEET_LABOR_MASTER)
        return [row for row in rows if self._is_active(row)]

    def get_parts_master(self) -> list[dict[str, Any]]:
        rows = self._get_records(Config.SHEET_PARTS_MASTER)
        return [row for row in rows if self._is_active(row)]

    def get_market_master(self) -> list[dict[str, Any]]:
        return self._get_records(Config.SHEET_MARKET_MASTER)

    def get_app_settings(self) -> list[dict[str, Any]]:
        return self._get_records(Config.SHEET_APP_SETTINGS)

    def get_all_masters(self) -> dict[str, list[dict[str, Any]]]:
        """
        計算画面に必要なマスタをまとめて返す。
        """
        return {
            "chain_master": self.get_chain_master(),
            "labor_master": self.get_labor_master(),
            "parts_master": self.get_parts_master(),
            "market_master": self.get_market_master(),
            "app_settings": self.get_app_settings(),
        }

    @staticmethod
    def get_supplier_options(chain_rows: list[dict[str, Any]]) -> list[str]:
        suppliers = {
            str(row.get("supplier", "")).strip()
            for row in chain_rows
            if str(row.get("supplier", "")).strip()
        }
        return sorted(suppliers)

    @staticmethod
    def get_chain_options(
        chain_rows: list[dict[str, Any]],
        supplier: str = "",
        material: str = "",
    ) -> list[str]:
        """
        指定された仕入先・素材に合うチェーン種類(display_name)一覧を返す。
        未選択のときは広めに返す。
        """
        results = []
        for row in chain_rows:
            row_supplier = str(row.get("supplier", "")).strip()
            row_material = str(row.get("material", "")).strip()
            display_name = str(row.get("display_name", "")).strip()

            if not display_name:
                continue
            if supplier and row_supplier != supplier:
                continue
            if material and row_material != material:
                continue

            results.append(display_name)

        return sorted(set(results))

    @staticmethod
    def get_part_options(
        parts_rows: list[dict[str, Any]],
        part_type: str,
        material: str,
    ) -> list[str]:
        """
        パーツのプルダウン候補を返す。
        sort_order 昇順 → part_size で並べる。
        """
        filtered = []
        for row in parts_rows:
            if str(row.get("part_type", "")).strip() != part_type:
                continue
            if str(row.get("material", "")).strip() != material:
                continue

            filtered.append(row)

        def sort_key(row: dict[str, Any]):
            raw_order = row.get("sort_order", 9999)
            try:
                order = int(float(str(raw_order)))
            except ValueError:
                order = 9999
            size = str(row.get("part_size", "")).strip()
            return (order, size)

        filtered.sort(key=sort_key)

        options = []
        for row in filtered:
            size = str(row.get("part_size", "")).strip()
            if size:
                options.append(size)

        return options
