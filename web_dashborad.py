import csv
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    print("Start")

    with open(Path(__file__).with_name("sensor_readings.csv"), newline="") as f:
        csv_data = list(csv.reader(f))
    return render_template("dashboard.html", input_from_python = csv_data)

if __name__ == "__main__":
    app.run(host = '0.0.0.0', port = 5001, debug=True)