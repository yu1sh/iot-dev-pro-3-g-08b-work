"""GitHub ActionsのJob Summaryへテスト結果を出力する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree


def load_test_counts(report: Path) -> dict[str, int]:
    root = ElementTree.parse(report).getroot()
    counts = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}

    for test_case in root.iter("testcase"):
        counts["total"] += 1
        if test_case.find("failure") is not None:
            counts["failed"] += 1
        elif test_case.find("error") is not None:
            counts["errors"] += 1
        elif test_case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return counts


def load_coverage(report: Path) -> dict[str, int | float]:
    totals = json.loads(report.read_text(encoding="utf-8"))["totals"]
    return {
        "covered_lines": totals["covered_lines"],
        "num_statements": totals["num_statements"],
        "line_percent": totals["percent_covered"],
        "covered_branches": totals["covered_branches"],
        "num_branches": totals["num_branches"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--test-report", type=Path, required=True)
    parser.add_argument("--coverage-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.test_report.exists() or not args.coverage_report.exists():
        args.output.write_text(
            f"## {args.category} 結果\n\n結果ファイルを生成できなかったため、集計できませんでした。\n",
            encoding="utf-8",
        )
        return

    tests = load_test_counts(args.test_report)
    coverage = load_coverage(args.coverage_report)
    success_rate = tests["passed"] / tests["total"] * 100 if tests["total"] else 0
    branch_percent = (
        coverage["covered_branches"] / coverage["num_branches"] * 100
        if coverage["num_branches"]
        else 100
    )

    with args.output.open("a", encoding="utf-8") as output:
        output.write(
            f"## {args.category} 結果\n\n"
            "| 指標 | 値 |\n| --- | ---: |\n"
            f"| 実行件数 | {tests['total']} |\n"
            f"| 成功 | {tests['passed']} |\n"
            f"| 失敗 | {tests['failed']} |\n"
            f"| エラー | {tests['errors']} |\n"
            f"| スキップ | {tests['skipped']} |\n"
            f"| 成功率 | {success_rate:.1f}% |\n"
            f"| 行カバレッジ | {coverage['line_percent']:.1f}% ({coverage['covered_lines']}/{coverage['num_statements']}) |\n"
            f"| 分岐カバレッジ | {branch_percent:.1f}% ({coverage['covered_branches']}/{coverage['num_branches']}) |\n\n"
        )


if __name__ == "__main__":
    main()
