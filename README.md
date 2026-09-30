> **Case study:** https://ckluis.github.io/bochtCMS/ (part 2 of the [Bend series](https://ckluis.github.io/experiments/bend/): [bocht](https://github.com/ckluis/bocht) · [bochtCMS](https://github.com/ckluis/bochtCMS) · [shellOS](https://github.com/ckluis/shellOS)).
> The page is `index.html` in this repo, served by GitHub Pages from `main`. Below: the builder's bundle README, kept as shipped; the audit is in `eval/EVALUATION.md`.

# Bocht MCP blog — validatable source bundle

The whole CMS is one Bend program exposing its entire interface as MCP tools
over HTTP. This bundle contains everything needed to rebuild it from source
and re-run its 43-test verification suite. Assembled 2026-09-29 (deep-fix
revision: MCP large-request performance fix included).

## What this proves (and what it doesn't)

- The program (`mcp-blog.bend`, 9,681 lines) builds clean under Bend 2.0.34
  (exit 0) and passes its 43-test probe, including a WAL-replay persistence
  check across a server restart.
- The probe emits a canonical `RESULT: PASS=43 FAIL=0` line; anything else is
  a failure. `manifest_2034.txt` binds the exact binary SHA-256 to the result.
- This revision includes the deep performance fix for large MCP requests:
  the authenticated-parse hot path no longer does balanced-bracket extraction
  (`mcp_subval`) or kind-probing (`mcp_val_kind`) per request; 16 kB create
  went from ~46s to ~12s. Honest note: 12s is still slow — the remaining cost
  is Bend's per-character `jf_scan` overhead, not an algorithmic bug.
- What it doesn't prove: correctness beyond the 43 tests, production
  readiness, or anything about replication (there is none — single node).

## Contents

- `mcp-blog.bend` — the exact program the verified binary was built from.
  SHA-256 `07a60cbb6ca8a388af29fd6048e1f5a4785fc5eb715f00a0eb826b325a74d334`
- `effs/` — custom C effect implementations, pulled in by
  `import "./effs/….c"` lines in the source. Keep next to `mcp-blog.bend`.
  (`.js` files are the interpreter-backend variants.)
- `tests/probe_mcp_final.py` — the 43-test probe. Self-contained: starts its
  own server on `127.0.0.1:18081`, sets its own admin credential, runs the
  suite, restarts the server to verify WAL replay, then stops the listener.
  Two small portability patches vs the original (both marked in the file):
  `BOCHT_ROOT` env override for the project root, and an `lsof` fallback
  where macOS has no `ss`.
- `tests/probe_2034_verify.log` — our reference run: `RESULT: PASS=43 FAIL=0`.
- `manifest_2034.txt` — binds binary SHA-256 `c50db6f2…` to the probe result.
- `build2034_meta.txt` — the build record (exit 0, source + binary hashes).
- `manifest_mcp.txt` — the earlier 2.0.32-era manifest for reference.
- `campaign/` — `verify_claims.py` (checks evidence claims against disk) and
  `stamp_manifest.sh` (binds a binary hash to result files).

## Rebuild and re-verify (macOS)

1. Install Bend natively on your Mac: `curl -fsSL https://bend-lang.com/install.sh | sh`
   (needs Bend 2.0.34; `xcode-select --install` for clang). You must build
   on macOS — the Linux binary in our manifest will NOT run on a Mac.
2. Verify the source hash:
   `sha256sum mcp-blog.bend` → must start `07a60cbb`
3. Build (~5 min; set `TMPDIR` somewhere roomy if `/tmp` is small):
   `bend mcp-blog.bend -o medium/fresh/med_native_mcp1`
4. Run the probe (from this directory):
   `BOCHT_ROOT="$PWD" python3 tests/probe_mcp_final.py`
   Expect as the first stdout line: `RESULT: PASS=43 FAIL=0`
5. Confirm the manifest: `sha256sum medium/fresh/med_native_mcp1` → must
   start `c50db6f2` to match `manifest_2034.txt`. (Your build will differ —
   it's a macOS binary. What reproduces is exit 0 + `PASS=43 FAIL=0`, not the
   hash.)

## The interface (what the 43 tests exercise)

`POST /mcp` — JSON-RPC 2.0 / MCP Streamable HTTP, `Authorization: Bearer <key>`
(seven tools: `blog_create_post`, `blog_list_posts`, `blog_get_post`,
`blog_update_post`, `blog_publish_post`, `blog_unpublish_post`,
`blog_delete_post`), WAL-backed persistence with snapshot+replay.

## Honest limits

- Single-node. No replication, clustering, sharding, or consensus.
- WAL survives process death; power-loss durability is not guaranteed.
- Large MCP request bodies are slowish (~12s at 16 kB) due to Bend's
  character-scan overhead; the O(n²) algorithmic bottleneck is fixed.
- Bend's toolchain has been volatile (breaking changes in 2.0.27, 2.0.29,
  2.0.32, 2.0.34). This source is verified on 2.0.34 only.
