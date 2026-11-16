"""Load, validate and query the model retirement registry (data/registry.json)."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "registry.json"
STATES = {"active", "deprecated", "retired"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")
MODEL_FIELDS = ("state", "deprecated", "retires", "not_before", "replacement")


def load(path=DATA) -> dict:
    reg = json.loads(pathlib.Path(path).read_text())
    validate(reg)
    return reg


def save(reg: dict, path=DATA) -> None:
    validate(reg)
    pathlib.Path(path).write_text(json.dumps(reg, indent=1) + "\n")


def _date(value, where):
    if value is None:
        return None
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise ValueError(f"{where}: bad date {value!r}")
    return dt.date.fromisoformat(value)


def validate(reg: dict) -> None:
    providers = {}
    for p in reg["providers"]:
        if p["id"] in providers:
            raise ValueError(f"duplicate provider {p['id']}")
        if not p["source_url"].startswith("https://"):
            raise ValueError(f"{p['id']}: source_url must be https")
        _date(p.get("verified"), p["id"])
        providers[p["id"]] = p
    seen = set()
    for m in reg["models"]:
        key = (m["provider"], m["id"])
        where = "/".join(key)
        if key in seen:
            raise ValueError(f"duplicate model {where}")
        seen.add(key)
        if m["provider"] not in providers:
            raise ValueError(f"{where}: unknown provider")
        if not providers[m["provider"]].get("verified"):
            raise ValueError(f"{where}: provider has no verified date; unverified data is not published")
        if not ID_RE.match(m["id"]):
            raise ValueError(f"{where}: bad model id")
        if m["state"] not in STATES:
            raise ValueError(f"{where}: bad state {m['state']!r}")
        dep = _date(m.get("deprecated"), where)
        ret = _date(m.get("retires"), where)
        _date(m.get("not_before"), where)
        if m.get("retires") and m.get("not_before"):
            raise ValueError(f"{where}: set retires or not_before, not both")
        if dep and ret and ret < dep:
            raise ValueError(f"{where}: retires before deprecated")
        if m["state"] == "retired" and not ret:
            raise ValueError(f"{where}: retired without a date")


def status(m: dict, today: dt.date) -> str:
    """active | deprecated (no date yet) | retiring (firm future date) | retired."""
    if m.get("retires"):
        return "retired" if dt.date.fromisoformat(m["retires"]) <= today else "retiring"
    return "deprecated" if m["state"] == "deprecated" else "active"


def days_left(m: dict, today: dt.date):
    if not m.get("retires"):
        return None
    return (dt.date.fromisoformat(m["retires"]) - today).days


def key(m: dict) -> str:
    return f"{m['provider']}/{m['id']}"


def path(model_key: str) -> str:
    """URL path segment for a model key: provider/slug."""
    provider, _, mid = model_key.partition("/")
    return f"{provider}/{re.sub(r'[^A-Za-z0-9._-]', '-', mid)}"


def view(reg: dict, today: dt.date) -> list[dict]:
    """Models with computed status and days_left, soonest retirement first."""
    out = []
    for m in reg["models"]:
        v = dict(m, key=key(m), status=status(m, today), days_left=days_left(m, today))
        out.append(v)
    order = {"retiring": 0, "deprecated": 1, "active": 2, "retired": 3}

    def sort_key(v):
        if v["status"] == "retired":
            return (3, -dt.date.fromisoformat(v["retires"]).toordinal(), v["id"])
        date = v["retires"] or v["not_before"] or "9999-12-31"
        return (order[v["status"]], dt.date.fromisoformat(date).toordinal(), v["id"])

    return sorted(out, key=sort_key)


def apply_snapshot(reg: dict, provider_id: str, rows: list[dict], today: dt.date) -> list[dict]:
    """Replace one provider's models with a freshly read snapshot of its official page.

    Returns the change records appended to reg["changes"]. Models missing from the snapshot
    are kept (pages drop old rows) unless they were never retired, which is flagged.
    """
    prov = next(p for p in reg["providers"] if p["id"] == provider_id)
    old = {m["id"]: m for m in reg["models"] if m["provider"] == provider_id}
    first_import = not prov.get("verified")  # nothing to compare against: record no changes
    changes = []
    new_models = []
    for row in rows:
        m = {"provider": provider_id, "id": row["id"], "state": row["state"]}
        for f in MODEL_FIELDS[1:]:
            m[f] = row.get(f)
        prev = old.pop(m["id"], None)
        if prev is None:
            changes.append({"date": today.isoformat(), "provider": provider_id, "id": m["id"],
                            "field": "added", "old": None, "new": m["retires"] or m["not_before"]})
        else:
            for f in MODEL_FIELDS:
                if prev.get(f) != m.get(f):
                    changes.append({"date": today.isoformat(), "provider": provider_id,
                                    "id": m["id"], "field": f, "old": prev.get(f), "new": m.get(f)})
        new_models.append(m)
    for prev in old.values():
        if status(prev, today) != "retired":
            changes.append({"date": today.isoformat(), "provider": provider_id, "id": prev["id"],
                            "field": "missing_from_source", "old": None, "new": None})
        new_models.append(prev)
    reg["models"] = [m for m in reg["models"] if m["provider"] != provider_id] + new_models
    prov["verified"] = today.isoformat()
    if first_import:
        changes = []
    reg.setdefault("changes", []).extend(changes)
    validate(reg)
    return changes


def main(argv=None):
    """python -m sunset.registry apply <provider> <rows.json>  |  validate"""
    import sys
    argv = argv or sys.argv[1:]
    if argv[:1] == ["validate"]:
        reg = load()
        print(f"ok: {len(reg['models'])} models, "
              f"{sum(1 for p in reg['providers'] if p.get('verified'))} verified providers")
    elif argv[:1] == ["apply"] and len(argv) == 3:
        reg = json.loads(DATA.read_text())
        changes = apply_snapshot(reg, argv[1], json.loads(pathlib.Path(argv[2]).read_text()),
                                 dt.date.today())
        save(reg)
        print(json.dumps(changes, indent=1))
    else:
        sys.exit(main.__doc__)


if __name__ == "__main__":
    main()
