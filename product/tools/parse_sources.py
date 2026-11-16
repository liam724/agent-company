#!/usr/bin/env python3
"""Turn a saved official deprecation page into rows for `sunset.registry apply`.

    python3 -I tools/parse_sources.py <provider> <page.html> [YYYY-MM-DD] > rows.json

Run with -I and keep downloaded pages outside the repo: they are untrusted input.
Rows whose meaning is unclear (a past date on a model the page still lists as available, an
unparseable date) are skipped and reported on stderr, never guessed.
"""
import datetime as dt
import json
import re
import sys
from html.parser import HTMLParser

ID = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$")
NOT_MODELS = {"fine-tuning"}  # words in OpenAI's table that look like IDs but are not


class Tables(HTMLParser):
    """Collects (nearest heading, rows) for every table."""

    def __init__(self):
        super().__init__()
        self.tables, self.head, self.inh, self.row, self.cell, self.skip = [], "", False, None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4", "summary"):
            self.inh, self.head = True, ""
        elif tag == "table":
            self.tables.append((re.sub(r"\s+", " ", self.head).strip(), []))
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        elif tag in ("h1", "h2", "h3", "h4", "summary"):
            self.inh = False
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", " ", self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None and self.tables:
            self.tables[-1][1].append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.inh:
            self.head += data
        if self.cell is not None:
            self.cell += data


def warn(msg):
    print(f"skipped: {msg}", file=sys.stderr)


def date(text):
    text = text.strip().replace("Sept ", "Sep ")
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def row(id, state, deprecated=None, retires=None, not_before=None, replacement=None):
    if replacement in ("", "—", "-") or (replacement and len(replacement) > 80):
        replacement = None
    return {"id": id, "state": state, "deprecated": deprecated and deprecated.isoformat(),
            "retires": retires and retires.isoformat(),
            "not_before": not_before and not_before.isoformat(), "replacement": replacement}


def openai(tables, today):
    out, seen = [], set()
    for _, rows in tables:
        if not rows or not rows[0] or rows[0][0] != "Shutdown date":
            continue
        head = [h.lower() for h in rows[0]]
        mi = next((i for i, h in enumerate(head) if "model" in h), None)
        ri = next((i for i, h in enumerate(head) if "replacement" in h), None)
        ni = next((i for i, h in enumerate(head) if "notice" in h), None)
        if mi is None:
            continue
        for r in rows[1:]:
            if len(r) != len(head):
                continue
            shut = date(r[0])
            if not shut:
                warn(f"openai: bad date {r[0]!r}")
                continue
            ids = [t for t in re.split(r"[,\s()]+", r[mi]) if ID.match(t) and re.search(r"[\d-]", t) and t not in NOT_MODELS]
            for mid in ids:
                if mid in seen:
                    continue
                seen.add(mid)
                out.append(row(mid, "retired" if shut <= today else "deprecated",
                               date(r[ni]) if ni is not None else None, shut,
                               replacement=r[ri] if ri is not None else None))
    return out


def vertex(tables, today):
    out, seen = [], set()
    for heading, rows in tables:
        if not rows or not rows[0] or rows[0][0] != "Model ID":
            continue
        retired_table = "retired" in heading.lower()
        for r in rows[1:]:
            if len(r) < 4 or not r[0] or r[0] in seen:
                continue
            mid, cell, rep = r[0].rstrip("*"), r[2], r[3]
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._@-]*$", mid):
                warn(f"vertex: unexpected model id {mid!r}")
                continue
            soft = re.match(r"^(?:No sooner than )?(.+?)(?: or later)?$", cell)
            is_soft = "or later" in cell or cell.startswith("No sooner than")
            d = date(soft.group(1)) if cell and soft else None
            if not cell or "No retirement date" in cell:
                out.append(row(mid, "active"))
            elif not d:
                warn(f"vertex: {mid}: bad date {cell!r}")
                continue
            elif is_soft:
                out.append(row(mid, "active", not_before=d))
            elif retired_table:
                out.append(row(mid, "retired", retires=d, replacement=rep))
            elif d <= today:
                warn(f"vertex: {mid}: date {d} has passed but the page still lists it as available")
                continue
            else:
                out.append(row(mid, "active", retires=d, replacement=rep))
            seen.add(mid)
    return out


def mistral(tables, today):
    out, seen = [], set()
    for heading, rows in tables:
        if "retired" not in heading.lower():
            continue
        for r in rows:
            if len(r) != 5 or not ID.match(r[2]) or r[2] in seen:
                continue
            ds = [date(x) for x in re.findall(r"\d{1,2}/\d{1,2}/\d{4}", r[3])]
            if len(ds) != 2 or None in ds or ds[1] < ds[0]:
                warn(f"mistral: {r[2]}: cannot read dates {r[3]!r}")
                continue
            seen.add(r[2])
            out.append(row(r[2], "retired" if ds[1] <= today else "deprecated", ds[0], ds[1],
                           replacement=r[4]))
    return out


def azure(tables, today):
    out, seen = [], {}
    for heading, rows in tables:
        if heading != "Azure OpenAI" or not rows or rows[0][:2] != ["Model", "Version"]:
            continue
        for r in rows[1:]:
            if len(r) != 5:
                continue
            mid, d = f"{r[0]}@{r[1]}", date(r[3][:10])
            if not d:
                warn(f"azure: {mid}: bad date {r[3]!r}")
                continue
            life = r[2].lower()
            if mid in seen:
                if seen[mid] != d:
                    warn(f"azure: {mid}: listed twice with different dates; left out")
                    out = [x for x in out if x["id"] != mid]
                continue
            seen[mid] = d
            if life == "retired":
                out.append(row(mid, "retired", retires=d, replacement=r[4]))
            elif d <= today:
                warn(f"azure: {mid}: date {d} has passed but lifecycle is {r[2]!r}")
            else:
                out.append(row(mid, "deprecated" if life in ("deprecated", "legacy") else "active",
                               retires=d, replacement=r[4]))
        break
    return out


PARSERS = {"openai": openai, "vertex": vertex, "mistral": mistral, "azure": azure}


def main(argv):
    if len(argv) < 2 or argv[0] not in PARSERS:
        sys.exit(__doc__)
    today = dt.date.fromisoformat(argv[2]) if len(argv) > 2 else dt.date.today()
    p = Tables()
    p.feed(open(argv[1], encoding="utf-8", errors="replace").read())
    rows = PARSERS[argv[0]](p.tables, today)
    if not rows:
        sys.exit(f"{argv[0]}: no rows parsed; the page layout probably changed")
    json.dump(rows, sys.stdout, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
