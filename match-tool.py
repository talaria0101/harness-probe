#!/usr/bin/env python3
"""Match a tool name or survey id against the survey table, ignoring case and
spelling style.

Usage:
    python3 match-tool.py todowrite
    python3 match-tool.py TodoWrite web_search exitplanmode
    python3 match-tool.py --ids web_search          # one row id per line, for loops
    python3 match-tool.py --json exitplanmode       # machine-readable rows
    python3 match-tool.py --stats                   # row count per source
    python3 match-tool.py --table other.tsv Write

Reads tool-table.tsv (same directory) unless --table names another table.
A query matches a row when it is one of the row's accepted spellings:

    raw name            TodoWrite
    lowercased          todowrite
    snake_case          ask_user_question
    camelCase           applyPatch
    joined lowercase    askuserquestion, applypatch

A bare survey id (`B20`, `g4`) matches the row carrying that id, including the
ids a stacked comment row carried (`G4`/`G5` land on row `G3`). Exit code 0 if
at least one row matched, 1 if none, 2 on usage or table error.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

TABLE = Path(__file__).resolve().parent / "tool-table.tsv"
ID_RE = re.compile(r"^[A-Za-z]\d+$")


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
    if looks_camel(base):
        alts |= {camel_to_snake(base)}

    # dotted namespace: web.run -> run / web_run
    if "." in base:
        tail = base.rsplit(".", 1)[-1]
        alts |= {tail, tail.lower(), base.replace(".", "_")}

    return {a for a in alts if a}


def looks_camel(name: str) -> bool:
    return bool(name) and name[0].isupper() and any(
        c.isupper() or c.isdigit() for c in name[1:])


def camel_to_snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and (
                not name[i - 1].isupper() or (i + 1 < len(name) and name[i + 1].islower())):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def row_tokens(row: dict) -> set[str]:
    return {t.strip() for t in row["match_any_of"].split(",") if t.strip()}


def find_matches(query: str, rows: list[dict]) -> list[dict]:
    """Rows whose accepted spellings contain `query`, or whose survey id it is."""
    qset = normalize(query)
    upper = query.strip().upper()
    by_id = ID_RE.match(query.strip())
    hits = []
    for row in rows:
        toks = row_tokens(row)
        if qset & toks:
            hits.append(row)
        elif by_id:
            labels = {t.upper() for t in toks if ID_RE.match(t)}
            if upper == row["id"].upper() or upper in labels:
                hits.append(row)
    return hits


def load_rows(path: Path = TABLE) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="match-tool.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("queries", nargs="*", help="tool names or survey ids to look up")
    parser.add_argument("--table", default=str(TABLE), help="TSV table to read")
    parser.add_argument("--ids", action="store_true", help="print matching row ids only")
    parser.add_argument("--json", action="store_true", help="print matching rows as JSON")
    parser.add_argument("--stats", action="store_true", help="print row count per source")
    args = parser.parse_args(argv)

    table = Path(args.table)
    if not table.exists():
        print(f"table not found: {table}", file=sys.stderr)
        return 2

    rows = load_rows(table)

    if args.stats:
        sources: dict[str, int] = {}
        for r in rows:
            sources[r["source"]] = sources.get(r["source"], 0) + 1
        print(f"{len(rows)} rows")
        for src, n in sorted(sources.items()):
            print(f"  {src}: {n}")
        return 0

    if not args.queries:
        parser.print_help()
        return 2

    matched_ids: list[str] = []
    any_match = False
    for query in args.queries:
        hits = find_matches(query, rows)
        if hits:
            any_match = True
            matched_ids.extend(r["id"] for r in hits)
        if args.json:
            continue
        if args.ids:
            continue
        if hits:
            print(f"{query} -> {len(hits)} row(s):")
            for r in hits:
                print(f"  [{r['id']}] {r['source']}: {r['names']} -- {r['purpose']}")
        else:
            print(f"{query} -> NO MATCH in table")

    if args.json:
        hit_ids = set(matched_ids)
        print(json.dumps([r for r in rows if r["id"] in hit_ids], indent=2))
    elif args.ids:
        for row_id in dict.fromkeys(matched_ids):
            print(row_id)

    return 0 if any_match else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
