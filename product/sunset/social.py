"""Print today's posts for the company X account: python -m sunset.social [YYYY-MM-DD]

Output is JSON: posts not yet recorded in data/posted.json. After publishing a post, record
it with: python -m sunset.social --done <id>. At most MAX_PER_DAY are offered per day.
"""
import datetime as dt
import json
import os
import pathlib
import sys

from . import events, registry

POSTED = registry.DATA.parent / "posted.json"
MAX_PER_DAY = 4


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    posted = json.loads(POSTED.read_text()) if POSTED.exists() else []
    if argv[:1] == ["--done"]:
        posted.append(argv[1])
        POSTED.write_text(json.dumps(sorted(set(posted)), indent=1) + "\n")
        return
    today = dt.date.fromisoformat(argv[0]) if argv else dt.date.today()
    site = os.environ.get("SITE_URL", "https://modelsunset.dev").rstrip("/")
    todo = [p for p in events.posts(registry.load(), today, site) if p["id"] not in posted]
    print(json.dumps(todo[:MAX_PER_DAY], indent=1))


if __name__ == "__main__":
    main()
