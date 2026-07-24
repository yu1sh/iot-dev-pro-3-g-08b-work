#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import os
from datetime import datetime

from flask import Flask, render_template, request, send_file
try:
    from .csv_loader import CsvImportError, check_csv, merge_uploaded_csv
    from .csv_writter import CSV_FILE, CSV_LOCK
    from .env_loader import find_env_file, load_env_file, parse_bool_env
    from .logger_setup import setup_logger
except ImportError:
    from csv_loader import CsvImportError, check_csv, merge_uploaded_csv
    from csv_writter import CSV_FILE, CSV_LOCK
    from env_loader import find_env_file, load_env_file, parse_bool_env
    from logger_setup import setup_logger

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
logger = setup_logger(__name__)

def load_config():
    load_env_file(find_env_file("server"))
    return parse_bool_env(
        os.environ.get("DEBUG_MODE", "false"),
        "DEBUG_MODE",
        logger,
    )

@app.route("/", methods=["GET"])
def index():
    logger.info("Dashboard request received")

    return render_dashboard()


def render_dashboard(import_message=None, import_succeeded=None):
    with CSV_LOCK:
        check_csv(CSV_FILE, logger)
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            csv_data = list(csv.reader(f))
    last_timestamp = csv_data[-1][0] if len(csv_data) > 1 else "データなし"
    temperatures = [float(row[2]) for row in csv_data[1:] if row[2]]
    avg_temp = round(sum(temperatures) / len(temperatures), 1) if temperatures else 0
    humidities = [float(row[3]) for row in csv_data[1:] if row[3]]
    avg_humidity = round(sum(humidities) / len(humidities), 1) if humidities else 0
    return render_template(
        "dashboard.html",
        input_from_python=csv_data,
        modified_date=last_timestamp,
        import_message=import_message,
        import_succeeded=import_succeeded,
        temperature_average=avg_temp,
        humidity_average=avg_humidity
    )


@app.route("/files/import", methods=["POST"])
def import_csv():
    uploaded_file = request.files.get("csv_file")
    if uploaded_file is None or not uploaded_file.filename:
        return render_dashboard("CSVファイルを選択してください。", False), 400
    if not uploaded_file.filename.lower().endswith(".csv"):
        return render_dashboard("CSV形式のファイルを選択してください。", False), 400

    try:
        with CSV_LOCK:
            added_count, duplicate_count = merge_uploaded_csv(
                CSV_FILE,
                uploaded_file,
                logger,
            )
    except CsvImportError as exc:
        logger.warning("CSV import rejected filename=%s reason=%s", uploaded_file.filename, exc)
        return render_dashboard(str(exc), False), 400
    except OSError:
        logger.exception("Failed to import CSV filename=%s", uploaded_file.filename)
        return render_dashboard("CSVの保存に失敗しました。", False), 500

    return render_dashboard(
        f"{added_count}件を追加しました（重複 {duplicate_count}件）。",
        True,
    )

@app.route("/confirm", methods=["POST"])
def confirm():
    logger.info("Confirm button pressed")
    return render_dashboard(
        import_message="確認しました",
        import_succeeded=True,
    )

@app.route('/files')
def download():
    logger.info("Download CSV")
    dt = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"sensor_readings_{dt}.csv"
    with CSV_LOCK:
        check_csv(CSV_FILE, logger)
        return send_file(CSV_FILE, as_attachment=True, download_name=file_name)


def main():
    debug_mode = load_config()
    f_host = "0.0.0.0"
    f_port = 5001
    logger.info("Start flask server. host=%s, port %s", f_host, f_port)
    app.run(host=f_host, port=f_port, debug=debug_mode, use_reloader=False)
    # use_reloader=False: 開発者モードの内、自動リロードのみ無効 -> 余計なログファイル生成を解決
    # DEBUG_MODEの既定値は本番運用を考慮してFalse


if __name__ == "__main__":
    main()
