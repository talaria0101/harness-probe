# Harness probe protocol

Distilled from the kage#15 exercise: attempt every tool a survey lists, inside
the harness you were given, and produce a verdict per row that an operator can
check. The protocol has seven stages. Do them in order; each one decides how
the next one runs.

---

## Stage 0: Define the probe surface

Before running anything, write down the rows you will probe.

1. Get the tool list. Sources in order of trust:
   - A registration site in the harness's own source: a `ToolName` union, a
     `BUILTIN_TOOLS` map, a `Tool.define` array, a `createAllTools` factory.
     Code is the census of record; docs drift.
   - The harness's docs page. Assume it omits experimental and hidden tools.
   - A survey issue or external list. Treat every row as a claim to verify, not
     a fact.
2. Normalize the rows into a checklist with stable IDs. One line per row:
   `ID | name | source harness | claimed purpose`.
3. Add the asides. Survey prose often names extra tools in passing ("hidden",
   "renamed", "removed in vX"). Every named tool is a row.
4. Count the rows. Say the count in your report. "I attempted every tool" is
   checkable only if the reader knows how many there were.
5. Encode the checklist as a TSV with columns `id`, `source`, `names`,
   `match_any_of`, `purpose` (see `tool-table.tsv`), then run
   `python3 selftest.py <table>` on it. The matcher only finds what the table
   says, so a dropped row or a mangled cell turns into a phantom tool gap. Fix
   the table first, probe second.

## Stage 1: Probe the environment before probing any tool

Every later verdict depends on what the cage permits. Run `probe.sh` (same
directory), or do its steps by hand. Record, with captured output:

1. Which harness-natives you actually have in this session. Not which the
   harness ships: which are wired into YOUR turn. Check the system prompt, the
   tool-call wire format, or the session file.
2. What the shipped harness registers vs what your session exposes. If the
   source is on disk, read the registration array and, if it is JS/TS, call the
   factory in-process (node/bun import) to list names. The gap between shipped
   and exposed is a finding.
3. Extensions/plugins already installed. Read their manifests. Note which
   register tools vs providers vs nothing.
4. Binary availability: rg, fd, grep, find, ls, git, jq, curl, node, python3,
   LSP servers, ast-grep, debuggers, pwsh, ida. A missing binary is not yet a
   blocked row; it is a route to try installing.
5. Network shape, and this is the part every probe gets wrong the first time:
   - outbound HTTPS (curl an API),
   - loopback BIND (python `socket.bind` on 127.0.0.1, node http listen),
   - unix socket bind+listen,
   - stdio child pipes,
   - PTYs (`python3 -c "import pty; pty.spawn(['true'])"`, `script -c true`).
   These are five independent capabilities. Sandboxes deny subsets. Bind-denied
   plus stdio-allowed means MCP-over-stdio works and MCP-over-TCP never can.
   Prove each with a minimal snippet and paste the output.
6. Package managers and whether the toolchains work (a compile proves rustc
   exists better than `command -v` does).
7. Date, uid, cwd, resource limits (`ulimit -a`), /dev/pts and /proc/net
   presence. Anything you might blame later, capture now.

## Stage 2: Classify each row BEFORE attempting it

For each row, write the intended verdict class first. This forces you to plan
the attempt instead of improvising a shrug:

| Class | Meaning | Example |
|---|---|---|
| `NATIVE` | this session's own tool list has it | call it directly |
| `EQUIV` | a different surface here does the same job | rg for grep, DDG scrape for websearch |
| `BLOCKED` | the cage or host forbids the mechanism | OAuth callback with loopback binds denied |
| `N/A` | needs a different product or a human | Tower tools need kage; AskUser needs a human |
| `UNVERIFIED` | you did not run anything yet | (must not survive to the final report) |

A row you classified EQUIV still needs the equivalent to actually run. A row
classified BLOCKED needs the denial captured. Classification is a plan, not a
result.

## Stage 3: Attempt natively first, cheaply second, creatively third

For each row, in order:

1. **Call the native tool.** Even if you "know" the result. Read the file, run
   the edit, send the tool call. The call itself is evidence about wiring, not
   just capability.
