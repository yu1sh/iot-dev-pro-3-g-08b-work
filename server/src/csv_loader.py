#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import os
import tempfile
from datetime import datetime


CSV_HEADER = ["timestamp", "raspi_id", "dht_temp", "dht_humid", "sensor_id", "status"]
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
ALLOWED_STATUSES = {"OK", "WARNING", "ERROR", "SEND_FAILED"}


class CsvImportError(ValueError):
    """アップロードされたCSVが取り込めない場合のエラー。"""


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
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=csv_file.parent,
            prefix=f".{csv_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            temporary_path = f.name
            csv.writer(f).writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary_path, csv_file)
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _validate_import_row(row, row_number):
    if _is_empty_row(row):
        return None
    if len(row) != len(CSV_HEADER):
        raise CsvImportError(f"{row_number}行目の列数が正しくありません")

    normalized = [value.strip() for value in row]
    try:
        timestamp = datetime.strptime(normalized[0], TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise CsvImportError(
            f"{row_number}行目の日時は YYYYMMDD-HHMMSS 形式で入力してください"
        ) from exc

    if not normalized[1] or not normalized[4]:
        raise CsvImportError(f"{row_number}行目の端末IDまたはセンサーIDが空です")
    if normalized[5] not in ALLOWED_STATUSES:
        raise CsvImportError(f"{row_number}行目のステータスが正しくありません")

    for column, label in ((2, "温度"), (3, "湿度")):
        if normalized[column]:
            try:
                float(normalized[column])
            except ValueError as exc:
                raise CsvImportError(
                    f"{row_number}行目の{label}が数値ではありません"
                ) from exc

    return timestamp, normalized


def merge_uploaded_csv(csv_file, uploaded_file, logger):
    """ローカル保存CSVを検証し、既存CSVへ時系列順にマージする。"""
    try:
        uploaded_file.stream.seek(0)
        text = uploaded_file.stream.read().decode("utf-8-sig")
    except (AttributeError, UnicodeDecodeError) as exc:
        raise CsvImportError("UTF-8形式のCSVファイルを選択してください") from exc

    try:
        uploaded_rows = list(csv.reader(text.splitlines(), strict=True))
    except csv.Error as exc:
        raise CsvImportError("CSVの書式が正しくありません") from exc

    if not uploaded_rows or uploaded_rows[0] != CSV_HEADER:
        raise CsvImportError("CSVヘッダーが正しくありません")

    imported_rows = []
    for row_number, row in enumerate(uploaded_rows[1:], start=2):
        validated = _validate_import_row(row, row_number)
        if validated is not None:
            imported_rows.append(validated)

    if not imported_rows:
        raise CsvImportError("取り込めるデータ行がありません")

    check_csv(csv_file, logger)
    existing_rows = _read_rows(csv_file, logger)[1:]
    existing_set = {tuple(row) for row in existing_rows}
    added_rows = []
    duplicate_count = 0
    for timestamp, row in imported_rows:
        row_key = tuple(row)
        if row_key in existing_set:
            duplicate_count += 1
            continue
        existing_set.add(row_key)
        added_rows.append((timestamp, row))

    combined = []
    for row_number, row in enumerate(existing_rows, start=2):
        try:
            timestamp = datetime.strptime(row[0], TIMESTAMP_FORMAT)
        except ValueError:
            logger.warning(
                "Keeping row with invalid timestamp at end path=%s row=%s",
                csv_file,
                row_number,
            )
            timestamp = datetime.max
        combined.append((timestamp, row))
    combined.extend(added_rows)
    combined.sort(key=lambda item: item[0])

    _write_rows(csv_file, [CSV_HEADER, *(row for _, row in combined)])
    logger.info(
        "Merged uploaded CSV path=%s added=%s duplicates=%s",
        csv_file,
        len(added_rows),
        duplicate_count,
    )
    return len(added_rows), duplicate_count


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
