#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, send_file
from logger_setup import setup_logger

app = Flask(__name__)
logger = setup_logger(__name__)

CSV_DIR = Path(__file__).parent.parent / "outputs"
CSV_FILE = CSV_DIR / "sensor_readings.csv"
f_host = '0.0.0.0'
f_port = 5001

@app.route("/", methods=["GET"])
def index():
    logger.info("Dashboard request received")

    with open(CSV_FILE, newline="") as f:
        csv_data = list(csv.reader(f))
    return render_template("dashboard.html", input_from_python = csv_data)


@app.route('/files')
def download():
    logger.info("Download CSV")
    dt = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"sensor_readings_{dt}.csv"
    return send_file(CSV_FILE, as_attachment=True, download_name=file_name)


if __name__ == "__main__":
    logger.info("Start flask server. host=%s, port %s", f_host, f_port)
    app.run(host = f_host, port = f_port, debug=True)
    # debug=True: コードを変更するたびにmainを再実行するため、その度にブラウザが追加で開く
    # debug=True: 要は自動でリロードするため、ログファイルが2個生まれるってわけ
    # 本番はセキュリティやログファイルの観点からdebug=Falseにするべき
