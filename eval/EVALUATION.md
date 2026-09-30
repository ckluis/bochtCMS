# Bocht evaluation — 2026-09-29

Machine: macOS arm64, 16 GB, Apple clang 21, Bend 2.0.34 (official darwin-arm64 build).
Scripts in this folder start `bochtCMS/medium/fresh/med_native_mcp1` on 127.0.0.1:18081.

## Reproduced

| Claim | Result |
|---|---|
| `mcp-blog.bend` SHA-256 `71d886af…` | matches |
| `bocht-r61.bend` SHA-256 `cedfe66d…` | matches |
| MCP blog builds clean on Bend 2.0.34 | yes: exit 0, 26 s (10 harmless `size_t`/`u64` warnings) |
| 43-test probe | `RESULT: PASS=43 FAIL=0` on the Mac build |
| r61 does not build on 2.0.34 | confirmed: `TCP.listen(18081)` type error, as documented |

## Beyond the 43 tests (adv*.py)

Held up:
- wrong, empty, prefix and suffix tokens all get 401
- Unicode, emoji, quotes, HTML and `\u` surrogate pairs round-trip in titles and bodies
- wrong types, missing fields and bad status values get proper `-32602` errors
- 5000-deep nested JSON handled
- 7 kinds of malformed HTTP get clean 4xx responses; the server stays up
- 200 idle connections don't block service
- 500 concurrent creates: all succeed, unique ids, about 1,080 req/s; `tools/list` about 1,600 req/s
- rate limiter returns 429
- 303 acknowledged writes, then SIGKILL mid-burst: 0 lost after restart

Found:
1. **Quadratic JSON parsing on `POST /mcp`, which blocks the whole server.** Timings for a create request:
   1 KB 0.02 s · 4 KB 0.20 s · 8 KB 0.79 s · 16 KB 3.1 s · 32 KB 19.7 s · 48 KB 122 s.
   It is in the MCP request parse, not storage: `tools/list` with a 16 KB junk param takes 2.9 s,
   while REST `POST /v1/articles` with the same 16 KB takes 0.02 s.
   The server is single-threaded, so a legitimate `tools/list` waited 33 s behind one 32 KB post.
   Needs a valid token; unauthenticated junk is rejected in under 10 ms.
   Any key holder can stall the service for minutes with one request under the 64 KB limit. (adv4.py, adv6.py)
2. Tags only accept slug-like strings (`UPPER`, `a-b_c`); `"two words"` and `"café"` are rejected
   with the misleading message "must be a JSON array of strings". (adv3.py)
3. Titles reject newlines and tabs ("1-200 printable chars"), which is reasonable. Request bodies are
   capped at 64 KB (clean 413); requests over about 1 MB get a broken pipe instead of a 413.

## Evidence gaps

- `verify_claims.py` needs `hardening_status.md`, which isn't in the bundle, so "run this first" can't be done.
- `probe_2034_verify.log` is only the one-line summary; the per-check diagnostics weren't kept.
- Manifests are unsigned text: they bind a hash to a log file written by the same agent.
  They can catch drift but they don't prove who ran the test.
- The site says 200/200; the bundle holds one of those 200 items (item197, 27 checks).
- `bocht/README.md` contradicts itself: it says both "r61 does NOT build under 2.0.34"
  and "The build works on 2.0.34". It also calls four version bumps "three".
- `mcp-blog.bend` has 1,504 defs and no proofs (no `Equal`, `refl` or theorems). Bend's formal
  verification isn't used; all verification is black-box probe scripts.

---

# Round 2: "deep-fix" bundle, 2026-09-29

Only `bochtCMS/mcp-blog.bend` changed in substance (9,582 → 9,681 lines, SHA-256 `07a60cbb…`,
which matches the README). It builds clean in 22 s and still passes 43/43. The probe log now
includes per-check lines (round 1 gap fixed).

## Performance: no measurable change on this Mac
Same machine, old vs new binary (adv7.py):

| | 4 KB | 8 KB | 16 KB | 32 KB | update 16 KB | tools/list + 16 KB pad |
|---|---|---|---|---|---|---|
| v1 | 0.20 s | 0.74 s | 2.93 s | 15.0 s | 2.74 s | 2.70 s |
| v2 | 0.20 s | 0.74 s | 2.92 s | 13.5 s | 2.74 s | 2.71 s |