2. **Look for the equivalent.** The usual map:
   - grep/glob/find -> rg / fd / find
   - webfetch -> curl + an HTML-to-text pass
   - websearch -> a scrape-friendly engine (DuckDuckGo Lite historically
     returns parseable HTML; verify TODAY, engines wall bots without notice)
   - subagent/task -> the harness CLI run headless as a child process, fed a
     prompt, output captured
   - swarm/fan-out -> N headless children in parallel, outputs validated (jq
     for structured rows)
   - structured output -> child returns JSON, validate with jq
   - lsp -> drive the server over stdio JSON-RPC by hand (initialize,
     didOpen, documentSymbol, hover). LSP servers need warmup; a null result
     at attempt 1 is not a final answer, retry after indexing.
   - ast_grep/ast_edit -> `sg run -p PATTERN` / `sg run -p ... -r ... -U`
   - background tasks -> shell `&` + poll + `wait` (read the exit code) +
     kill; coproc for stdin-writing resumable processes
   - clock -> date, sleep; wakeup -> backgrounded sleep-and-fire inside the turn
   - checkpoint/rewind -> git commit / checkout -- ; worktree enter/exit ->
     git worktree add/remove
   - todo/plan -> a file mutated through the session, shown at the end
   - context budget -> the harness RPC/SDK stats if any; compaction refusal on
     an empty session is itself proof the command machinery works
   - eval -> one interpreter process, two cells, prove state survives
   - MCP -> a mini JSON-RPC server over stdio (initialize / tools/list /
     tools/call). If TCP is bind-blocked, stdio is the transport that still
     proves the protocol shape.
   - apply_patch dialect -> a ~20-line consumer for the `*** Begin Patch`
     format, if the harness lacks it
   - code-mode -> a sandboxed VM runtime (node:vm with a timeout) calling
     tool-equivalents as injected functions
   - custom tools/plugins -> build the smallest real extension, install it the
     documented way, and have a child session call it end to end
   - tool_search/deferred loading -> the harness's allowlist flag with two
     different sets, children reporting their own visible tool names
   - cross-session messaging -> unix socket or named pipe between two processes
3. **Read the harness's own docs** for the surface you are substituting
   (extension API, RPC commands, package layout). The docs of the INSTALLED
   version, not your memory of the tool.
4. **Distrust first nulls.** Skills absent without project trust and present
   with it; LSP hover null until the indexer warms; extension directory
   packages failing until they have the conventional layout. Retry with the
   knob turned before writing BLOCKED.

## Stage 4: Prove the wall, do not assert it

A BLOCKED verdict needs the mechanism named and the denial captured:

| Claimed wall | Minimal proof |
|---|---|
| no binary | `command -v x` empty, and install attempt failed or unnecessary |
| bind denied | the exact bind call + `Permission denied` from two stacks (python and node) |
| no PTY | pty.spawn traceback + `script` failure + absent /dev/pts |
| no daemon | `ps` output |
| model/provider gap | the tool result saying the image "was not shown to the model" |
| interactive-only | where in the flow a human is required, and what you did instead |

Then run the substitution check: is there a socket-shaped, pipe-shaped, or
file-shaped route around the wall? Bind denied but unix sockets fine changes
the verdict from BLOCKED to EQUIV for anything that can ride a unix socket.

## Stage 5: Negative and self-check rows

Some rows are guards, not features. Test them as guards:

- unknown-tool dispatch: the API schema usually prevents fake calls; find the
  runtime guard text in source, quote it.
- refusals that prove machinery: compaction on an empty session, an install
  command on a bad path. A correct refusal is a PASS for the row.
- self-report checks: ask a child session to list its own tools and compare
  against the registration array you read in Stage 1. Children that under- or
  over-report are findings.

## Stage 6: Report format

One line per row, this shape:

```
<ID> <name> -> <VERDICT> : <one-sentence evidence pointer>
```

Evidence pointer formats that work:
- `ran: <exact command> -> <key output fragment>`
- `native call: <tool> on <file>, result <verified/failed because>`
- `blocked: <mechanism>, denial: <captured message>`
- `N/A: requires <thing>, absent because <captured reason>`
- `equiv: <substitute> <command> -> <output fragment>`

Close the report with three counts and two lists:
- N rows, N attempted, N verdicts with captured evidence.
- Findings list: anything learned that the survey got wrong or did not know
  (gaps between shipped and exposed tools, trust gates, version drift).
- Environment limits list with expiry: each wall is true as of today on this
  cage. Write the date. A limit recorded without an expiry reads as a law.

## Calibrations learned the hard way

- A hand-encoded survey rots silently. A dropped row and a mangled
  `match_any_of` cell both look exactly like a harness that lacks the tool, and
  nothing in the probe can tell them apart. `selftest.py` exists because both
  happened in this table: codex's hosted `web_search` (F35) was missing, and
  the claude-code `Write`/`Edit`/`Glob`/`Grep` row was unmatchable.
- The first explanation that fits is the most dangerous object in the probe.
  "pwsh missing" ended one row, but "pty missing" would have wrongly ended the
  background-jobs row had `&`+poll not been tried first.
- Docs of the installed version beat memory. Flags rename, defaults invert.
- A survey row is a claim about SOMEONE ELSE's harness. Verify the name, the
  gate, and the mechanism here, every time.
- Cleanup is part of the probe. Remove scaffolding you created in the mounted
  workspace after the proof, and record the recipe in the report instead.
- Save reusable environment findings (bind policy, PTY policy, proxy shape) to
  the project notes so the next session skips Stage 1's failures, not Stage 1.
