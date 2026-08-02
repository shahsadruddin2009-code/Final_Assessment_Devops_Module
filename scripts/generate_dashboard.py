#!/usr/bin/env python3
"""Generate an HTML dashboard summarising the latest CI/CD run.

Reads pytest XML/HTML reports from the reports/ directory and writes a
self-contained dashboard to dashboard/index.html including:
  - timestamp and run metadata
  - programming language versions
  - test counts and status
  - embedded HTML report link
"""

from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path("reports")
DASHBOARD_DIR = Path("dashboard")


def parse_pytest_junit(path: Path) -> dict:
    """Extract counts and suite metadata from a JUnit XML file."""
    tree = ET.parse(path)
    root = tree.getroot()
    testsuites = root if root.tag == "testsuites" else None
    suite = root if root.tag == "testsuite" else root.find("testsuite")

    if testsuites is not None:
        suite = testsuites.find("testsuite")

    return {
        "tests": int(suite.get("tests", 0)) if suite is not None else 0,
        "failures": int(suite.get("failures", 0)) if suite is not None else 0,
        "errors": int(suite.get("errors", 0)) if suite is not None else 0,
        "skipped": int(suite.get("skipped", 0)) if suite is not None else 0,
        "time": float(suite.get("time", 0.0)) if suite is not None else 0.0,
    }


def copy_report_html() -> str:
    """Copy the HTML report into the dashboard folder and return its filename."""
    source = REPORTS_DIR / "pytest-report.html"
    if source.exists():
        shutil.copy(source, DASHBOARD_DIR / "pytest-report.html")
        return "pytest-report.html"
    return ""


def build_dashboard() -> None:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    report_file = copy_report_html()

    junit = REPORTS_DIR / "pytest-results.xml"
    results = parse_pytest_junit(junit) if junit.exists() else {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}

    passed = results["tests"] - results["failures"] - results["errors"] - results["skipped"]
    status = "PASSED" if results["failures"] == 0 and results["errors"] == 0 else "FAILED"

    now = datetime.now(timezone.utc)
    metadata = {
        "Repository": os.environ.get("GITHUB_REPOSITORY", "local"),
        "Branch / Ref": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "Commit SHA": os.environ.get("GITHUB_SHA", "unknown")[:12],
        "Trigger": os.environ.get("GITHUB_EVENT_NAME", "manual"),
        "Timestamp (UTC)": now.isoformat(),
        "Language": "Python",
        "Python Version": os.environ.get("PYTHON_VERSION", "3.12"),
        "Go Version": "1.22 (comparison service)",
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
    table {{ width: 100%; max-width: 600px; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.08); }}
    th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e9ecef; }}
    th {{ background: #e9ecef; width: 40%; }}
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
    <div class="card">
      <div>Total Tests</div>
      <div class="metric">{results['tests']}</div>
    </div>
    <div class="card">
      <div>Passed</div>
      <div class="metric" style="color: var(--ok)">{passed}</div>
    </div>
    <div class="card">
      <div>Failed</div>
      <div class="metric" style="color: var(--fail)">{results['failures'] + results['errors']}</div>
    </div>
    <div class="card">
      <div>Skipped</div>
      <div class="metric">{results['skipped']}</div>
    </div>
    <div class="card">
      <div>Duration</div>
      <div class="metric">{results['time']:.2f}s</div>
    </div>
  </div>

  <h2>Run Metadata</h2>
  <table>
    {rows}
  </table>

  {f'<a href="{report_file}">View detailed pytest report</a>' if report_file else '<p>Detailed pytest report not available.</p>'}

  <footer>
    <p><small>Generated on {metadata["Timestamp (UTC)"]} by scripts/generate_dashboard.py</small></p>
  </footer>
</body>
</html>"""

    (DASHBOARD_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Dashboard generated at {DASHBOARD_DIR / 'index.html'}")


if __name__ == "__main__":
    build_dashboard()
