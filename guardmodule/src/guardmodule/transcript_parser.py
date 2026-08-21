"""Parses a Claude Code transcript (JSONL) and extracts the block types the
Module cares about.

Per spec section 5.5 / 5.6: `thinking` blocks are always empty in Claude Code
transcripts (0 of 4083 blocks measured carried text), so this parser does not
bother surfacing them. What matters is `text` blocks (the agent's visible,
stated plan/prose) and `tool_use` blocks (what it actually did).

Input can be either:
  - `transcript_tail` bytes (a suffix of the file, possibly starting mid-line
    if `transcript_tail_truncated` is true — the first line is dropped if it
    fails to parse as JSON), or
  - a `transcript_path` to read from disk.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ParsedTranscript:
    text_blocks: list[str] = field(default_factory=list)
    tool_use_blocks: list[dict] = field(default_factory=list)
    unparsed_line_count: int = 0

    def all_text(self) -> list[str]:
        """Every text_block, plus a stringified form of each tool_use block so
        rules can also match on tool names/arguments recorded in the transcript."""
        texts = list(self.text_blocks)
        for tu in self.tool_use_blocks:
            texts.append(json.dumps(tu, ensure_ascii=False))
        return texts


def _iter_content_blocks(raw_lines: list[str]):
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            yield None
            continue
        message = record.get("message") if isinstance(record, dict) else None
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict):
                yield block


def _parse_lines(lines: list[str]) -> ParsedTranscript:
    parsed = ParsedTranscript()
    for block in _iter_content_blocks(lines):
        if block is None:
            parsed.unparsed_line_count += 1
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text", "")
            if text:
                parsed.text_blocks.append(text)
        elif block_type == "tool_use":
            parsed.tool_use_blocks.append(
                {"name": block.get("name", ""), "input": block.get("input", {})}
            )
        # "thinking" blocks are intentionally ignored — see module docstring.
    return parsed


def parse_transcript_text(raw_text: str) -> ParsedTranscript:
    return _parse_lines(raw_text.split("\n"))


def parse_transcript_tail(tail_bytes: bytes, truncated: bool) -> ParsedTranscript:
    """Parse transcript_tail bytes. When truncated, the first line may be a
    partial JSON fragment and is safely skipped if it fails to parse."""
    raw_text = tail_bytes.decode("utf-8", errors="replace")
    lines = raw_text.split("\n")

    if truncated and lines:
        # The first line is likely a cut-off fragment of an earlier record; verify
        # it actually fails to parse before dropping it, so we never discard real data.
        first = lines[0].strip()
        if first:
            try:
                json.loads(first)
            except (json.JSONDecodeError, ValueError):
                lines = lines[1:]

    return _parse_lines(lines)


def parse_transcript_file(path: str) -> ParsedTranscript:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return parse_transcript_text(fh.read())

