#!/usr/bin/env python3
"""Export Codex JSONL sessions for this repository to readable HTML."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSIONS_ROOT = Path.home() / ".codex" / "sessions"
OUTPUT_DIR = REPO_ROOT / "codex-sessions"
DETAIL_TEXT_LIMIT = 12_000


@dataclass(frozen=True)
class Session:
    source: Path
    session_id: str
    started_at: str
    cwd: str
    git_commit: str | None
    branch: str | None
    repository_url: str | None
    events: list[dict[str, Any]]


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def discover_sessions() -> list[Session]:
    sessions: list[Session] = []
    repo_cwd = str(REPO_ROOT)
    for source in sorted(SESSIONS_ROOT.rglob("*.jsonl")):
        records = read_jsonl(source)
        meta = next((r for r in records if r.get("type") == "session_meta"), None)
        payload = (meta or {}).get("payload", {})
        if payload.get("cwd") != repo_cwd:
            continue

        git = payload.get("git") or {}
        sessions.append(
            Session(
                source=source,
                session_id=payload.get("id", source.stem),
                started_at=payload.get("timestamp") or records[0].get("timestamp", ""),
                cwd=payload.get("cwd", ""),
                git_commit=git.get("commit_hash"),
                branch=git.get("branch"),
                repository_url=git.get("repository_url"),
                events=records,
            )
        )
    return sorted(sessions, key=lambda session: parse_timestamp(session.started_at))


def visible_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {"input_text", "output_text"}:
            parts.append(str(item.get("text", "")))
    return "\n\n".join(part for part in parts if part)


def format_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    return json.dumps(value, indent=2, ensure_ascii=False)


def limit_detail_text(text: str) -> str:
    if len(text) <= DETAIL_TEXT_LIMIT:
        return text
    omitted = len(text) - DETAIL_TEXT_LIMIT
    return f"{text[:DETAIL_TEXT_LIMIT]}\n\n[truncated {omitted} characters from this tool detail]"


def event_blocks(session: Session) -> list[str]:
    blocks: list[str] = []

    for record in session.events:
        timestamp = html.escape(record.get("timestamp", ""))
        record_type = record.get("type")
        payload = record.get("payload", {})

        if record_type == "response_item" and payload.get("type") == "message":
            role = payload.get("role")
            if role in {"system", "developer"}:
                continue
            text = visible_text_from_content(payload.get("content"))
            if not text:
                continue
            label = "User" if role == "user" else "Assistant"
            blocks.append(block(label, timestamp, role or "message", html.escape(text)))

        elif record_type == "response_item" and payload.get("type") in {
            "function_call",
            "custom_tool_call",
        }:
            name = payload.get("name") or payload.get("call_id") or payload.get("type")
            args = payload.get("arguments") or payload.get("input") or ""
            text = html.escape(limit_detail_text(format_json(args)))
            blocks.append(details_block(f"Tool Call: {name}", timestamp, "tool-call", text))

        elif record_type == "response_item" and payload.get("type") in {
            "function_call_output",
            "custom_tool_call_output",
        }:
            output = payload.get("output", "")
            text = html.escape(limit_detail_text(format_json(output)))
            blocks.append(details_block("Tool Output", timestamp, "tool-output", text))

        elif record_type == "event_msg" and payload.get("type") in {
            "task_started",
            "task_complete",
            "item_completed",
            "turn_aborted",
            "patch_apply_end",
        }:
            label = payload.get("type", "event").replace("_", " ").title()
            text = html.escape(limit_detail_text(format_json(payload)))
            blocks.append(details_block(label, timestamp, "event", text))

    return blocks


def count_visible_messages(session: Session) -> int:
    count = 0
    for record in session.events:
        payload = record.get("payload", {})
        if record.get("type") != "response_item" or payload.get("type") != "message":
            continue
        if payload.get("role") in {"system", "developer"}:
            continue
        if visible_text_from_content(payload.get("content")):
            count += 1
    return count


def block(label: str, timestamp: str, css_class: str, text: str) -> str:
    return (
        f'<article class="event {css_class}">'
        f'<div class="meta"><strong>{html.escape(label)}</strong><span>{timestamp}</span></div>'
        f"<pre>{text}</pre>"
        "</article>"
    )


def details_block(label: str, timestamp: str, css_class: str, text: str) -> str:
    return (
        f'<details class="event {css_class}">'
        f'<summary><strong>{html.escape(label)}</strong><span>{timestamp}</span></summary>'
        f"<pre>{text}</pre>"
        "</details>"
    )


def render_session(session: Session) -> str:
    title = f"Codex Session {session.started_at[:10]} {session.session_id}"
    source = html.escape(str(session.source))
    commit = session.git_commit or "unknown"
    short_commit = commit[:12] if commit != "unknown" else commit
    body = "\n".join(event_blocks(session))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  {style()}
</head>
<body>
  <main>
    <nav><a href="index.html">Back to session index</a></nav>
    <header>
      <h1>{html.escape(title)}</h1>
      <dl>
        <dt>Session ID</dt><dd>{html.escape(session.session_id)}</dd>
        <dt>Started</dt><dd>{html.escape(session.started_at)}</dd>
        <dt>Working directory</dt><dd>{html.escape(session.cwd)}</dd>
        <dt>Git</dt><dd>{html.escape(session.branch or "unknown")} @ {html.escape(short_commit)}</dd>
        <dt>Repository</dt><dd>{html.escape(session.repository_url or "unknown")}</dd>
        <dt>Source log</dt><dd>{source}</dd>
      </dl>
    </header>
    <section>{body}</section>
  </main>
</body>
</html>
"""


