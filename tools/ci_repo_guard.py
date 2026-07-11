#!/usr/bin/env python3
"""CI checks for repository hygiene and obvious secret leaks."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED_PATTERNS = [
    re.compile(r".*\.db$", re.IGNORECASE),
    re.compile(r".*\.sqlite$", re.IGNORECASE),
    re.compile(r".*\.sqlite3$", re.IGNORECASE),
    re.compile(r".*\.db-wal$", re.IGNORECASE),
    re.compile(r".*\.db-shm$", re.IGNORECASE),
    re.compile(r".*-wal$", re.IGNORECASE),
    re.compile(r".*-shm$", re.IGNORECASE),
    re.compile(r".*\.pyc$", re.IGNORECASE),
    re.compile(r".*\.pyo$", re.IGNORECASE),
    re.compile(r".*__pycache__/.*", re.IGNORECASE),
    re.compile(r".*tsconfig\.tsbuildinfo$", re.IGNORECASE),
]

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{20,})['\"]?"),
]

TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def tracked_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        raise SystemExit(f"Could not list tracked files with git: {exc}") from exc
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_hygiene(files: list[str]) -> int:
    failures: list[str] = []
    for filename in files:
        normalized = filename.replace("\\", "/")
        if normalized == ".env.example":
            continue
        if normalized.startswith(".env") or "/.env" in normalized:
            failures.append(filename)
            continue
        if any(pattern.fullmatch(normalized) for pattern in FORBIDDEN_TRACKED_PATTERNS):
            failures.append(filename)

    if not (ROOT / ".env.example").exists():
        failures.append(".env.example is required and must be versioned")

    if failures:
        print("Forbidden runtime/local files are tracked or required template is missing:", file=sys.stderr)
        for item in failures:
            print(f"  {item}", file=sys.stderr)
        return 1
    return 0


def is_text_candidate(path: Path) -> bool:
    if path.name == ".env.example":
        return True
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in {"Dockerfile", ".dockerignore", ".gitignore"}


def check_secrets(files: list[str]) -> int:
    failures: list[str] = []
    for filename in files:
        path = ROOT / filename
        if not path.is_file() or not is_text_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if "example" in filename.lower() and ("change-me" in line or "example" in line.lower()):
                continue
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                failures.append(f"{filename}:{index}")

    if failures:
        print("Potential secrets found in tracked files:", file=sys.stderr)
        for item in failures:
            print(f"  {item}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Repository hygiene and secret checks.")
    parser.add_argument("--hygiene", action="store_true", help="Check tracked runtime files.")
    parser.add_argument("--secrets", action="store_true", help="Run simple secret scan.")
    args = parser.parse_args()

    files = tracked_files()
    status = 0
    if args.hygiene or not args.secrets:
        status |= check_hygiene(files)
    if args.secrets or not args.hygiene:
        status |= check_secrets(files)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
