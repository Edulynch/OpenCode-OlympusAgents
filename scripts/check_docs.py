#!/usr/bin/env python3
"""Check repository-owned Markdown links and the compact docs index."""

from __future__ import annotations

import re
import os
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)")
HTML_ID = re.compile(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
INLINE_CODE = re.compile(r"`+([^`]+)`+")
MARKDOWN_LINK = re.compile(r"!?(?:\[[^\]]*\])\([^)]*\)")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def markdown_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        raise RuntimeError("Git could not enumerate repository Markdown.") from None
    if result.returncode != 0:
        raise RuntimeError("Git could not enumerate repository Markdown.")

    roots = {"docs", "specs", "tests", "olympus", ".specify"}
    excluded_fixtures = {
        ("tests", "codex", "fixtures"),
        ("tests", "phase11-integrated-routing", "fixtures"),
    }
    files: set[Path] = set()
    for raw_name in result.stdout.split(b"\0"):
        if not raw_name:
            continue
        relative = Path(os.fsdecode(raw_name))
        if relative.suffix.lower() != ".md" or not relative.is_file():
            continue
        parts = relative.parts
        if len(parts) == 1 or parts[0] in roots:
            if any(parts[: len(prefix)] == prefix for prefix in excluded_fixtures):
                continue  # Synthetic Markdown fixtures can intentionally name absent paths.
            files.add((ROOT / relative).resolve())
    return sorted(files)


def _heading_text(raw: str) -> str:
    text = INLINE_CODE.sub(r"\1", raw)
    text = MARKDOWN_LINK.sub("", text)
    text = text.replace("&", "")
    text = "".join(ch for ch in text if ch == "-" or ch.isspace() or ch == "_" or unicodedata.category(ch)[0] in "LN")
    return re.sub(r"\s+", "-", text.strip()).lower()


def anchors(path: Path) -> set[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return set()
    result = set(HTML_ID.findall(content))
    counts: dict[str, int] = {}
    for line in content.splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        anchor = _heading_text(match.group(1))
        if not anchor:
            continue
        duplicate = counts.get(anchor, 0)
        counts[anchor] = duplicate + 1
        result.add(anchor if duplicate == 0 else f"{anchor}-{duplicate}")
    return result


def local_target(source: Path, raw_target: str) -> tuple[Path, str] | None:
    target = raw_target[1:-1] if raw_target.startswith("<") and raw_target.endswith(">") else raw_target
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    decoded_path = unquote(parts.path)
    destination = (source.parent / decoded_path).resolve() if decoded_path else source.resolve()
    fragment = unquote(parts.fragment)
    return destination, fragment


def check_links(files: list[Path]) -> list[str]:
    failures: list[str] = []
    cache: dict[Path, set[str]] = {}
    for source in files:
        try:
            lines = source.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            failures.append(f"{source.relative_to(ROOT).as_posix()}: unreadable Markdown")
            continue
        for line_number, line in enumerate(lines, start=1):
            for match in LINK.finditer(line):
                found = local_target(source, match.group(1))
                if found is None:
                    continue
                destination, fragment = found
                label = f"{source.relative_to(ROOT).as_posix()}:{line_number}"
                if not destination.exists():
                    failures.append(f"{label}: missing local link target")
                    continue
                if destination.is_dir():
                    if not fragment:
                        continue
                    destination = destination / "README.md"
                    if not destination.exists():
                        failures.append(f"{label}: directory link has no README anchor target")
                        continue
                if fragment and destination.suffix.lower() == ".md" and not re.fullmatch(r"L\d+", fragment):
                    if destination not in cache:
                        cache[destination] = anchors(destination)
                    if fragment not in cache[destination]:
                        failures.append(f"{label}: missing local heading anchor")
    return failures


def check_index(files: list[Path]) -> list[str]:
    index = ROOT / "docs" / "README.md"
    if not index.is_file():
        return ["docs/README.md: missing documentation index"]
    indexed: set[Path] = set()
    try:
        lines = index.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return ["docs/README.md: unreadable documentation index"]
    for line in lines:
        for match in LINK.finditer(line):
            found = local_target(index, match.group(1))
            if found is not None:
                indexed.add(found[0])
    expected = {path.resolve() for path in files if path != index and path.is_relative_to(ROOT / "docs")}
    missing = sorted(path.relative_to(ROOT).as_posix() for path in expected - indexed)
    if missing:
        return [f"docs/README.md: unindexed document {path}" for path in missing]
    return []


def main() -> int:
    try:
        files = markdown_files()
    except RuntimeError as error:
        print(f"[docs] ERROR: {error}", file=sys.stderr)
        return 2
    failures = check_links(files) + check_index(files)
    if failures:
        for failure in failures:
            print(f"[docs] FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"[docs] PASS: local links and anchors checked in {len(files)} authored Markdown files; docs index covers all documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
