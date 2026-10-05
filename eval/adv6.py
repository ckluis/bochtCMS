exec(open("adv.py").read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
X="x"*16000
def t(label, **kw):
    t0=time.time(); st,txt=req(timeout=120, **kw); print(f"{label:55s} http={st} {time.time()-t0:6.2f}s  {txt[:70]!r}", flush=True)
t("tools/list with 16KB junk param (parse only)", payload={"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"pad":X}})
t("bogus tool, 16KB arg (parse + dispatch, no store)", payload={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"bogus","arguments":{"body":X}}})
t("create, empty title, 16KB body (validation fail)", payload={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"","body":X,"tags":[]}}})
t("create valid 16KB body (full path)", payload={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"ok","body":X,"tags":[]}}})
t("REST POST /v1/articles 16KB body", payload={"title":"rest","body":X}, path="/v1/articles")
proc.kill()
