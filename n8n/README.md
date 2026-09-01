# Local n8n

n8n runs from npm (no Docker): `npm install -g n8n`. Data lives in `n8n/data/` (gitignored).

## Start

```bash
export N8N_USER_FOLDER=C:/Automations/n8n/data
export N8N_ENCRYPTION_KEY=<long random string, keep it stable>
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false          # lets Code nodes read $env.* (the builds use it for config)
export N8N_RESTRICT_FILE_ACCESS_TO=C:/Automations/builds   # folders the Read/Write Files node may touch
n8n start          # http://localhost:5678
```

## Import a build and its credentials without the UI

```bash
cp n8n/credentials.example.json n8n/credentials.json   # fill in real keys; this file is gitignored
n8n import:credentials --input=n8n/credentials.json
n8n import:workflow --input=builds/01-invoice-extractor/workflow.json
```

Workflows reference credentials by the `id` in `credentials.json` (`anthropic-local`, `google-sheets-local`, `slack-local`, `hubspot-local`), so the import wires them up. OAuth credentials (Google, Slack) still need the one-time browser consent in the UI.

## Headless run

`n8n execute --id=<workflow id>` runs a workflow without the UI. On n8n 2.36 the CLI sometimes reports "No active execution found" even though the run completed; the result is still stored and can be read from `n8n/data/.n8n/database.sqlite` (`execution_entity`, `execution_data`).
