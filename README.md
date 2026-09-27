# harness-probe

Probe any coding-agent harness the way kage issue #15 was probed: attempt every
tool a survey lists, record a verdict per row, and produce a coverage report an
operator can trust. Works from inside a single agent session with nothing but
the tools the harness already gave you.

Five files live here:

| File | What it is |
|---|---|
| `PROTOCOL.md` | The method. Read this first. Stage 0 through stage 6. |
| `probe.sh` | Stage 1 environment probe as one runnable script. |
| `tool-table.tsv` | The encoded kage#15 survey: 162 rows, columns `id`, `source`, `names`, `match_any_of`, `purpose`. The encoded rows are the stable-name tools: issue body opencode A1-A17 and kimi-code B1-B41, follow-up comment pi D1-D8, oh-my-pi E1-E33, codex F1-F36, claude-code G1-G30. The dynamic rows the survey also names (A18/A19 MCP and custom tools, B42/B43, F37/F38) are deliberately absent because their names are minted at runtime. The comment stacked the claude-code file tools, so G3/G4/G5 are one row and G6/G7 are one row; the sub-labels stay matchable as id aliases. |
| `match-tool.py` | Name and id matcher over that table. Usage: `python3 match-tool.py todowrite TodoWrite web_search exitplanmode`. Matches any spelling: raw, lowercased, snake_case, camelCase, joined (`applypatch`), dotted (`web.run` matches `run`); a bare survey id (`B20`, `G4`) matches the row carrying it. `--ids` prints ids only, for loops; `--json` emits rows; `--stats` prints the row count per source. Exit 0 if any row matched, 1 if none, so it can gate a loop. |
| `selftest.py` | The encoder's check: schema, per-source id coverage, name round-trip, token sanity, golden queries, the CLI contract, and the README row count. Run `python3 selftest.py` after any table edit. |

## Use it

1. Get the tool list to probe. A survey issue, a docs page, a registry array in
   source. If the source of the harness is available, prefer the registration
   site over any document: the code is the census of record.
2. Run `PROTOCOL.md` stage by stage. Stage 1 is automated in `probe.sh`; run it
   before anything else and read its output, because every later decision
   depends on what the cage permits. The script is self-checking: on this
   session's cage it printed `BIND DENIED`, `UNIX SOCK OK`, `stdio roundtrip
   OK`, and a compile smoke returning rc=42, which is the evidence shape every
   BLOCKED and EQUIV verdict needs.
3. Record one verdict per row in the format at the end of PROTOCOL.md. Empty
   and blocked results are results. Say what fired and what would have changed
   it.

## Encoding a survey

Encode it as a TSV with the same five columns, one row per tool. One row may
carry several names and several ids; that is how the stacked claude-code file
tools landed. Then run `python3 selftest.py your-table.tsv` before probing
anything. The matcher only finds what the table actually says, and a table that
lost a row or had a paste artifact in a `match_any_of` cell reads as a tool gap
that does not exist.

## The one rule that makes the output honest

A claim in your final report must point at a captured output. "The tool is
missing" is a claim: show the `command -v` that returned nothing, the bind that
was denied, the binary that exited 127. "The equivalent worked" is a claim:
show the output of the equivalent. An unverifiable row gets marked `UNVERIFIED`
and stays that way until you run something.

## What was proven with this method

The kage#15 exercise (2026-09-27) surveyed 162 rows across 6 upstream harnesses
and ran every row to one of four verdicts inside one session of a 4-tool
harness: natively available, equivalent-capability, blocked-with-named-wall, or
not-applicable. The interesting finding class was environmental: loopback binds
denied, PTYs absent, unix sockets allowed, which turned three "impossible" rows
into "possible over stdio/unix-socket transports". A probe that stops at the
first denial never learns that.
