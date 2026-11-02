"""CORE-BRAIN dashboard: dark glassmorphism UI on port 5000 (Flask, else stdlib)."""

import csv
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
PORT = 5000
CSV_FILES = ("revenue_leads.csv", "seo_results.csv", "engineering_logs.csv", "pod_deliveries.csv")
DIVISIONS = ("REVENUE ENGINE", "HEAD OF ENGINEERING", "DELIVERY PODS 1-3")

CSS = """
body{margin:0;color:#e8f0ff;font-family:system-ui,sans-serif;min-height:100vh;
background:radial-gradient(circle at 20% 0%,#1b2a4a,#0b1020 65%);}
.node,.card,.panel{background:rgba(255,255,255,.06);backdrop-filter:blur(14px);
border:1px solid rgba(255,255,255,.14);border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.4);}
.node{margin:24px auto;padding:18px;width:min(560px,92%);text-align:center;font-size:20px;font-weight:700;}
.cards{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;padding:0 24px;}
.card{flex:1 1 240px;padding:16px;text-align:center;font-weight:600;}
.panel{margin:20px 24px;padding:14px;overflow-x:auto;}
.live{color:#39ff14;text-shadow:0 0 8px #39ff14;}
table{border-collapse:collapse;width:100%;font-size:13px;}
th,td{border-bottom:1px solid rgba(255,255,255,.12);padding:6px 10px;text-align:left;}
th{color:#8fd0ff;text-transform:uppercase;}
"""


def _table(name: str) -> str:
    """Render one CSV as a glass panel table (all rows, read live per request)."""
    path = BASE / name
    if not path.is_file():
        return f'<div class="panel"><h2>{name}</h2><p>file missing</p></div>'
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    head, body = (rows[0], rows[1:]) if rows else ([], [])
    th = "".join(f"<th>{html.escape(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in body)
    return (f'<div class="panel"><h2>{name} &middot; {len(body)} rows</h2>'
            f"<table><tr>{th}</tr>{trs}</table></div>")


def render() -> str:
    cards = "".join(
        f'<div class="card">{d} <span class="live">[LIVE / ACTIVE]</span></div>' for d in DIVISIONS
    )
    tables = "".join(_table(name) for name in CSV_FILES)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>CORE-BRAIN</title>
<style>{CSS}</style></head><body>
<div class="node">CEO <small>(Founder &amp; Master Orchestrator)</small>
<span class="live">[ONLINE]</span></div>
<div class="cards">{cards}</div>{tables}</body></html>"""


def _serve_stdlib() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = render().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


def main() -> None:
    try:
        from flask import Flask
    except ImportError:
        print(f"stdlib http.server on port {PORT}")
        return _serve_stdlib()
    app = Flask(__name__)
    app.add_url_rule("/", "index", lambda: render())
    print(f"Flask on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
