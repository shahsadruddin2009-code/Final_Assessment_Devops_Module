#!/usr/bin/env python3
"""Generate an HTML dashboard summarising the latest CI/CD run.

Reads the pytest JUnit XML (reports/pytest-results.xml) and the Go JUnit XML
(reports/go-results.xml) and writes a self-contained dashboard to
dashboard/index.html including:
  - timestamp and run metadata
  - per-language test counts (Python and Go) and status
  - a persistent run-history log (date, time, push id, result, language,
    number of tests) accumulated across pipeline runs
  - embedded HTML report link
"""

from __future__ import annotations

import json
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path("reports")
DASHBOARD_DIR = Path("dashboard")
HISTORY_DIR = Path(".dashboard-history")
HISTORY_FILE = HISTORY_DIR / "history.json"
MAX_HISTORY_ROWS = 50


def parse_junit(path: Path) -> dict:
    """Sum counts across every <testsuite> in a JUnit XML file."""
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    if not path.exists():
        return totals

    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    for suite in suites:
        totals["tests"] += int(suite.get("tests", 0))
        totals["failures"] += int(suite.get("failures", 0))
        totals["errors"] += int(suite.get("errors", 0))
        totals["skipped"] += int(suite.get("skipped", 0))
        totals["time"] += float(suite.get("time", 0.0))
    return totals


def summarise(results: dict) -> dict:
    passed = results["tests"] - results["failures"] - results["errors"] - results["skipped"]
    if results["tests"] == 0:
        status = "NO DATA"
    elif results["failures"] == 0 and results["errors"] == 0:
        status = "PASSED"
    else:
        status = "FAILED"
    return {**results, "passed": passed, "status": status}


BACK_LINK = (
    '<a href="index.html" style="display:inline-block;margin:0.75rem 0;'
    'font-family:system-ui,sans-serif;font-size:1rem;text-decoration:none;'
    'background:#0d6efd;color:#fff;padding:0.4rem 0.9rem;border-radius:6px">'
    '&larr; Back to dashboard</a>'
)


def copy_report_html() -> str:
    """Copy the HTML report into the dashboard folder, adding a back link."""
    source = REPORTS_DIR / "pytest-report.html"
    if source.exists():
        html = source.read_text(encoding="utf-8")
        if "Back to dashboard" not in html:
            html = html.replace("<body>", f"<body>\n{BACK_LINK}", 1)
        (DASHBOARD_DIR / "pytest-report.html").write_text(html, encoding="utf-8")
        return "pytest-report.html"
    return ""


def parse_junit_cases(path: Path) -> list[dict]:
    """Extract every <testcase> from a JUnit XML file."""
    if not path.exists():
        return []
    cases = []
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        if case.find("failure") is not None:
            status, detail_node = "FAILED", case.find("failure")
        elif case.find("error") is not None:
            status, detail_node = "ERROR", case.find("error")
        elif case.find("skipped") is not None:
            status, detail_node = "SKIPPED", case.find("skipped")
        else:
            status, detail_node = "PASSED", None
        detail = ""
        if detail_node is not None:
            detail = (detail_node.get("message") or detail_node.text or "").strip()
        cases.append({
            "suite": case.get("classname", ""),
            "name": case.get("name", ""),
            "time": float(case.get("time", 0.0)),
            "status": status,
            "detail": detail,
        })
    return cases


