#!/usr/bin/env python3
"""Self-test for tool-table.tsv and match-tool.py.

The table is hand-encoded from a survey, and hand-encoding rots silently: a row
can be dropped (codex F35 was), or its `names`/`match_any_of` cells can be
mangled by a bad paste (claude-code G3/G6 were), and the matcher simply stops
finding those tools. Nothing in the repo noticed until this file existed.

Usage:
    python3 selftest.py [TABLE]

TABLE defaults to tool-table.tsv next to this script. Schema, id uniqueness,
name round-trip and token checks run on any table; the survey-coverage, golden
query and README checks only run on the bundled tool-table.tsv. Every check
prints its name and, on failure, the exact rows or strings that broke it.
Exit 0 if all checks pass, 1 otherwise.
"""

import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TABLE = HERE / "tool-table.tsv"
TABLE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_TABLE

# The survey ranges the README advertises. A dropped row shows up as a gap.
# claude-code is the one source whose comment numbered stacked rows, so G4/G5/G7
# live as label aliases on the G3/G6 rows instead of as rows of their own.
EXPECTED = {
    "opencode": ("A", 1, 17),
    "kimi-code": ("B", 1, 41),
    "pi": ("D", 1, 8),
    "oh-my-pi": ("E", 1, 33),
    "codex": ("F", 1, 36),
    "claude-code": ("G", 1, 30),
}
EXPECTED_ROWS_PER_SOURCE = {"opencode": 17, "kimi-code": 41, "pi": 8,
                            "oh-my-pi": 33, "codex": 36, "claude-code": 27}
EXPECTED_TOTAL = sum(EXPECTED_ROWS_PER_SOURCE.values())
HEADER = ["id", "source", "names", "match_any_of", "purpose"]
ID_RE = re.compile(r"^[A-Za-z]\d+$")

# query -> row ids that MUST come back. The first four are the regression: on the
# broken table they returned no claude-code row at all.
GOLDEN = [
    ("Write", ["A2", "B2", "D5", "E4", "G3"]),
    ("Edit", ["A3", "B3", "D4", "E3", "G3"]),
    ("Grep", ["A5", "B6", "D6", "E5", "G6"]),
    ("Glob", ["A4", "B5", "E6", "G6"]),
    ("web_search", ["A10", "B8", "E15", "F35", "G18"]),
    ("web.run", ["F34"]),
    ("fetch_url", ["B7"]),
    ("mcp_search", ["G17"]),
    ("todowrite", ["A8", "G10"]),
    ("exitplanmode", ["B20", "G22"]),
    ("G4", ["G3"]),          # survey-label lookup
    ("G5", ["G3"]),
    ("G7", ["G6"]),
    ("B20", ["B20"]),        # bare survey id
]
GOLDEN_MISS = "this-tool-does-not-exist"

# normalize() spellings every encoding must accept.
NORMALIZE_CASES = {
    "FetchURL": "fetch_url",
    "MCPSearch": "mcp_search",
    "ApplyPatch": "apply_patch",
    "ReadMediaFile": "read_media_file",
    "web.run": "run",
    "TodoWrite": "todo_write",
}


