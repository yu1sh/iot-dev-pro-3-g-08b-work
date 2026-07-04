#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, send_file
try:
    from .env_loader import load_required_env, parse_int_env
    from .logger_setup import setup_logger
except ImportError:
    from env_loader import load_required_env, parse_int_env
    from logger_setup import setup_logger

app = Flask(__name__)
logger = setup_logger(__name__)

CSV_DIR = Path(__file__).parent.parent / "outputs"
CSV_FILE = CSV_DIR / "sensor_readings.csv"


def load_config():
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        env_file = Path.cwd() / "server" / "src" / ".env"
    env = load_required_env(env_file, ["F_HOST", "F_PORT"], logger)
    return env["F_HOST"], parse_int_env(env["F_PORT"], "F_PORT", logger)

@app.route("/", methods=["GET"])
def index():
    logger.info("Dashboard request received")

    # TODO: CSVファイルが存在しない場合でもエラーやダッシュボードが落ちないようにする
    # TODO: CSV読み込み時に壊れた行や空行を無視できるようにする
    with open(CSV_FILE, newline="") as f:
        csv_data = list(csv.reader(f))
    return render_template("dashboard.html", input_from_python = csv_data)


@app.route('/files')
def download():
    logger.info("Download CSV")
    dt = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"sensor_readings_{dt}.csv"
    return send_file(CSV_FILE, as_attachment=True, download_name=file_name)


def main():
    f_host, f_port = load_config()
    logger.info("Start flask server. host=%s, port %s", f_host, f_port)
    app.run(host = f_host, port = f_port, debug=True, use_reloader=False)
    # use_reloader=False: 開発者モードの内、自動リロードのみ無効 -> 余計なログファイル生成を解決
    # debug=True: コードを変更するたびにmainを再実行するため、その度にブラウザが追加で開く
    # debug=True: 要は自動でリロードするため、ログファイルが2個生まれるってわけ
    # 本番はセキュリティやログファイルの観点からdebug=Falseにするべき


if __name__ == "__main__":
    main()