def render_index(sessions: list[Session], filenames: dict[str, str]) -> str:
    rows = []
    for session in sessions:
        commit = session.git_commit or "unknown"
        block_count = len(event_blocks(session))
        message_count = count_visible_messages(session)
        rows.append(
            "<tr>"
            f'<td><a href="{html.escape(filenames[session.session_id])}">'
            f"{html.escape(session.started_at)}</a></td>"
            f"<td>{html.escape(session.session_id)}</td>"
            f"<td>{html.escape((session.branch or 'unknown') + ' @ ' + commit[:12])}</td>"
            f"<td>{message_count}</td>"
            f"<td>{block_count - message_count}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Session Exports</title>
  {style()}
</head>
<body>
  <main>
    <header>
      <h1>Codex Session Exports</h1>
      <p>HTML exports for Codex sessions whose working directory was {html.escape(str(REPO_ROOT))}.</p>
    </header>
    <table>
      <thead><tr><th>Started</th><th>Session ID</th><th>Git</th><th>Visible Messages</th><th>Collapsed Details</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </main>
</body>
</html>
"""


def style() -> str:
    return """<style>
  :root { color-scheme: light; }
  body { margin: 0; background: #f7f8fa; color: #1f2933; font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  main { max-width: 1120px; margin: 0 auto; padding: 32px 20px 64px; }
  a { color: #0969da; }
  header { margin-bottom: 24px; }
  h1 { margin: 0 0 12px; font-size: 28px; line-height: 1.2; }
  p { margin: 0 0 16px; color: #52606d; }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 16px 0 0; }
  dt { color: #52606d; font-weight: 600; }
  dd { margin: 0; overflow-wrap: anywhere; }
  table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e2ec; }
  th, td { padding: 10px 12px; border-bottom: 1px solid #e6ebf1; text-align: left; vertical-align: top; }
  th { background: #eef2f7; font-size: 13px; text-transform: uppercase; letter-spacing: .03em; color: #52606d; }
  .event { margin: 14px 0; border: 1px solid #d9e2ec; border-radius: 8px; background: #fff; overflow: hidden; }
  .event .meta, summary { display: flex; justify-content: space-between; gap: 16px; padding: 10px 12px; background: #eef2f7; color: #334e68; cursor: default; }
  summary { cursor: pointer; }
  .user .meta { background: #e7f0ff; }
  .assistant .meta { background: #e8f7ef; }
  .tool-call summary { background: #fff4d6; }
  .tool-output summary { background: #f2e9ff; }
  .event summary { background: #edf2f7; }
  pre { margin: 0; padding: 12px; white-space: pre-wrap; word-break: break-word; font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  nav { margin-bottom: 16px; }
</style>"""


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    sessions = discover_sessions()
    filenames: dict[str, str] = {}
    for index, session in enumerate(sessions, start=1):
        started = parse_timestamp(session.started_at).strftime("%Y-%m-%dT%H-%M-%SZ")
        filename = f"{index:02d}-{started}-{slugify(session.session_id)}.html"
        filenames[session.session_id] = filename
        (OUTPUT_DIR / filename).write_text(render_session(session), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(render_index(sessions, filenames), encoding="utf-8")
    print(f"Exported {len(sessions)} sessions to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