def generate_go_report(summary: dict, now: datetime) -> str:
    """Write a detailed per-test Go report page and return its filename."""
    cases = parse_junit_cases(REPORTS_DIR / "go-results.xml")
    if not cases:
        return ""

    status_colour = {"PASSED": "var(--ok)", "FAILED": "var(--fail)", "ERROR": "var(--fail)", "SKIPPED": "#6c757d"}
    rows = "\n".join(
        "<tr>"
        f"<td><code>{c['suite']}</code></td>"
        f"<td>{c['name']}</td>"
        f"<td>{c['time']:.3f}s</td>"
        f"<td style='color:{status_colour[c['status']]};font-weight:700'>{c['status']}</td>"
        f"<td>{c['detail']}</td>"
        "</tr>"
        for c in cases
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Go Test Report — Northwind Delivery</title>
  <style>
    :root {{ --ok: #28a745; --fail: #dc3545; --bg: #f4f6f8; --card: #ffffff; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); margin: 0; padding: 2rem; color: #222; }}
    h1 {{ margin-top: 0; }}
    .summary {{ background: var(--card); border-radius: 8px; padding: 1rem 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.08); display: inline-block; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.08); }}
    th, td {{ padding: 0.55rem 0.9rem; text-align: left; border-bottom: 1px solid #e9ecef; }}
    thead th {{ background: #e9ecef; }}
    code {{ background: #f1f3f5; padding: 0.1rem 0.3rem; border-radius: 4px; }}
    a {{ display: inline-block; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  {BACK_LINK}
  <h1>Go Test Report — Northwind Delivery (Go comparison service)</h1>
  <div class="summary">
    <strong>{summary['tests']}</strong> tests &middot;
    <strong style="color:var(--ok)">{summary['passed']} passed</strong> &middot;
    <strong style="color:var(--fail)">{summary['failures'] + summary['errors']} failed</strong> &middot;
    {summary['skipped']} skipped &middot; {summary['time']:.2f}s
    &middot; generated {now.isoformat()}
  </div>
  <table>
    <thead>
      <tr><th>Package / Suite</th><th>Test</th><th>Duration</th><th>Result</th><th>Detail</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>"""

    (DASHBOARD_DIR / "go-report.html").write_text(html, encoding="utf-8")
    return "go-report.html"


def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def append_history(history: list[dict], now: datetime, sha: str, run_number: str,
                   trigger: str, language: str, summary: dict) -> None:
    if summary["status"] == "NO DATA":
        return
    # Re-runs of the same workflow run replace their earlier entry instead of duplicating it.
    history[:] = [e for e in history
                  if not (e.get("run_number") == run_number and e.get("language") == language
                          and e.get("push_id") == sha[:12])]
    history.append({
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S UTC"),
        "push_id": sha[:12],
        "run_number": run_number,
        "trigger": trigger,
        "language": language,
        "tests": summary["tests"],
        "passed": summary["passed"],
        "failed": summary["failures"] + summary["errors"],
        "result": summary["status"],
    })


def save_history(history: list[dict]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history[-MAX_HISTORY_ROWS:], indent=2), encoding="utf-8")


def language_card(title: str, summary: dict) -> str:
    if summary["status"] == "PASSED":
        colour = "var(--ok)"
    elif summary["status"] == "FAILED":
        colour = "var(--fail)"
    else:
        colour = "#6c757d"
    return f"""    <div class="card">
      <div>{title}</div>
      <div class="metric" style="color: {colour}">{summary['status']}</div>
      <div>{summary['passed']} / {summary['tests']} passed &middot; {summary['time']:.2f}s</div>
    </div>"""


def history_rows(history: list[dict]) -> str:
    rows = []
    for entry in reversed(history[-MAX_HISTORY_ROWS:]):
        colour = "var(--ok)" if entry["result"] == "PASSED" else "var(--fail)"
        rows.append(
            "<tr>"
            f"<td>{entry['date']}</td>"
            f"<td>{entry['time']}</td>"
            f"<td><code>{entry['push_id']}</code></td>"
            f"<td>{entry.get('run_number', '')}</td>"
            f"<td>{entry['language']}</td>"
            f"<td>{entry['tests']}</td>"
            f"<td>{entry['passed']}</td>"
            f"<td>{entry['failed']}</td>"
            f"<td style='color:{colour};font-weight:700'>{entry['result']}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_dashboard() -> None:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    report_file = copy_report_html()

    python_summary = summarise(parse_junit(REPORTS_DIR / "pytest-results.xml"))
    go_summary = summarise(parse_junit(REPORTS_DIR / "go-results.xml"))

    now = datetime.now(timezone.utc)
    go_report_file = generate_go_report(go_summary, now)

    combined_tests = python_summary["tests"] + go_summary["tests"]
    combined_passed = python_summary["passed"] + go_summary["passed"]
    combined_failed = (python_summary["failures"] + python_summary["errors"]
                       + go_summary["failures"] + go_summary["errors"])
    combined_skipped = python_summary["skipped"] + go_summary["skipped"]
    combined_time = python_summary["time"] + go_summary["time"]
    status = "PASSED" if combined_failed == 0 and combined_tests > 0 else "FAILED"

    sha = os.environ.get("GITHUB_SHA", "local")
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "-")
    trigger = os.environ.get("GITHUB_EVENT_NAME", "manual")

    history = load_history()
    append_history(history, now, sha, run_number, trigger, "Python", python_summary)
    append_history(history, now, sha, run_number, trigger, "Go", go_summary)
    save_history(history)
    shutil.copy(HISTORY_FILE, DASHBOARD_DIR / "history.json")

    metadata = {
        "Repository": os.environ.get("GITHUB_REPOSITORY", "local"),
        "Branch / Ref": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "Commit SHA": sha[:12],
        "Run Number": run_number,
        "Trigger": trigger,
        "Timestamp (UTC)": now.isoformat(),
        "Python Version": os.environ.get("PYTHON_VERSION", "3.12"),
        "Go Version": os.environ.get("GO_VERSION", "1.22"),
    }

    rows = "\n".join(
        f'<tr><th>{key}</th><td>{value}</td></tr>' for key, value in metadata.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Northwind Delivery — CI/CD Dashboard</title>
  <style>
    :root {{ --ok: #28a745; --fail: #dc3545; --bg: #f4f6f8; --card: #ffffff; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); margin: 0; padding: 2rem; color: #222; }}
    h1 {{ margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
    .card {{ background: var(--card); border-radius: 8px; padding: 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.08); }}
    .metric {{ font-size: 2rem; font-weight: 700; margin: 0.25rem 0; }}
    .status {{ color: {'var(--ok)' if status == 'PASSED' else 'var(--fail)'}; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.08); margin-bottom: 1.5rem; }}
    .meta-table {{ max-width: 600px; }}
    th, td {{ padding: 0.6rem 0.9rem; text-align: left; border-bottom: 1px solid #e9ecef; }}
    thead th {{ background: #e9ecef; }}
    .meta-table th {{ background: #e9ecef; width: 40%; }}
    a {{ display: inline-block; margin-top: 1rem; }}
  </style>
</head>
<body>
  <h1>Northwind Logistics — Delivery Tracking CI/CD Dashboard</h1>

  <div class="grid">
    <div class="card">
      <div>Overall Status</div>
      <div class="metric status">{status}</div>
    </div>
{language_card("Python Tests", python_summary)}
{language_card("Go Tests", go_summary)}
    <div class="card">
      <div>Total Tests</div>
      <div class="metric">{combined_tests}</div>
    </div>
    <div class="card">
      <div>Passed</div>
      <div class="metric" style="color: var(--ok)">{combined_passed}</div>
    </div>
    <div class="card">
      <div>Failed</div>
      <div class="metric" style="color: var(--fail)">{combined_failed}</div>
    </div>
    <div class="card">
      <div>Skipped</div>
      <div class="metric">{combined_skipped}</div>
    </div>
    <div class="card">
      <div>Duration</div>
      <div class="metric">{combined_time:.2f}s</div>
    </div>
  </div>

  <h2>Run Metadata</h2>
  <table class="meta-table">
    {rows}
  </table>

  <h2>Run History</h2>
  <table>
    <thead>
      <tr>
        <th>Date</th><th>Time</th><th>Push ID</th><th>Run #</th>
        <th>Language</th><th>Tests</th><th>Passed</th><th>Failed</th><th>Result</th>
      </tr>
    </thead>
    <tbody>
      {history_rows(history)}
    </tbody>
  </table>

  {f'<a href="{report_file}">View detailed pytest report</a>' if report_file else '<p>Detailed pytest report not available.</p>'}
  {f'<a href="{go_report_file}" style="margin-left:1rem">View detailed Go test report</a>' if go_report_file else '<p>Detailed Go test report not available.</p>'}

  <footer>
    <p><small>Generated on {metadata["Timestamp (UTC)"]} by scripts/generate_dashboard.py</small></p>
  </footer>
</body>
</html>"""

    (DASHBOARD_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Dashboard generated at {DASHBOARD_DIR / 'index.html'}")
    print(f"History entries: {len(history)}")


if __name__ == "__main__":
    build_dashboard()
