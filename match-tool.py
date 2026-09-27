#!/usr/bin/env python3
"""Match a tool name against the survey table, ignoring case and spelling style.

Usage:
    python3 match-tool.py todowrite
    python3 match-tool.py TodoWrite web_search exitplanmode
    python3 match-tool.py --stats

Reads tool-table.tsv (same directory). Prints every row whose match_any_of set
contains the name under any of the accepted spellings:

    raw name            TodoWrite
    lowercased          todowrite
    snake_case          ask_user_question
    camelCase           applyPatch
    joined lowercase    askuserquestion, applypatch

Exit code 0 if at least one row matched, 1 if none.
"""

import csv
import sys
from pathlib import Path

TABLE = Path(__file__).resolve().parent / "tool-table.tsv"


def normalize(name: str) -> set[str]:
    """Every spelling of `name` that should be considered equivalent."""
    base = name.strip()
    if not base:
        return set()
    lower = base.lower()
    alts = {base, lower}

    # snake/dotted -> camel + Pascal + joined
    parts = [p for p in base.replace(".", "_").split("_") if p]
    if len(parts) > 1:
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        pascal = "".join(p.capitalize() for p in parts)
        alts |= {camel, camel.lower(), pascal, pascal.lower(), lower.replace("_", "")}

    # CamelCase -> snake
    if re_match_camel(base):
        alts |= {camel_to_snake(base)}

    # dotted namespace: web.run -> run / web_run
    if "." in base:
        tail = base.rsplit(".", 1)[-1]
        alts |= {tail, tail.lower(), base.replace(".", "_")}

    return {a for a in alts if a}


def re_match_camel(name: str) -> bool:
    return name[0].isupper() and any(c.isupper() or c.isdigit() for c in name[1:])


def camel_to_snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and (not name[i - 1].isupper() or (i + 1 < len(name) and name[i + 1].islower())):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def load_rows() -> list[dict]:
    with TABLE.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main(argv: list[str]) -> int:
    if not TABLE.exists():
        print(f"table not found: {TABLE}", file=sys.stderr)
        return 2

    rows = load_rows()

    if argv and argv[0] == "--stats":
        sources: dict[str, int] = {}
        for r in rows:
            sources[r["source"]] = sources.get(r["source"], 0) + 1
        print(f"{len(rows)} rows")
        for src, n in sorted(sources.items()):
            print(f"  {src}: {n}")
        return 0

    if not argv:
        print(__doc__)
        return 2

    any_match = False
    for query in argv:
        qset = normalize(query)
        hits = []
        for r in rows:
            table_alts = {a.strip() for a in r["match_any_of"].split(",")}
            if qset & table_alts:
                hits.append(r)
        if hits:
            any_match = True
            print(f"{query} -> {len(hits)} row(s):")
            for r in hits:
                print(f"  [{r['id']}] {r['source']}: {r['names']} -- {r['purpose']}")
        else:
            print(f"{query} -> NO MATCH in table")
    return 0 if any_match else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
