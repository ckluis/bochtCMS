#!/usr/bin/env python3
"""Final MCP blog workstream probe (self-contained).

Starts its own server in a dedicated fresh workdir on :18081, obtains a
deterministic admin credential via MEDIUM_ADMIN_SECRET (which it sets
itself), runs the full 21-step sequence, restarts the server to verify WAL
replay persistence, then stops the exact :18081 listener PID (found via ss,
or lsof on macOS).

Stdout/stderr discipline: NOTHING is printed until the sole canonical first
line `RESULT: PASS=n FAIL=0`. Buffered diagnostics are dumped to stderr only
after that line.

Usage: probe_mcp_final.py   (run from ~/workspace/bocht/.test_runs/mcp-blog,
                             unpiped; binary must already be built)
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- config

HERE = os.path.dirname(os.path.abspath(__file__))
# Portability patch (source bundle 2026-09-29): allow overriding the project
# root via BOCHT_ROOT so the probe works outside the original repo layout.
BOCHT = os.environ.get("BOCHT_ROOT") or os.path.dirname(os.path.dirname(HERE))
BINARY = os.path.join(BOCHT, "medium", "fresh", "med_native_mcp1")
WORKDIR = os.path.join(HERE, "probe_wd")
BASE = "http://127.0.0.1:18081"
SECRET = "mcp-probe-deterministic-secret-20260929"       # test-only credential
START_TIMEOUT_S = 60
REQ_TIMEOUT_S = 15

# ---------------------------------------------------------------- buffering

DIAG = []          # buffered diagnostics, flushed to stderr AFTER the RESULT line
PASS = 0
FAIL = 0


def diag(msg):
    DIAG.append(msg)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        diag(f"ok: {name}")
    else:
        FAIL += 1
        diag(f"FAIL: {name} {detail}")


# ---------------------------------------------------------------- server control

_server_proc = None


def ss_listener_pid(port):
    """Return the PID of the exact :<port> listener via ss, or None.

    macOS has no `ss`; fall back to `lsof -ti :<port>` there. (Portability
    patch added for the source bundle 2026-09-29; the only change vs the
    original probe.)"""
    try:
        out = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=10
        ).stdout
    except FileNotFoundError:
        try:
            out = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True,
                timeout=10,
            ).stdout
        except Exception as e:
            diag(f"lsof failed: {e}")
            return None
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        return None
    except Exception as e:
        diag(f"ss failed: {e}")
        return None
    for line in out.splitlines():
        if re.search(rf":{port}\s", line):
            m = re.search(r"pid=(\d+)", line)
            if m:
                return int(m.group(1))
    return None


def wait_port_open(timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", 18081), timeout=1)
            s.close()
            return True
        except OSError:
            time.sleep(0.25)
    return False


def wait_port_closed(timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if ss_listener_pid(18081) is None:
            return True
        time.sleep(0.25)
    return False


def start_server():
    global _server_proc
    env = dict(os.environ)
    env["MEDIUM_ADMIN_SECRET"] = SECRET
    logf = open(os.path.join(WORKDIR, "server.log"), "ab")
    _server_proc = subprocess.Popen(
        [BINARY], cwd=WORKDIR, env=env, stdout=logf, stderr=subprocess.STDOUT
    )
    diag(f"server started pid={_server_proc.pid}")
    if not wait_port_open(START_TIMEOUT_S):
        diag("server did not open :18081 in time")
        return False
    return True


def stop_server():
    """Stop ONLY the exact :18081 listener PID identified via ss."""
    global _server_proc
    pid = ss_listener_pid(18081)
    if pid is None:
        diag("no :18081 listener to stop")
    else:
        diag(f"stopping :18081 listener pid={pid}")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not wait_port_closed(15):
            diag(f"pid={pid} ignored SIGTERM; SIGKILL")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            wait_port_closed(10)
    if _server_proc is not None:
        try:
            _server_proc.wait(timeout=10)
        except Exception:
            pass
        _server_proc = None


# ---------------------------------------------------------------- http

def mcp_request(payload=None, raw_body=None, token=SECRET, no_auth=False,
                path="/mcp", method="POST"):
    """Return (http_status, parsed_json_or_None, raw_text)."""
    body = raw_body if raw_body is not None else json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if not no_auth:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + path, data=body.encode(), headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=REQ_TIMEOUT_S) as r:
            text = r.read().decode()
            try:
                return r.status, (json.loads(text) if text.strip() else None), text
            except Exception:
                return r.status, None, text
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, (json.loads(text) if text.strip() else None), text
        except Exception:
            return e.code, None, text
    except Exception as e:
        diag(f"request exception: {e}")
        return -1, None, ""


def rpc(method, params=None, rpc_id=1):
    p = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        p["params"] = params
    return p


def tool_text(resp):
    """Extract the MCP text content and parse it as JSON."""
    try:
        text = (resp.get("result", {}).get("content") or [{}])[0].get("text", "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def tool_is_error(resp):
    return (resp or {}).get("result", {}).get("isError") is True


def err_code(resp):
    return (resp or {}).get("error", {}).get("code")


# ---------------------------------------------------------------- sequence

def main():
    global PASS, FAIL
    diag("probe start")
    if not os.path.isfile(BINARY):
        print("RESULT: PASS=0 FAIL=1")
        sys.stderr.write("probe abort: binary missing: %s\n" % BINARY)
        return 1

    # Fresh dedicated workdir.
    if os.path.isdir(WORKDIR):
        shutil.rmtree(WORKDIR)
    os.makedirs(WORKDIR, exist_ok=True)

    if not start_server():
        print("RESULT: PASS=0 FAIL=1")
        sys.stderr.write("probe abort: server did not start\n")
        for d in DIAG:
            sys.stderr.write(d + "\n")
        return 1

    rid = [20]

    def rpc_id():
        rid[0] += 1
        return rid[0]

    def call(tool, args):
        st, resp, raw = mcp_request(rpc("tools/call", {"name": tool, "arguments": args}, rpc_id()))
        return st, resp, raw

    try:
        # ---- 1. initialize ------------------------------------------------
        st, resp, _ = mcp_request(rpc("initialize", {"protocolVersion": "2025-06-18"}, rpc_id()))
        check("initialize http 200", st == 200, f"got {st}")
        res = (resp or {}).get("result", {})
        check("initialize protocolVersion", res.get("protocolVersion") == "2025-06-18")
        check("initialize serverInfo", res.get("serverInfo", {}).get("name") == "bocht-fresh-blog"
              and res.get("serverInfo", {}).get("version") == "0.1.0")

        # ---- 2. tools/list -------------------------------------------------
        st, resp, _ = mcp_request(rpc("tools/list", None, rpc_id()))
        check("tools/list http 200", st == 200, f"got {st}")
        tools = (resp or {}).get("result", {}).get("tools", [])
        names = {t.get("name") for t in tools}
        expected = {"blog_create_post", "blog_list_posts", "blog_get_post",
                    "blog_update_post", "blog_publish_post", "blog_unpublish_post",
                    "blog_delete_post"}
        check("tools/list has all seven", expected <= names, f"got {names}")
        for t in tools:
            if t.get("name") in expected:
                check(f"schema {t['name']}", t.get("inputSchema", {}).get("type") == "object")

        # ---- 3. create draft ----------------------------------------------
        st, resp, raw = call("blog_create_post",
                             {"title": "Hello MCP", "body": "First post body",
                              "tags": ["intro", "mcp"]})
        check("create http 200", st == 200, f"got {st} {raw[:160]}")
        check("create not isError", not tool_is_error(resp), f"got {raw[:160]}")
        post = tool_text(resp)
        pid = post.get("id", "")
        check("create returns id", isinstance(pid, str) and pid.startswith("p"), f"got {post}")
        check("create status draft", post.get("status") == "draft", f"got {post}")
        check("create tags array", post.get("tags") == ["intro", "mcp"], f"got {post.get('tags')}")

        # ---- 4. draft in draft list, not in published ----------------------
        st, resp, raw = call("blog_list_posts", {"status": "draft"})
        drafts = tool_text(resp).get("posts", [])
        check("draft in draft list", any(p.get("id") == pid for p in drafts), f"got {raw[:200]}")
        st, resp, raw = call("blog_list_posts", {"status": "published"})
        pubs = tool_text(resp).get("posts", [])
        check("draft excluded from published", not any(p.get("id") == pid for p in pubs))

        # ---- 5. get ---------------------------------------------------------
        st, resp, raw = call("blog_get_post", {"id": pid})
        got = tool_text(resp)
        check("get returns post", got.get("id") == pid and got.get("title") == "Hello MCP",
              f"got {raw[:200]}")

        # ---- 6. update ------------------------------------------------------
        st, resp, raw = call("blog_update_post",
                             {"id": pid, "title": "Hello MCP v2",
                              "tags": ["intro", "mcp", "v2"]})
        upd = tool_text(resp)
        check("update title", upd.get("title") == "Hello MCP v2", f"got {raw[:200]}")
        check("update tags", upd.get("tags") == ["intro", "mcp", "v2"],
              f"got {upd.get('tags')}")

        # ---- 7. publish -----------------------------------------------------
        st, resp, raw = call("blog_publish_post", {"id": pid})
        pub = tool_text(resp)
        check("publish status", pub.get("status") == "published", f"got {raw[:200]}")

        # ---- 8. in published list -------------------------------------------
        st, resp, raw = call("blog_list_posts", {"status": "published"})
        pubs = tool_text(resp).get("posts", [])
        check("published in published list", any(p.get("id") == pid for p in pubs))

        # ---- 9. unpublish ---------------------------------------------------
        st, resp, raw = call("blog_unpublish_post", {"id": pid})
        unpub = tool_text(resp)
        check("unpublish status", unpub.get("status") == "draft", f"got {raw[:200]}")

        # ---- 10. delete ------------------------------------------------------
        st, resp, raw = call("blog_delete_post", {"id": pid})
        dele = tool_text(resp)
        check("delete ok", dele.get("deleted") is True, f"got {raw[:200]}")

        # ---- 11. get deleted -> MCP tool error --------------------------------
        st, resp, raw = call("blog_get_post", {"id": pid})
        check("get deleted isError", tool_is_error(resp), f"got {raw[:200]}")

        # ---- 12. no Bearer token at all -> HTTP 401 ---------------------------
        st, resp, raw = mcp_request(rpc("initialize", None, rpc_id()), no_auth=True)
        check("missing token -> 401", st == 401, f"got {st} {raw[:120]}")

        # ---- 13. malformed JSON -> -32700 -------------------------------------
        st, resp, raw = mcp_request(raw_body="{not json")
        check("malformed JSON -> -32700", st == 200 and err_code(resp) == -32700,
              f"got http={st} {raw[:160]}")

        # ---- 14. valid JSON, not a JSON-RPC request -> -32600 -----------------
        st, resp, raw = mcp_request({"foo": "bar"})
        check("invalid JSON-RPC -> -32600", st == 200 and err_code(resp) == -32600,
              f"got http={st} {raw[:160]}")

        # ---- 15. unknown method -> -32601 --------------------------------------
        st, resp, raw = mcp_request(rpc("bogus/method", None, rpc_id()))
        check("unknown method -> -32601", st == 200 and err_code(resp) == -32601,
              f"got http={st} {raw[:160]}")

        # ---- 16. invalid params -> -32602 --------------------------------------
        st, resp, raw = mcp_request(rpc("tools/call", "not-an-object", rpc_id()))
        check("invalid params -> -32602", st == 200 and err_code(resp) == -32602,
              f"got http={st} {raw[:160]}")

        # ---- 17. unknown tool -> MCP tool error ---------------------------------
        st, resp, raw = call("bogus_tool", {})
        check("unknown tool isError", st == 200 and tool_is_error(resp), f"got {raw[:200]}")

        # ---- 18. existing article CRUD smoke (REST, additive) -------------------
        st, resp, raw = mcp_request({"title": "rest smoke", "body": "b"},
                                    path="/v1/articles")
        ok_create = st in (200, 201)
        check("article create REST", ok_create, f"got http={st} {raw[:160]}")
        aid = ""
        try:
            aid = (resp or {}).get("id") or (resp or {}).get("article", {}).get("id") or ""
        except Exception:
            pass
        if aid:
            st2, _, _ = mcp_request(path=f"/v1/articles/{aid}", method="GET")
            check("article get REST", st2 == 200, f"got http={st2}")
        else:
            check("article get REST", False, "no article id returned")

        # ---- 19. existing auth-rejection smoke (REST, no token) ------------------
        st, _, raw = mcp_request(path="/v1/articles/x", method="GET", no_auth=True)
        check("article no-auth rejected", st in (401, 403), f"got http={st}")

        # ---- 20. notifications/initialized -> 202 empty ---------------------------
        st, resp, raw = mcp_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
        check("notifications/initialized 202", st == 202, f"got http={st} {raw[:120]}")
        check("notifications/initialized empty body", raw.strip() == "", f"got {raw[:120]!r}")

        # ---- 21. restart: WAL replay persistence -----------------------------------
        st, resp, raw = call("blog_create_post",
                             {"title": "Persist me", "body": "wal replay check",
                              "tags": ["persist"]})
        ppersist = tool_text(resp)
        persist_id = ppersist.get("id", "")
        check("restart setup: post created", bool(persist_id), f"got {raw[:200]}")

        stop_server()
        diag("server stopped for restart test")
        if not start_server():
            check("restart: server came back", False, "did not reopen :18081")
        else:
            check("restart: server came back", True)
            # Same credential must still work (keys replay from WAL).
            st, resp, _ = mcp_request(rpc("initialize", {"protocolVersion": "2025-06-18"},
                                          rpc_id()))
            check("restart: initialize still auths", st == 200, f"got {st}")
            st, resp, raw = call("blog_get_post", {"id": persist_id})
            got2 = tool_text(resp)
            check("restart: post survived WAL replay",
                  got2.get("id") == persist_id and got2.get("title") == "Persist me"
                  and got2.get("tags") == ["persist"],
                  f"got {raw[:200]}")
            # Draft-list visibility after replay too.
            st, resp, raw = call("blog_list_posts", {"status": "draft"})
            drafts2 = tool_text(resp).get("posts", [])
            check("restart: post in draft list after replay",
                  any(p.get("id") == persist_id for p in drafts2))
    finally:
        stop_server()

    # Canonical first line on stdout, then buffered diagnostics to stderr.
    print(f"RESULT: PASS={PASS} FAIL={FAIL}", flush=True)
    for d in DIAG:
        sys.stderr.write(d + "\n")
    sys.stderr.flush()
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
