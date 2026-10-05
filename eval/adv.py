import json, os, socket, subprocess, sys, time, signal, urllib.request, urllib.error, concurrent.futures as cf, shutil
BIN=os.environ.get("BOCHT_BIN",os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","medium","fresh","med_native_mcp1"))
WD=os.path.dirname(os.path.abspath(__file__))+"/wd"
SECRET="adv-secret-123"
BASE="http://127.0.0.1:18081"
proc=None
def start():
    global proc
    env=dict(os.environ, MEDIUM_ADMIN_SECRET=SECRET)
    proc=subprocess.Popen([BIN],cwd=WD,env=env,stdout=open(WD+"/server.log","ab"),stderr=subprocess.STDOUT)
    for _ in range(200):
        try: socket.create_connection(("127.0.0.1",18081),timeout=0.5).close(); return True
        except OSError: time.sleep(0.1)
    return False
def alive(): return proc.poll() is None
def req(payload=None, raw=None, token=SECRET, path="/mcp", method="POST", headers=None, timeout=15):
    body=(raw if raw is not None else json.dumps(payload)).encode() if (raw is not None or payload is not None) else None
    h={"Content-Type":"application/json"}
    if token is not None: h["Authorization"]="Bearer "+token
    if headers: h.update(headers)
    r=urllib.request.Request(BASE+path,data=body,headers=h,method=method)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x: t=x.read().decode("utf-8","replace"); return x.status,t
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8","replace")
    except Exception as e: return -1, repr(e)
def call(tool,args,**k):
    st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":tool,"arguments":args}},**k)
    try:
        j=json.loads(t); inner=j.get("result",{}).get("content",[{}])[0].get("text","")
        return st,j,(json.loads(inner) if inner else {})
    except Exception as e: return st,t,None
def raw_http(data, timeout=5):
    s=socket.create_connection(("127.0.0.1",18081),timeout=timeout)
    s.sendall(data); out=b""
    try:
        while True:
            c=s.recv(65536)
            if not c: break
            out+=c
            if len(out)>200000: break
    except Exception as e: out+=b"<<"+repr(e).encode()+b">>"
    s.close(); return out[:300]
R=[]
def rec(name, ok, detail=""): R.append((("PASS" if ok else "FAIL"),name,str(detail)[:300])); print(("PASS" if ok else "FAIL"),name,str(detail)[:300],flush=True)

shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD)
assert start()

# auth
st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},token="wrong-token"); rec("wrong token -> 401", st==401, (st,t[:100]))
st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},token=""); rec("empty bearer -> 401", st==401, (st,t[:100]))
st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},token=SECRET+"x"); rec("secret+suffix -> 401", st==401, (st,t[:100]))
st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},token=SECRET[:-1]); rec("secret prefix -> 401", st==401, (st,t[:100]))

# unicode / escaping roundtrip
weird={"title":'Quote " back\\slash \n newline \t tab é 日本 🎉 \u0001','body':'</script><b>x</b>   end',"tags":["a,b","\"q\"","ünï"]}
st,j,p=call("blog_create_post",weird)
pid=(p or {}).get("id")
st,j,g=call("blog_get_post",{"id":pid})
rec("unicode/escape roundtrip title", g and g.get("title")==weird["title"], (g or j) and repr((g or {}).get("title")))
rec("unicode/escape roundtrip body", g and g.get("body")==weird["body"], repr((g or {}).get("body")))
rec("unicode/escape roundtrip tags", g and g.get("tags")==weird["tags"], repr((g or {}).get("tags")))
# \u escapes in raw JSON input
rawbody='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"\\u00e9\\ud83c\\udf89","body":"b","tags":[]}}}'
st,t=req(raw=rawbody)
try:
    pid2=json.loads(json.loads(t)["result"]["content"][0]["text"])["id"]; _,_,g2=call("blog_get_post",{"id":pid2})
    rec("\\u escape + surrogate pair decoded", g2.get("title")=="é🎉", repr(g2.get("title")))
except Exception as e: rec("\\u escape + surrogate pair decoded", False, (st,t[:200]))

