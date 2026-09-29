# Timing sweep for POST /mcp (create, update, tools/list pad) and REST. BOCHT_BIN selects the binary.
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
sizes=[int(x) for x in os.environ.get("SIZES","4000,8000,16000,32000,60000").split(",")]
for n in sizes:
    t0=time.time(); st,j,p=call("blog_create_post",{"title":"big","body":"x"*n,"tags":["t"]},timeout=120); c=time.time()-t0
    pid=(p or {}).get("id")
    t0=time.time(); st2,j2,p2=call("blog_update_post",{"id":pid,"body":"y"*n},timeout=120); u=time.time()-t0
    t0=time.time(); st3,_=req({"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"pad":"x"*n}},timeout=120); l=time.time()-t0
    t0=time.time(); st4,_=req({"title":"r","body":"x"*n},path="/v1/articles",timeout=120); r=time.time()-t0
    ok = bool(pid) and (p2 or {}).get("body")==("y"*n)
    print(f"{n:>6} B  create {c:6.3f}s  update {u:6.3f}s  tools/list {l:6.3f}s  REST {r:6.3f}s  roundtrip_ok={ok}", flush=True)
proc.kill()
