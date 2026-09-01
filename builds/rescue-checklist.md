# Workflow rescue checklist

For "my n8n / Zapier / Make automation stopped working" gigs. Work top to bottom; most fixes are in the first three sections. Every item here bit me while building this portfolio, not in theory.

## 1. Reproduce before touching anything
- Get read access first, edit access only after the diagnosis is written down.
- Open the last failed execution. Note the failing node, the error text, and the timestamp of the last success.
- Ask: what changed around that time? New credential, plan downgrade, renamed sheet tab or column, a vendor API version bump, someone "tidied" a node.
- Export the workflow JSON before editing (n8n: Download; Make: export blueprint; Zapier: copy the Zap). That is the rollback.

## 2. Credentials and access (half of all breakages)
- Expired OAuth token: reconnect the credential, then re-run the failed execution.
- API key rotated or revoked: the error is usually a 401 "API key is invalid" from the vendor, not from the automation tool.
- The node is pointed at a credential the workflow owner cannot see ("does not have access to the credential"): re-select it as that user.
- Scope changes: Google, Slack, and HubSpot all add scopes over time; a re-consent fixes "insufficient permissions".

## 3. Environment and hosting (self-hosted n8n)
- `$env` reads fail with "access to env vars denied" unless `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`.
- File nodes fail with "Access to the file is not allowed" unless the folder is in `N8N_RESTRICT_FILE_ACCESS_TO`.
- Upgraded n8n: check the changelog for node version bumps; an old `typeVersion` still runs, but new parameters may be required.
- Encryption key changed: every stored credential becomes unreadable. Restore the key, do not re-enter secrets one by one.

## 4. Data shape drift
- Sheet or CRM column renamed: auto-mapped nodes silently write nothing; explicit mappings error. Compare the column list against the last good execution's input.
- Empty input: a trigger returning zero items makes downstream nodes "succeed" with no output. Check the item counts per node, not just the green ticks.
- Item pairing: in a Code node running once for all items, `$('Node').item` is not positional; use `.all()[i]` or the failure shows up as every row carrying the first row's data.
- Expression cut short: n8n ends an expression at the first `}}`, so object literals inside `{{ }}` silently break. Build the object in a Code node and pass it through.

## 5. LLM steps
- Provider error 400 after a model deprecation: pin a current model id and remove retired parameters.
- Output no longer parses: the prompt was relying on luck. Switch to a JSON-schema constrained output and validate before writing anywhere.
- Costs jumped: look for a loop feeding whole documents in instead of the relevant slice, or a retry storm on a failing node.
- Rate limits: add batching (n8n HTTP node batching options) and a sane retry with backoff instead of "retry on fail" with zero wait.

## 6. Hand back properly
- One paragraph: what broke, why, what changed, how to tell if it recurs.
- Leave a test execution in the history that shows the fixed path working end to end.
- Suggest one monitoring improvement (error workflow that posts to Slack, or an execution-count alert) as the follow-up offer.