# type confusion
st,j,p=call("blog_create_post",{"title":123,"body":"b","tags":[]}); rec("title as number rejected", isinstance(j,dict) and (j.get("result",{}).get("isError") or "error" in j), json.dumps(j)[:200] if isinstance(j,dict) else j)
st,j,p=call("blog_create_post",{"title":"t","body":"b","tags":"notarray"}); rec("tags as string rejected", isinstance(j,dict) and (j.get("result",{}).get("isError") or "error" in j), json.dumps(j)[:200] if isinstance(j,dict) else j)
st,j,p=call("blog_create_post",{"body":"b"}); rec("missing title rejected", isinstance(j,dict) and (j.get("result",{}).get("isError") or "error" in j), json.dumps(j)[:200] if isinstance(j,dict) else j)
st,j,p=call("blog_create_post",{"title":"","body":"","tags":[]}); rec("empty title (info)", True, json.dumps(j)[:200] if isinstance(j,dict) else j)
st,j,p=call("blog_update_post",{"id":"p999999","title":"x"}); rec("update missing -> isError", isinstance(j,dict) and j.get("result",{}).get("isError"), json.dumps(j)[:200] if isinstance(j,dict) else j)
st,j,p=call("blog_publish_post",{"id":"../../etc/passwd"}); rec("path-ish id -> isError", isinstance(j,dict) and j.get("result",{}).get("isError"), json.dumps(j)[:200] if isinstance(j,dict) else j)
st,j,p=call("blog_list_posts",{"status":"bogus"}); rec("list bogus status (info)", True, json.dumps(j)[:200] if isinstance(j,dict) else j)
# deep nesting
deep='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"d","body":"b","tags":[],"x":'+'['*5000+']'*5000+'}}}'
st,t=req(raw=deep); rec("5000-deep nested JSON: server survives", alive(), (st,t[:120]))
# batch
st,t=req(raw='[{"jsonrpc":"2.0","id":1,"method":"tools/list"}]'); rec("JSON-RPC batch (info)", True, (st,t[:150]))
# id types
st,t=req({"jsonrpc":"2.0","id":"abc","method":"tools/list"}); rec("string id echoed", '"id":"abc"' in t.replace(" ",""), t[:120])
st,t=req({"jsonrpc":"2.0","id":None,"method":"tools/list"}); rec("null id (info)", True, (st,t[:120]))

# sizes
for kb in (64, 256, 1024, 4096):
    body="x"*(kb*1024)
    t0=time.time(); st,j,p=call("blog_create_post",{"title":f"big{kb}","body":body,"tags":[]},timeout=60); dt=time.time()-t0
    ok = isinstance(p,dict) and p.get("id")
    if ok:
        _,_,g=call("blog_get_post",{"id":p["id"]},timeout=60); ok = g.get("body")==body
    rec(f"{kb}KB body create+roundtrip", bool(ok), f"http={st} {dt:.2f}s alive={alive()} {(json.dumps(j)[:120] if isinstance(j,dict) else str(j)[:120]) if not ok else ''}")
    if not alive(): break

# malformed HTTP
if alive():
    for name,data in [("no CRLF garbage",b"GARBAGE\r\n\r\n"),
                      ("Content-Length lies (bigger)",b"POST /mcp HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer "+SECRET.encode()+b"\r\nContent-Length: 100\r\n\r\n{}"),
                      ("negative Content-Length",b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Length: -5\r\n\r\n"),
                      ("huge Content-Length",b"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Length: 99999999999999999999\r\n\r\n"),
                      ("64KB header",b"GET / HTTP/1.1\r\nHost: x\r\nX-A: "+b"a"*65536+b"\r\n\r\n"),
                      ("chunked body",b"POST /mcp HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer "+SECRET.encode()+b"\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n"),
                      ("null bytes",b"POST /mcp\x00 HTTP/1.1\r\n\r\n")]:
        try: out=raw_http(data, timeout=5)
        except Exception as e: out=repr(e).encode()
        time.sleep(0.2)
        rec(f"malformed HTTP: {name} -> still alive", alive(), out[:100])
        if not alive(): break

# slowloris-ish: open idle connections, then check service
if alive():
    socks=[]
    for i in range(200):
        try: socks.append(socket.create_connection(("127.0.0.1",18081),timeout=2))
        except Exception as e: break
    t0=time.time(); st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},timeout=10); dt=time.time()-t0
    rec(f"serves while {len(socks)} idle conns open", st==200, f"http={st} {dt:.2f}s")
    for s in socks: s.close()
    time.sleep(1)

