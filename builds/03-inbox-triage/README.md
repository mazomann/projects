# 03 · Inbox triage: Gmail → classify, label, draft, escalate, daily digest

Every new email is classified into support, sales, billing, spam, or needs-human. Support and sales get a reply drafted into Gmail Drafts for a person to approve and send. Billing is labelled and left alone. Spam is labelled and marked read. Anything angry, legal, sensitive, or uncertain pings Slack immediately. At 5 pm a digest lists what still needs a human.

```
Gmail unread ─▶ normalise ─▶ Claude (category, confidence, summary, urgency, draft) ─▶ policy ─▶ label
                                                                                                 ├─ support/sales ─▶ Gmail draft (human sends)
                                                                                                 ├─ needs_human ──▶ Slack alert
                                                                                                 ├─ spam ─────────▶ mark read
                                                                                                 └─ billing ──────▶ label only
Schedule 17:00 ─▶ today's labelled mail ─▶ digest ─▶ Slack
```

The AI never sends anything. It drafts, labels, and summarises; a human clicks send.

| | n8n workflow (`workflow.json`) | Python (`triage/`) |
|---|---|---|
| Input | Gmail trigger, polling unread | JSON list of emails (`sample-data/inbox.json`) |
| Policy layer | `Apply policy` Code node | `triage_email()` |
| Digest | from labels, no second model call | `digest()` over decisions |
| Tests | run against a test Gmail account | `uv run pytest` (10 tests, fake model) |

## Python

```bash
uv sync && uv run pytest
export ANTHROPIC_API_KEY=sk-ant-...
BUSINESS_CONTEXT="Family law firm in Fort Myers, ..." uv run python -m triage.triage sample-data/inbox.json
```

## n8n

1. In Gmail create five labels (for example `triage/support`, `triage/sales`, `triage/billing`, `triage/spam`, `triage/needs-human`) and note their ids (Gmail API label ids look like `Label_123456`; the n8n Gmail node's label dropdown shows them).
2. Import `workflow.json`. Credentials: Gmail OAuth2, Anthropic, Slack.
3. Env: `TRIAGE_LABEL_SUPPORT`, `TRIAGE_LABEL_SALES`, `TRIAGE_LABEL_BILLING`, `TRIAGE_LABEL_SPAM`, `TRIAGE_LABEL_NEEDS_HUMAN` (label ids), `TRIAGE_SLACK_CHANNEL`, `BUSINESS_CONTEXT` (one paragraph: who you are, hours, what must always go to a human), `TRIAGE_MODEL`.
4. Activate. Outlook variant: swap the Gmail trigger and nodes for the Microsoft Outlook trigger and nodes; the Code nodes are unchanged.

## Design notes

- **Two safety layers.** The schema forces one of five categories and a confidence. The policy code then strips drafts from anything that is not support or sales and escalates anything under 0.7 confidence, so even a confused model cannot draft a refund promise.
- **The business context is data, not prompt engineering.** One paragraph in an env var is what a client edits; the prompt itself does not change per client.
- **The digest costs nothing.** It reads the labels the live flow already applied, so there is no second pass over the day's mail.
- **Cost:** about 600 input tokens and 200 output per email; roughly $0.003 on Claude Sonnet 5, so a 200-email day is under a dollar.

## What I learned

- Gmail's trigger payload differs between "simple" and full modes; normalising into one small `email` object up front keeps every later node identical.
- A Switch node with named outputs is much easier to read than chained If nodes when there are four destinations.
