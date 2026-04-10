from __future__ import annotations

import math
from typing import Any


class CalculationError(Exception):
    """
    マスタ不整合や計算不能時に使う業務用エラー。
    """


def to_float(value: Any, default: float | None = None) -> float:
    text = str(value).strip()
    if text == "":
        if default is not None:
            return default
        raise ValueError("数値が空です。")
    return float(text)


def to_int(value: Any, default: int | None = None) -> int:
    text = str(value).strip()
    if text == "":
        if default is not None:
            return default
        raise ValueError("整数が空です。")
    return int(float(text))


def floor_yen(value: float) -> int:
    """
    円未満切り捨て。
    """
    return math.floor(value)


def round_up_to_10(value: float) -> int:
    """
    10円単位切り上げ。
    例: 12341 -> 12350
    """
    return int(math.ceil(value / 10.0) * 10)


def format_yen(value: int | float | None) -> str:
    if value is None:
        return ""
    return f"¥{int(value):,}"


def encode_cost(cost: int) -> str:
    """
    下代を暗号化する。

    例
    17,220 → 101722
    12,300 → 20123
    98,700 → 20987
    """

    s = str(cost)

    zero_count = 0

    for c in reversed(s):
        if c == "0":
            zero_count += 1
        else:
            break

    significant = s[:-zero_count] if zero_count > 0 else s

    prefix = str(zero_count * 10)

    return prefix + significant


def get_setting_value(settings_rows: list[dict[str, Any]], key: str) -> str:
    for row in settings_rows:
        if str(row.get("setting_key", "")).strip() == key:
            return str(row.get("setting_value", "")).strip()
    raise CalculationError(f"app_settings に {key} が見つかりません。")


def get_market_price(market_rows: list[dict[str, Any]], material: str) -> float:
    for row in market_rows:
        if str(row.get("material", "")).strip() == material:
            return to_float(row.get("market_price", 0))
    raise CalculationError(f"market_master に {material} の相場が見つかりません。")


def find_chain(
    chain_rows: list[dict[str, Any]],
    supplier: str,
    material: str,
    display_name: str,
) -> dict[str, Any]:
    for row in chain_rows:
        if (
            str(row.get("supplier", "")).strip() == supplier
            and str(row.get("material", "")).strip() == material
            and str(row.get("display_name", "")).strip() == display_name
        ):
            return row
    raise CalculationError("該当するチェーンマスタが見つかりません。")


def find_labor_cost(
    labor_rows: list[dict[str, Any]],
    supplier: str,
    material: str,
    labor_rank: str,
) -> float:
    for row in labor_rows:
        if (
            str(row.get("supplier", "")).strip() == supplier
            and str(row.get("material", "")).strip() == material
            and str(row.get("labor_rank", "")).strip() == labor_rank
        ):
            return to_float(row.get("labor_cost", 0))
    raise CalculationError("工賃マスタが見つかりません。")


def find_part_price(
    parts_rows: list[dict[str, Any]],
    part_type: str,
    material: str,
    part_size: str,
) -> float:
    for row in parts_rows:
        if (
            str(row.get("part_type", "")).strip() == part_type
            and str(row.get("material", "")).strip() == material
            and str(row.get("part_size", "")).strip() == part_size
        ):
            return to_float(row.get("part_price", 0))
    raise CalculationError(f"{part_type} のパーツマスタが見つかりません。")


def calculate_chain_price(
    *,
    supplier: str,
    material: str,
    display_name: str,
    length_cm: int,
    clasp_size: str,
    plate_size: str,
    slide_size: str,
    chain_rows: list[dict[str, Any]],
    labor_rows: list[dict[str, Any]],
    parts_rows: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
    settings_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    価格計算の本体。
    戻り値は画面表示しやすいように整形済みの値も含める。
    """
    chain = find_chain(
        chain_rows=chain_rows,
        supplier=supplier,
        material=material,
        display_name=display_name,
    )

    labor_rank = str(chain.get("labor_rank", "")).strip()

    # 見積品は通常計算しない
    if labor_rank == "見積":
        market_price = get_market_price(market_rows, material)
        return {
            "mode": "estimate",
            "market_price": market_price,
            "price_ex_tax": "見積",
            "price_in_tax": "見積",
            "encoded_cost": "",
        }

    weight_per_cm = to_float(chain.get("weight_per_cm", ""))
    labor_cost = find_labor_cost(
        labor_rows=labor_rows,
        supplier=supplier,
        material=material,
        labor_rank=labor_rank,
    )

    market_price = get_market_price(market_rows, material)

    clasp_price = find_part_price(parts_rows, "引き輪", material, clasp_size)
    plate_price = find_part_price(parts_rows, "プレート", material, plate_size)
    slide_price = find_part_price(parts_rows, "スライド金具", material, slide_size)

    markup_rate = to_float(get_setting_value(settings_rows, "markup_rate"))
    tax_rate = to_float(get_setting_value(settings_rows, "tax_rate"))

    # 1. チェーン本体下代
    chain_cost = weight_per_cm * length_cm * market_price

    # 2. 工賃下代
    labor_total = weight_per_cm * labor_cost * length_cm

    # 3. パーツ合計
    parts_total = clasp_price + plate_price + slide_price

    # 4. 最終下代
    total_cost = chain_cost + labor_total + parts_total

    # 5. 最終下代を十円単位切り上げ
    rounded_cost = round_up_to_10(total_cost)

    # 7. 税抜上代（500円境界で千円丸め）
    price_ex_tax_raw = rounded_cost * markup_rate

    price_ex_tax = int(math.floor((price_ex_tax_raw + 500) / 1000) * 1000)

    # 8. 税込上代 = 税抜上代 × tax_rate → 円未満切り捨て
    price_in_tax = floor_yen(price_ex_tax * tax_rate)

    # 暗号化下代
    encoded_cost = encode_cost(rounded_cost)

    return {
        "mode": "normal",
        "market_price": market_price,
        "price_ex_tax": format_yen(price_ex_tax),
        "price_in_tax": format_yen(price_in_tax),
        "encoded_cost": encoded_cost,
        "debug_details": {
            "supplier": supplier,
            "material": material,
            "display_name": display_name,
            "weight_per_cm": weight_per_cm,
            "length_cm": length_cm,
            "market_price": market_price,
            "labor_rank": labor_rank,
            "labor_cost": labor_cost,
            "labor_total": labor_total,
            "clasp_size": clasp_size,
            "clasp_price": clasp_price,
            "plate_size": plate_size,
            "plate_price": plate_price,
            "slide_size": slide_size,
            "slide_price": slide_price,
            "chain_cost": chain_cost,
            "parts_total": parts_total,
            "total_cost": total_cost,
            "rounded_cost": rounded_cost,
            "markup_rate": markup_rate,
            "price_ex_tax_raw": price_ex_tax_raw,
            "price_ex_tax_rounded": price_ex_tax,
            "tax_rate": tax_rate,
            "price_in_tax_final": price_in_tax,
            "encoded_cost": encoded_cost,
        },
    }