def load_matcher():
    spec = importlib.util.spec_from_file_location("match_tool", HERE / "match-tool.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mt = load_matcher()
FAILURES: list[str] = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'}  {name}")
    if not ok:
        FAILURES.append(name)
        if detail:
            for line in str(detail).splitlines():
                print(f"        {line}")
    return ok


def load_rows(path):
    with open(path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
        return reader.fieldnames, rows


def source_labels(rows, source):
    """Row ids plus id-shaped label aliases carried by that source's rows."""
    labels = set()
    for r in rows:
        if r["source"] != source:
            continue
        labels.add(r["id"])
        labels |= {t.strip() for t in r["match_any_of"].split(",")
                   if ID_RE.match(t.strip())}
    return labels


def main():
    if not TABLE.exists():
        print(f"table not found: {TABLE}", file=sys.stderr)
        return 2
    is_default = TABLE == DEFAULT_TABLE.resolve()

    header, rows = load_rows(TABLE)

    check("schema: header is id/source/names/match_any_of/purpose",
          header == HEADER, f"got {header}")

    bad_cells = [(r.get("id", "?"), k) for r in rows for k, v in r.items()
                 if k in HEADER and not (v or "").strip()]
    check("schema: no empty cells", not bad_cells, bad_cells)

    ids = [r["id"] for r in rows if r.get("id")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    check("schema: row ids are unique", not dupes, f"duplicates: {dupes}")

    # Every name must be findable, both directly and through the matcher.
    unreachable = []
    for r in rows:
        toks = mt.row_tokens(r)
        for name in (n.strip() for n in r["names"].split(",")):
            if name and not (mt.normalize(name) & toks):
                unreachable.append(f"{r['id']}: name {name!r} not covered by {sorted(toks)}")
    check("names: every name in `names` matches its own row", not unreachable, unreachable)

    # No matcher token the row's own names cannot produce, except label aliases.
    junk = []
    for r in rows:
        names = [n.strip() for n in r["names"].split(",") if n.strip()]
        allowed = set().union(*(mt.normalize(n) for n in names))
        for tok in (t.strip() for t in r["match_any_of"].split(",")):
            if not tok:
                continue
            if re.search(r"[\s`]", tok):
                junk.append(f"{r['id']}: token contains whitespace or backtick: {tok!r}")
            elif not ID_RE.match(tok) and tok not in allowed:
                junk.append(f"{r['id']}: token {tok!r} is not a spelling of any of {names}")
    check("tokens: every match_any_of token is derivable (or a survey id)", not junk, junk)

    for name, want in NORMALIZE_CASES.items():
        got = mt.normalize(name)
        check(f"normalize: {name!r} -> {want!r}", want in got, f"got {sorted(got)}")

    if is_default:
        check(f"count: {EXPECTED_TOTAL} rows total", len(rows) == EXPECTED_TOTAL,
              f"got {len(rows)}; README advertises {EXPECTED_TOTAL}")

        # Every advertised survey label is present as a row id or a label alias.
        for source, (prefix, lo, hi) in EXPECTED.items():
            src_rows = [r for r in rows if r["source"] == source]
            missing = sorted({f"{prefix}{i}" for i in range(lo, hi + 1)}
                             - source_labels(rows, source), key=lambda x: int(x[1:]))
            check(f"coverage: {source} has {prefix}{lo}-{prefix}{hi}",
                  not missing and len(src_rows) == EXPECTED_ROWS_PER_SOURCE[source],
                  f"missing labels: {missing}; rows: {len(src_rows)} "
                  f"(expected {EXPECTED_ROWS_PER_SOURCE[source]})")

        for query, must_include in GOLDEN:
            got = {r["id"] for r in mt.find_matches(query, rows)}
            missing = [i for i in must_include if i not in got]
            check(f"golden: {query!r} matches {must_include}", not missing,
                  f"missing {missing}; got {sorted(got)}")

        miss_rows = mt.find_matches(GOLDEN_MISS, rows)
        check(f"golden: {GOLDEN_MISS!r} matches nothing", not miss_rows,
              f"got {[r['id'] for r in miss_rows]}")

        readme = (HERE / "README.md").read_text()
        check(f"docs: README advertises {EXPECTED_TOTAL} rows",
              f"{EXPECTED_TOTAL} rows" in readme,
              "README does not contain the table's row count")

    # CLI surface: --ids, --json, and the exit-code contract, against the
    # bundled table (match-tool.py's own default).
    def run(*args):
        return subprocess.run([sys.executable, str(HERE / "match-tool.py"), *args],
                              capture_output=True, text=True)

    p = run("--ids", "web_search")
    check("cli: --ids web_search prints F35 and exits 0",
          p.returncode == 0 and "F35" in p.stdout, f"rc={p.returncode} out={p.stdout!r}")

    p = run("--json", "exitplanmode")
    ok = False
    if p.returncode == 0:
        try:
            ok = {r["id"] for r in json.loads(p.stdout)} >= {"B20", "G22"}
        except json.JSONDecodeError:
            ok = False
    check("cli: --json exitplanmode returns valid JSON with B20/G22", ok,
          f"rc={p.returncode} out={p.stdout!r}")

    p = run("this-tool-does-not-exist")
    check("cli: unknown name exits 1", p.returncode == 1, f"rc={p.returncode}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: " + ", ".join(FAILURES))
        return 1
    scope = "bundled survey" if is_default else f"{TABLE.name} (generic checks only)"
    print(f"all checks passed ({scope}, {len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
