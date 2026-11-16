#!/usr/bin/env python3
"""modelsunset: find LLM model IDs in your code that are retired or about to be.

    modelsunset scan [PATH ...] [--fail-within DAYS] [--registry URL_OR_FILE] [--json]

Exit status is 1 when a referenced model is already retired, or retires within
--fail-within days. Single file, standard library only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request

DEFAULT_REGISTRY = os.environ.get("MODELSUNSET_REGISTRY", "https://modelsunset.dev/api/v1/models.json")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next",
             "target", "vendor", ".tox", ".mypy_cache"}
MAX_BYTES = 1_000_000


def load_registry(src: str) -> list[dict]:
    if re.match(r"^https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "modelsunset-cli"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    else:
        with open(src, encoding="utf-8") as f:
            data = json.load(f)
    return data["models"]


def matcher(models: list[dict]) -> re.Pattern:
    ids = sorted({m["id"] for m in models}, key=len, reverse=True)
    alt = "|".join(re.escape(i) for i in ids)
    # An ID must stand alone: "claude-opus-5" must not match inside "claude-opus-5-5".
    return re.compile(rf"(?<![A-Za-z0-9_-])({alt})(?![A-Za-z0-9_-])(?!\.[A-Za-z0-9])")


def classify(m: dict, today: dt.date) -> tuple[str, int | None]:
    if m.get("retires"):
        left = (dt.date.fromisoformat(m["retires"]) - today).days
        return ("retired" if left <= 0 else "retiring"), left
    return ("deprecated" if m.get("state") == "deprecated" else "active"), None


def iter_files(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                yield os.path.join(root, name)


def scan(paths, models, today=None) -> list[dict]:
    today = today or dt.date.today()
    by_id: dict[str, list[dict]] = {}
    for m in models:
        by_id.setdefault(m["id"], []).append(m)
    pat = matcher(models)
    hits = []
    for path in iter_files(paths):
        try:
            if os.path.getsize(path) > MAX_BYTES:
                continue
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        for n, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            for found in pat.finditer(line):
                for m in by_id[found.group(1)]:
                    status, left = classify(m, today)
                    hits.append({"file": path, "line": n, "provider": m["provider"],
                                 "id": m["id"], "status": status, "retires": m.get("retires"),
                                 "days_left": left, "replacement": m.get("replacement")})
    return hits


def failing(hit: dict, fail_within: int) -> bool:
    return hit["status"] == "retired" or (
        hit["status"] == "retiring" and hit["days_left"] <= fail_within)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modelsunset", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan", help="scan files for retired or retiring model IDs")
    sc.add_argument("paths", nargs="*", default=["."])
    sc.add_argument("--fail-within", type=int, default=0, metavar="DAYS",
                    help="also fail for models retiring within DAYS (default: only retired)")
    sc.add_argument("--registry", default=DEFAULT_REGISTRY, help="URL or file of models.json")
    sc.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    try:
        models = load_registry(args.registry)
    except Exception as exc:  # network or parse failure must not look like a clean scan
        print(f"modelsunset: cannot load registry {args.registry}: {exc}", file=sys.stderr)
        return 2
    hits = scan(args.paths, models)
    bad = [h for h in hits if failing(h, args.fail_within)]
    if args.json:
        print(json.dumps({"hits": hits, "failing": len(bad)}, indent=1))
        return 1 if bad else 0
    shown = [h for h in hits if h["status"] != "active"]
    for h in shown:
        if h["status"] == "retired":
            what = f"RETIRED on {h['retires']}"
        elif h["status"] == "retiring":
            what = f"retires {h['retires']} ({h['days_left']} days)"
        else:
            what = "deprecated, no retirement date yet"
        rep = f" -> {h['replacement']}" if h["replacement"] else ""
        mark = "FAIL" if failing(h, args.fail_within) else "warn"
        print(f"{mark}  {h['file']}:{h['line']}  {h['provider']}/{h['id']}  {what}{rep}")
    print(f"{len(hits)} model reference(s), {len(shown)} deprecated or retiring, {len(bad)} failing.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
