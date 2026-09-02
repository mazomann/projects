"""Print per-node results of recent headless n8n executions straight from SQLite.

Usage: python n8n/inspect_execution.py [N=1]   (N most recent executions)
Handy because `n8n execute` on 2.36 sometimes reports "No active execution found" even when the run was saved.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

DB = Path(__file__).resolve().parent / "data" / ".n8n" / "database.sqlite"
PREVIEW_NODES = {
    "Apply policy",
    "Build digest",
    "HTML -> text + request",
    "Validate + flatten",
    "Build run summary",
    "Guard: has text?",
}


def show(db: sqlite3.Connection, eid: int) -> None:
    status, wid = db.execute("select status, workflowId from execution_entity where id=?", (eid,)).fetchone()
    flat = json.loads(db.execute("select data from execution_data where executionId=?", (eid,)).fetchone()[0])

    def walk(x: Any) -> Any:
        while isinstance(x, str) and x.isdigit():  # n8n stores every value as an index into one flat list
            x = flat[int(x)]
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x

    print(f"== execution {eid} {wid} {status}")
    for node, runs in walk(flat[0])["resultData"]["runData"].items():
        r = runs[0]
        outs = (r.get("data") or {}).get("main") or [[]]
        err = r.get("error")
        line = f"  {node!r}: {r.get('executionStatus')} items_out={[len(o or []) for o in outs]}"
        if err:
            line += f" error={str(err.get('message', ''))[:160]}"
        print(line)
        if node in PREVIEW_NODES:
            for it in (outs[0] or [])[:8]:
                j = it.get("json", {})
                if "text" in j and isinstance(j["text"], str) and "\n" in j["text"] and len(j) <= 3:
                    print("\n".join("      " + text_line for text_line in j["text"].splitlines()))
                else:
                    keep = {
                        k: (v if not isinstance(v, (dict, list)) else "...")
                        for k, v in j.items()
                        if k not in ("request", "text", "page")
                    }
                    print("      " + json.dumps(keep, ensure_ascii=False)[:220])


def report(n: int) -> None:
    """Print the N most recent executions, oldest first. Shared with headless_run.py."""
    db = sqlite3.connect(DB)
    ids = [r[0] for r in db.execute("select id from execution_entity order by id desc limit ?", (n,))]
    for eid in sorted(ids):
        show(db, eid)


if __name__ == "__main__":
    report(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