Time still roughly quadruples when size doubles. The README says "the O(n²) algorithmic
bottleneck is fixed" and blames Bend's per-character overhead for what remains. That is contradicted
by REST `POST /v1/articles`, which parses the same 16 KB in 0.02 s. `tools/list` with padding is
still 2.7 s and never reaches the rewritten `tools/call` code, so the slow step is earlier in the MCP path.

## Regressions introduced by the fix (adv7.py, adv8.py; v1 was correct in every row)

| Request | v1 | v2 |
|---|---|---|
| `blog_get_post` whose `arguments` (listed before `name`) contain `"name":"blog_delete_post"` | returns the post | **deletes the post** (`{"deleted":true}`; gone from the list) |
| `params._meta.title` plus `arguments.title:"real"` | stores `real` | stores `META-TITLE` |
| `arguments` is a string or array | -32602 "arguments must be an object" | -32602 "missing required argument: title" |
| `tags:"notarray"` | -32602 | **accepted; tags silently dropped** |
| `params:"notobj"` on `initialize` | -32600 | accepted, returns success |
| no `params.name`, `arguments.name:"blog_list_posts"` | "missing tool name" | runs `blog_list_posts` |
| REST `{"meta":{"title":"NESTED"},"title":"real"}` | stores `real` | **stores `NESTED`** (REST API changed) |

Cause: the `depth==1` guard was removed from `jf_find_key` (around line 1578), so every
`jf_field` lookup returns the first matching key at any depth, including in the REST handlers the
round-1 bundle said were untouched. Tool dispatch now calls `jf_field(body, "name")` on the whole request body.
None of these cases are covered by the 43-test probe.

---

# Round 3: our fix (v1 source + one function), 2026-09-29

the builder's v2 was dropped; the fix is applied to the v1 source, which handled every request correctly.

## Root cause (found with macOS `sample`, not guessed)
The profile during a slow request was almost all `jf_raw_go` and `String.from_list`. `jf_raw_go` reads an
unquoted JSON value (a number, true/false/null):

    Bool.pick(String, jf_raw_end(h), String.from_list(List.reverse(acc)), jf_raw_go(t, h <> acc))

`Bool.pick` evaluates both branches, so at every character it rebuilt the whole string read so far, and it
never stopped at the value's end. Every MCP request reads the JSON-RPC `"id": 1` this way
(`mcp_id_json`), so it walked the rest of the request body with O(k) work per character: quadratic.
The REST clap endpoint reads `"count"` the same way and had the same bug.

## Fix
`jf_raw_go` now takes a `hit: Bool` parameter (whether the previous character was a terminator) and uses
`match` on it, which only evaluates the branch taken. That is the JfAct pattern the file already uses in `jf_str_go`.
It stops at the terminator and builds the string once. One function changed, plus one call site.

## Results (same Mac)
| | 4 KB | 16 KB | 32 KB | 60 KB |
|---|---|---|---|---|
| MCP create, before | 0.20 s | 2.98 s | 13.7 s | — |
| MCP create, after | 0.013 s | 0.036 s | 0.071 s | 0.133 s |
| REST clap + padding, before → after | | 2.85 s → 0.006 s | 13.5 s → 0.011 s | |

Time now grows linearly; MCP is as fast as REST.

## Correctness
- Builds clean; 43-test probe `RESULT: PASS=43 FAIL=0`.
- `diff_v1.py`: 88 requests (16 id shapes × 4 positions, junk/array/object ids, 10 clap bodies,
  the round-2 regression cases, nested REST keys, no-auth) replayed against v1 and the fix:
  **0 differences**. The same harness finds 8 differences between v1 and the builder's v2, so it can catch them.
- adv.py: same 31/8 as round 1; the 8 are known limits or test artifacts.
- kill9.py: acknowledged write, then SIGKILL, then restart, 20 cycles: 20/20 survived (the round-1
  "SIGKILL after ack" failure was the rate limiter answering 429, not data loss).

## Not changed
- `bocht/` (r61 and `src/`) likely has the same `jf_raw_go` (REST clap). r61 is a pinned release
  that doesn't build on 2.0.34, so it was left alone.
- Other strict `Bool.pick` recursions (`jf_skip_ws`, `jf_trail_ws_go`, `mcp_bal_go`) still walk the whole
  body once per call. That is linear and measured fine up to the 64 KB cap; cleanup is optional.
