# harness-probe

Probe any coding-agent harness the way kage issue #15 was probed: attempt every
tool a survey lists, record a verdict per row, and produce a coverage report an
operator can trust. Works from inside a single agent session with nothing but
the tools the harness already gave you.

Two artifacts live here:

| File | What it is |
|---|---|
| `PROTOCOL.md` | The method. Read this first. Stage 0 through stage 6. |
| `probe.sh` | Stage 1 environment probe as one runnable script. |
| `tool-table.tsv` | The encoded kage#15 survey: 161 rows, columns `id`, `source`, `names`, `match_any_of`, `purpose`. The rows are every tool named in the issue body (opencode A1-A17, kimi-code B1-B41) and its follow-up comment (pi D1-D8, oh-my-pi E1-E33, codex F1-F36, claude-code G1-G30). |
| `match-tool.py` | Name matcher over that table. Usage: `python3 match-tool.py todowrite TodoWrite web_search exitplanmode`. Matches any spelling: raw, lowercased, snake_case, camelCase, joined (`applypatch`), dotted (`web.run` matches `run`). Exit 0 if any row matched, 1 if none, so it can gate a loop. `--stats` prints the row count per source. |

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

## The one rule that makes the output honest

A claim in your final report must point at a captured output. "The tool is
missing" is a claim: show the `command -v` that returned nothing, the bind that
was denied, the binary that exited 127. "The equivalent worked" is a claim:
show the output of the equivalent. An unverifiable row gets marked `UNVERIFIED`
and stays that way until you run something.

## What was proven with this method

The kage#15 exercise (2026-09-27, 148 tool rows across 6 upstream harnesses)
ran every row to one of four verdicts inside one session of a 4-tool harness:
natively available, equivalent-capability, blocked-with-named-wall, or
not-applicable. The interesting finding class was environmental: loopback
binds denied, PTYs absent, unix sockets allowed, which turned three "impossible"
rows into "possible over stdio/unix-socket transports". A probe that stops at
the first denial never learns that.
