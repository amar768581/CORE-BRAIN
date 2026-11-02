"""CORE-BRAIN CEO master runner: executes the agency pipeline and reports CSV rows."""

import csv
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCRIPTS = ("revenue_engine.py", "head_of_engineering.py", "delivery_pods.py")
CSV_FILES = ("revenue_leads.csv", "seo_results.csv", "engineering_logs.csv", "pod_deliveries.csv")


def run_step(script: str) -> bool:
    try:
        subprocess.run([sys.executable, str(BASE / script)], check=True, cwd=BASE)
        return True
    except Exception as exc:  # no step may crash the pipeline
        print(f"  [FAIL] {script}: {exc}")
        return False


def row_counts() -> None:
    print("\nCSV row counts:")
    total = 0
    for name in CSV_FILES:
        try:
            with (BASE / name).open(newline="", encoding="utf-8") as fh:
                rows = max(sum(1 for _ in csv.reader(fh)) - 1, 0)
            total += rows
            print(f"  {name}: {rows} rows")
        except OSError:
            print(f"  {name}: missing")
    print(f"  total: {total} rows")


def main() -> int:
    print("CEO Master Runner - agency pipeline", flush=True)
    ok = all([run_step(script) for script in SCRIPTS])  # list runs every step
    row_counts()
    if "--serve" in sys.argv:
        print("launching dashboard on port 5000 ...")
        try:
            subprocess.run([sys.executable, str(BASE / "app.py")], cwd=BASE)
        except Exception as exc:
            print(f"  [FAIL] app.py: {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
