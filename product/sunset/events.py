"""Derive the public event stream (feed, social posts) from the registry."""
from __future__ import annotations

import datetime as dt

from . import registry

REMINDER_DAYS = (30, 7, 1)


def _names(reg):
    return {p["id"]: p["name"] for p in reg["providers"]}


def events(reg: dict, today: dt.date) -> list[dict]:
    """Everything that has happened up to today, newest first."""
    names = _names(reg)
    out = []
    for m in reg["models"]:
        k, prov = registry.key(m), names[m["provider"]]
        if m.get("deprecated") and m["deprecated"] <= today.isoformat():
            tail = f" It will be retired on {m['retires']}." if m.get("retires") else \
                " No retirement date has been published yet."
            if m.get("replacement"):
                tail += f" Recommended replacement: {m['replacement']}."
            out.append({"id": f"{k}#deprecated#{m['deprecated']}", "date": m["deprecated"],
                        "type": "deprecated", "key": k,
                        "title": f"{m['id']} deprecated by {prov}",
                        "text": f"{prov} deprecated {m['id']} on {m['deprecated']}." + tail})
        if m.get("retires") and m["retires"] <= today.isoformat():
            tail = f" Recommended replacement: {m['replacement']}." if m.get("replacement") else ""
            out.append({"id": f"{k}#retired#{m['retires']}", "date": m["retires"],
                        "type": "retired", "key": k,
                        "title": f"{m['id']} retired by {prov}",
                        "text": f"{prov} retired {m['id']} on {m['retires']}. "
                                f"Requests to this model ID no longer work as before." + tail})
    for c in reg.get("changes", []):
        if c["field"] != "retires" or not c["old"] or not c["new"]:
            continue
        k = f"{c['provider']}/{c['id']}"
        out.append({"id": f"{k}#moved#{c['date']}#{c['new']}", "date": c["date"],
                    "type": "date_changed", "key": k,
                    "title": f"{c['id']} retirement date changed",
                    "text": f"{names[c['provider']]} moved the retirement of {c['id']} "
                            f"from {c['old']} to {c['new']}."})
    return sorted(out, key=lambda e: (e["date"], e["id"]), reverse=True)


def posts(reg: dict, today: dt.date, site_url: str) -> list[dict]:
    """Posts the company account should publish today. Each has a stable id for dedupe."""
    names = _names(reg)
    out = []
    for e in events(reg, today):
        if e["date"] == today.isoformat():
            out.append({"id": e["id"], "text": _fit(e["text"], f"{site_url}/models/{registry.path(e['key'])}/")})
    for m in registry.view(reg, today):
        if m["status"] == "retiring" and m["days_left"] in REMINDER_DAYS:
            d = m["days_left"]
            when = "tomorrow" if d == 1 else f"in {d} days"
            text = f"{m['id']} ({names[m['provider']]}) retires {when}, on {m['retires']}."
            if m.get("replacement"):
                text += f" Replacement: {m['replacement']}."
            out.append({"id": f"{m['key']}#reminder#{m['retires']}#{d}",
                        "text": _fit(text, f"{site_url}/models/{registry.path(m['key'])}/")})
    return out


def _fit(text: str, url: str, limit: int = 280) -> str:
    room = limit - 24  # X counts any link as 23 characters, plus a space
    if len(text) > room:
        text = text[: room - 1].rstrip() + "…"
    return f"{text} {url}"
