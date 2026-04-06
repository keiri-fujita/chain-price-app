from __future__ import annotations

from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for

from config import Config
from services.calculator import CalculationError, calculate_chain_price
from services.sheets_service import SheetsService

app = Flask(__name__)
app.config.from_object(Config)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get(Config.LOGIN_SESSION_KEY):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def build_default_form_data() -> dict:
    return {
        "supplier": "",
        "material": "",
        "display_name": "",
        "length_cm": "",
        "clasp_size": "なし",
        "plate_size": "なし",
        "slide_size": "なし",
    }


@app.route("/")
def index():
    if session.get(Config.LOGIN_SESSION_KEY):
        return redirect(url_for("calculator"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error_message = ""

    if request.method == "POST":
        password = request.form.get("password", "")

        if password and password == Config.APP_PASSWORD:
            session[Config.LOGIN_SESSION_KEY] = True
            return redirect(url_for("calculator"))

        error_message = "パスワードが違います。"

    return render_template("login.html", error_message=error_message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/calculator", methods=["GET", "POST"])
@login_required
def calculator():
    sheets = SheetsService()
    masters = sheets.get_all_masters()

    chain_rows = masters["chain_master"]
    parts_rows = masters["parts_master"]
    market_rows = masters["market_master"]

    supplier_options = sheets.get_supplier_options(chain_rows)
    material_options = Config.ALLOWED_MATERIALS

    form_data = build_default_form_data()
    errors = {}
    result = None

    if request.method == "POST":
        form_data = {
            "supplier": request.form.get("supplier", "").strip(),
            "material": request.form.get("material", "").strip(),
            "display_name": request.form.get("display_name", "").strip(),
            "length_cm": request.form.get("length_cm", "").strip(),
            "clasp_size": request.form.get("clasp_size", "なし").strip() or "なし",
            "plate_size": request.form.get("plate_size", "なし").strip() or "なし",
            "slide_size": request.form.get("slide_size", "なし").strip() or "なし",
        }

        # バリデーション
        if not form_data["supplier"]:
            errors["supplier"] = "仕入先を選択してください。"

        if not form_data["material"]:
            errors["material"] = "素材を選択してください。"
        elif form_data["material"] not in Config.ALLOWED_MATERIALS:
            errors["material"] = "素材が不正です。"

        if not form_data["display_name"]:
            errors["display_name"] = "チェーン種類を選択してください。"

        if not form_data["length_cm"]:
            errors["length_cm"] = "全長を入力してください。"
        elif not form_data["length_cm"].isdigit():
            errors["length_cm"] = "全長は整数で入力してください。"

        if not errors:
            try:
                result = calculate_chain_price(
                    supplier=form_data["supplier"],
                    material=form_data["material"],
                    display_name=form_data["display_name"],
                    length_cm=int(form_data["length_cm"]),
                    clasp_size=form_data["clasp_size"],
                    plate_size=form_data["plate_size"],
                    slide_size=form_data["slide_size"],
                    chain_rows=masters["chain_master"],
                    labor_rows=masters["labor_master"],
                    parts_rows=masters["parts_master"],
                    market_rows=masters["market_master"],
                    settings_rows=masters["app_settings"],
                )
            except CalculationError as exc:
                errors["form"] = str(exc)
            except Exception:
                errors["form"] = (
                    "計算中にエラーが発生しました。マスタ設定を確認してください。"
                )

    selected_supplier = form_data["supplier"]
    selected_material = form_data["material"]

    chain_options = sheets.get_chain_options(
        chain_rows,
        supplier=selected_supplier,
        material=selected_material,
    )

    # 素材未選択ならパーツ候補は空にせず、とりあえず「なし」のみ
    if selected_material:
        clasp_options = sheets.get_part_options(parts_rows, "引き輪", selected_material)
        plate_options = sheets.get_part_options(
            parts_rows, "プレート", selected_material
        )
        slide_options = sheets.get_part_options(
            parts_rows, "スライド金具", selected_material
        )
    else:
        clasp_options = ["なし"]
        plate_options = ["なし"]
        slide_options = ["なし"]

    # 念のため「なし」が無ければ補う
    if "なし" not in clasp_options:
        clasp_options.insert(0, "なし")
    if "なし" not in plate_options:
        plate_options.insert(0, "なし")
    if "なし" not in slide_options:
        slide_options.insert(0, "なし")

    # ヘッダー表示用の当日相場
    market_map = {}
    for row in market_rows:
        material = str(row.get("material", "")).strip()
        price = row.get("market_price", "")
        market_map[material] = price

    return render_template(
        "calculator.html",
        form_data=form_data,
        errors=errors,
        result=result,
        supplier_options=supplier_options,
        material_options=material_options,
        chain_options=chain_options,
        clasp_options=clasp_options,
        plate_options=plate_options,
        slide_options=slide_options,
        market_map=market_map,
    )


if __name__ == "__main__":
    app.run(debug=True)