# concurrency + throughput
if alive():
    def one(i):
        st,j,p=call("blog_create_post",{"title":f"c{i}","body":"b","tags":[]}); return isinstance(p,dict) and bool(p.get("id")), (p or {}).get("id")
    t0=time.time()
    with cf.ThreadPoolExecutor(32) as ex: res=list(ex.map(one,range(500)))
    dt=time.time()-t0; ids=[r[1] for r in res if r[0]]
    rec("500 concurrent creates all succeed", len(ids)==500, f"{len(ids)}/500 ok in {dt:.2f}s ({500/dt:.0f} req/s)")
    rec("concurrent creates -> unique ids", len(set(ids))==len(ids), f"{len(set(ids))} unique of {len(ids)}")
    t0=time.time()
    for i in range(200): req({"jsonrpc":"2.0","id":1,"method":"tools/list"})
    dt=time.time()-t0; rec("sequential tools/list latency (info)", True, f"{200/dt:.0f} req/s, {dt/200*1000:.1f} ms avg")
    t0=time.time(); st,j,p=call("blog_list_posts",{}); dt=time.time()-t0
    rec("list all posts (info)", True, f"{len((p or {}).get('posts',[]))} posts in {dt*1000:.0f} ms, {len(json.dumps(j))} bytes")

# rate limit probe
if alive():
    codes={}
    for i in range(300):
        st,_=req({"jsonrpc":"2.0","id":1,"method":"tools/list"}); codes[st]=codes.get(st,0)+1
    rec("rate limit on 300 rapid requests (info)", True, codes)

# kill -9 durability
if alive():
    st,j,p=call("blog_create_post",{"title":"survive-kill9","body":"b","tags":["k9"]}); kid=(p or {}).get("id")
    os.kill(proc.pid, signal.SIGKILL); proc.wait()
    ok=start()
    _,_,g=call("blog_get_post",{"id":kid}) if ok else (0,0,{})
    rec("post survives SIGKILL right after ack", ok and (g or {}).get("title")=="survive-kill9", g)
    _,_,lst=call("blog_list_posts",{})
    rec("all posts after SIGKILL restart (info)", True, f"{len((lst or {}).get('posts',[]))} posts")
    # kill -9 during a burst of writes
    def w(i): return call("blog_create_post",{"title":f"burst{i}","body":"b","tags":[]})
    acked=[]
    with cf.ThreadPoolExecutor(8) as ex:
        futs=[ex.submit(w,i) for i in range(400)]
        time.sleep(0.3); os.kill(proc.pid, signal.SIGKILL)
        for f in futs:
            try:
                st,j,p=f.result()
                if isinstance(p,dict) and p.get("id"): acked.append(p["id"])
            except Exception: pass
    proc.wait(); ok=start()
    lost=[]
    for i in acked:
        _,_,g=call("blog_get_post",{"id":i})
        if not (g or {}).get("id"): lost.append(i)
    rec("acked writes survive SIGKILL mid-burst", ok and not lost, f"acked={len(acked)} lost={len(lost)} {lost[:5]}")
    # corrupt the tail of the newest WAL segment
    proc.send_signal(signal.SIGTERM); proc.wait()
    files=[]
    for root,_,fs in os.walk(WD):
        for f in fs: files.append(os.path.join(root,f))
    print("WORKDIR files:", sorted((os.path.relpath(f,WD),os.path.getsize(f)) for f in files)[:40], flush=True)

print("SUMMARY", sum(1 for r in R if r[0]=="PASS"), "pass /", sum(1 for r in R if r[0]=="FAIL"), "fail")
if proc and alive(): proc.terminate()
