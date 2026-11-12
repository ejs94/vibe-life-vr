#!/usr/bin/env python3
"""Validate the canonical documentation set, links, and relative-path rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_ROOT = REPO_ROOT / "Documentation" / "vr"

REQUIRED = [
    DOC_ROOT / "README.md",
    DOC_ROOT / "STATUS.md",
    DOC_ROOT / "ROADMAP.md",
    DOC_ROOT / "GATES.md",
    DOC_ROOT / "TESTING.md",
    DOC_ROOT / "ASSETS.md",
    DOC_ROOT / "WEAPONS.md",
    DOC_ROOT / "UPSTREAM.md",
    DOC_ROOT / "DECISIONS.md",
    DOC_ROOT / "MODEL_BENCHMARKS.md",
    DOC_ROOT / "reference" / "MOD_COMPATIBILITY.md",
    DOC_ROOT / "reference" / "MODDER_GUIDE.md",
]

# Gate IDs are parsed dynamically from Documentation/vr/GATES.md.

ABSOLUTE_RE = re.compile(
    r"(?:^|[\s(])((?:/(?:home|Users|root|mnt|tmp|opt|var)/)|(?:[A-Za-z]:\\)|file://)"
)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SCRIPT_RE = re.compile(r"`([^`]*?(?:scripts/|\./scripts/)[^`]*?)`")
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
IGNORED_LINK_PREFIXES = ("http://", "https://", "mailto:", "#")


def markdown_files() -> list[Path]:
    files = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md"]
    files.extend(DOC_ROOT.rglob("*.md"))
    files.extend((REPO_ROOT / ".opencode").rglob("*.md"))
    return sorted({path for path in files if path.exists()})


def check_required(errors: list[str]) -> None:
    for path in REQUIRED:
        if not path.exists():
            errors.append(f"missing canonical document: {path.relative_to(REPO_ROOT)}")


def mask_code(text: str) -> str:
    """Blank fenced and inline code while preserving line numbers."""
    text = FENCE_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)
    return INLINE_CODE_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)


def check_absolute_paths(errors: list[str]) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in ABSOLUTE_RE.finditer(line):
                if "/sdcard/" in line:
                    continue
                errors.append(
                    f"absolute path in {path.relative_to(REPO_ROOT)}:{line_no}: {match.group(1)}"
                )


def check_links(errors: list[str]) -> None:
    for path in markdown_files():
        text = mask_code(path.read_text(encoding="utf-8", errors="replace"))
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target = match.group(1).strip()
                if target.startswith(IGNORED_LINK_PREFIXES):
                    continue
                if target.startswith("/"):
                    errors.append(
                        f"absolute markdown link in {path.relative_to(REPO_ROOT)}:{line_no}: {target}"
                    )
                    continue
                clean = target.split("#", 1)[0].split("?", 1)[0]
                if not clean or any(token in clean for token in ("<", ">", "{", "}", "*")):
                    continue
                resolved = (path.parent / clean).resolve()
                if not resolved.exists():
                    errors.append(
                        f"broken markdown link in {path.relative_to(REPO_ROOT)}:{line_no}: {target}"
                    )


def parse_gate_registry() -> dict[str, str]:
    gates = DOC_ROOT / "GATES.md"
    if not gates.exists():
        return {}
    registry: dict[str, str] = {}
    for line in gates.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\|\s*`([^`]+)`\s*\|\s*[^|]+\|\s*([A-Za-z]+)\s*\|", line)
        if match:
            registry[match.group(1)] = match.group(2).lower()
    return registry


def check_gates(errors: list[str]) -> None:
    registry = parse_gate_registry()
    if not registry:
        errors.append("GATES.md registry is empty or missing")
        return
    gate_like = re.compile(r"`([A-Z]{1,2}\d+[a-z]?)`")
    for path in markdown_files():
        if path == DOC_ROOT / "GATES.md":
            continue
        if "reference" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in gate_like.finditer(line):
                gate_id = match.group(1)
                if gate_id in ("S0", "S1", "S2", "S3", "S4", "S5", "H0", "H1",
                               "H2", "H3", "H4", "H4a", "H4b", "H5", "H6",
                               "IK1", "IK2", "W2", "W4"):
                    continue
                if gate_id not in registry:
                    errors.append(
                        f"unknown gate id in {path.relative_to(REPO_ROOT)}:{line_no}: `{gate_id}`"
                    )
                    continue
                if registry[gate_id] == "retired" and "retired" not in line.lower():
                    errors.append(
                        f"retired gate cited as live in {path.relative_to(REPO_ROOT)}:{line_no}: `{gate_id}`"
                    )


def check_commands(errors: list[str]) -> None:
    gates = DOC_ROOT / "GATES.md"
    if not gates.exists():
        return
    text = gates.read_text(encoding="utf-8", errors="replace")
    for match in SCRIPT_RE.finditer(text):
        command = match.group(1).strip()
        for token in command.split():
            token = token.strip("'\"")
            if not token.startswith(("scripts/", "./scripts/")):
                continue
            token = token.removeprefix("./")
            candidate = (REPO_ROOT / token).resolve()
            if not candidate.exists():
                errors.append(f"GATES.md references a missing command path: {token}")


def check_status(errors: list[str]) -> None:
    status = DOC_ROOT / "STATUS.md"
    if not status.exists():
        return
    text = status.read_text(encoding="utf-8", errors="replace")
    if "out/qa" not in text:
        errors.append("STATUS.md must point at the out/qa evidence root")
    if "STATUS" not in text and "Last updated" not in text:
        errors.append("STATUS.md is missing its update marker")


def main() -> int:
    errors: list[str] = []
    check_required(errors)
    check_absolute_paths(errors)
    check_links(errors)
    check_gates(errors)
    check_commands(errors)
    check_status(errors)

    if errors:
        print("DOCUMENTATION GATE FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"DOCUMENTATION GATE PASSED ({len(markdown_files())} markdown files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
