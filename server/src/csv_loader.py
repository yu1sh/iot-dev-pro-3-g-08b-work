#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv


CSV_HEADER = ["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"]


def _read_rows(csv_file, logger):
    """CSVファイルを読み込み、存在しない場合は空の行リストを返す。"""
    try:
        with csv_file.open(newline="", encoding="utf-8") as f:
            return list(csv.reader(f))
    except FileNotFoundError:
        logger.info("CSV file not found. Creating an empty CSV path=%s", csv_file)
        return []


def _is_empty_row(row):
    """空行または空白だけで構成された行かを判定する。"""
    return not row or all(not value.strip() for value in row)


def _filter_valid_rows(rows, csv_file, logger, has_valid_header):
    """空行と列数が不正な行を除外したデータ行を返す。"""
    data_rows = rows[1:] if has_valid_header else rows
    start_row_number = 2 if has_valid_header else 1
    valid_rows = []

    for row_number, row in enumerate(data_rows, start=start_row_number):
        if _is_empty_row(row):
            continue
        if len(row) != len(CSV_HEADER):
            logger.warning(
                "Ignoring malformed CSV row path=%s row=%s values=%s",
                csv_file,
                row_number,
                row,
            )
            continue
        valid_rows.append(row)

    return valid_rows


def _write_rows(csv_file, rows):
    """正規化済みのCSV行を書き込む。"""
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def check_csv(csv_file, logger):
    """ダッシュボードで安全に読み込めるCSVファイルを用意する。"""
    rows = _read_rows(csv_file, logger)

    has_valid_header = rows and rows[0] == CSV_HEADER
    if rows and not has_valid_header:
        logger.warning("CSV header is invalid. Replacing it path=%s", csv_file)

    valid_rows = _filter_valid_rows(rows, csv_file, logger, has_valid_header)
    normalized_rows = [CSV_HEADER, *valid_rows]
    if rows != normalized_rows:
        _write_rows(csv_file, normalized_rows)
