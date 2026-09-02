"""Run an n8n workflow headlessly with fake or no-op nodes, then print every node's result.

Usage:
  python n8n/headless_run.py builds/01-invoice-extractor/workflow.json
  python n8n/headless_run.py WORKFLOW --noop "Append row to Google Sheet,Post summary to Slack" \
      --fake "Claude: extract fields=fakes/claude.json" \
      --env INVOICE_INBOX=/c/Automations/builds/01-invoice-extractor/sample-data

--noop  comma-separated node names replaced with NoOp (external writes: Sheets, Slack, HubSpot, Gmail)
--fake  NODE=FILE, repeatable. FILE holds a JSON array of item json objects; the node becomes a
        Code node returning them.
        Use it for the LLM call: put one fake API response per input item.
--trigger-to-manual  replace the first trigger node with a Manual trigger
        (Gmail/Schedule triggers cannot run headlessly)
--env   KEY=VALUE, repeatable, passed to n8n (also sets the switches n8n needs: env access, file access)

The real workflow file is never modified. A copy with id "<id>-headless" is imported and executed.
Requires: n8n on PATH (npm install -g n8n), N8N_ENCRYPTION_KEY consistent with n8n/data.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from inspect_execution import report

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
USER_FOLDER = HERE / "data"


def retype(node: dict[str, Any], kind: str, version: int, parameters: dict[str, Any]) -> None:
    """Turn a node into a plain built-in node of another type, dropping anything that needs the outside world."""
    node.update(type=f"n8n-nodes-base.{kind}", typeVersion=version, parameters=parameters)
    node.pop("credentials", None)
    node.pop("onError", None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow")
    ap.add_argument("--noop", default="")
    ap.add_argument("--fake", action="append", default=[])
    ap.add_argument("--trigger-to-manual", action="store_true")
    ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args()

    w = json.loads(Path(a.workflow).read_text(encoding="utf-8"))
    by = {n["name"]: n for n in w["nodes"]}
    for name in [s.strip() for s in a.noop.split(",") if s.strip()]:
        retype(by[name], "noOp", 1, {})
    for spec in a.fake:
        name, _, file = spec.partition("=")
        items = json.loads(Path(file).read_text(encoding="utf-8"))
        code = f"const fake = {json.dumps(items)};\nreturn fake.map(j => ({{ json: j }}));"
        retype(by[name.strip()], "code", 2, {"jsCode": code})
    if a.trigger_to_manual:
        retype(next(n for n in w["nodes"] if "trigger" in n["type"].lower()), "manualTrigger", 1, {})
    w["id"] = f"{w.get('id', 'wf')}-headless"
    w["name"] = f"{w.get('name', 'workflow')} [headless]"
    w["pinData"] = {}

    tmp = Path(tempfile.gettempdir()) / f"{w['id']}.json"
    tmp.write_text(json.dumps(w, indent=1), encoding="utf-8")

    env = dict(os.environ)
    env.setdefault("N8N_USER_FOLDER", str(USER_FOLDER))
    env.setdefault("N8N_ENCRYPTION_KEY", "local-dev-only-key-0123456789")
    env["N8N_BLOCK_ENV_ACCESS_IN_NODE"] = "false"
    env["N8N_RESTRICT_FILE_ACCESS_TO"] = str(ROOT / "builds")
    for kv in a.env:
        k, _, v = kv.partition("=")
        env[k] = v

    def n8n(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["n8n", *args], env=env, capture_output=True, text=True, shell=(os.name == "nt"))

    imp = n8n("import:workflow", f"--input={tmp}")
    if "Successfully imported" not in imp.stdout + imp.stderr:
        print(imp.stdout[-800:], imp.stderr[-800:], file=sys.stderr)
        return 1
    run = n8n("execute", f"--id={w['id']}")
    ok = "Execution was successful" in run.stdout + run.stderr
    print(f"headless run of {w['id']}: {'succeeded' if ok else 'finished with errors (or CLI race; see nodes below)'}")
    report(1)
    tmp.unlink(missing_ok=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
