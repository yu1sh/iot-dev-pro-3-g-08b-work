#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, send_file

app = Flask(__name__)

CSV_DIR = Path(__file__).parent.parent / "outputs"
CSV_FILE = CSV_DIR / "sensor_readings.csv"

@app.route("/", methods=["GET"])
def index():
    print("Start")

    with open(CSV_FILE, newline="") as f:
        csv_data = list(csv.reader(f))
    return render_template("dashboard.html", input_from_python = csv_data)


@app.route('/files')
def download():
    dt = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"sensor_readings_{dt}.csv"
    return send_file(CSV_FILE, as_attachment=True, download_name=file_name)


if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5001, debug=True)