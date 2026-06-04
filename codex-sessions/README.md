# Codex Session Exports

Open `index.html` in this directory to review the Codex sessions for this repository.

Each HTML file is generated from the local Codex JSONL session log whose recorded working directory is this
repo. The exporter filters system/developer messages and presents user, assistant, command, and patch events in
chronological order.

To regenerate after more Codex work:

```bash
python codex-sessions/export_codex_sessions.py
```
