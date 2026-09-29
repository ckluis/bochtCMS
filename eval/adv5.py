exec(open("adv.py").read().split("R=[]")[0])
import threading
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
body=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"t","body":"x"*30000,"tags":[]}}})
for label,tok in (("NO token",None),("WRONG token","nope")):
    r={}
    def go():
        t0=time.time(); r['st']=req(raw=body,token=tok,timeout=120)[0]; r['t']=time.time()-t0
    th=threading.Thread(target=go); th.start(); time.sleep(0.3)
    t0=time.time(); st,_=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},timeout=120); d=time.time()-t0
    th.join(); print(f"{label}: 30KB junk -> http={r['st']} in {r['t']:.2f}s; concurrent legit tools/list waited {d:.2f}s", flush=True)
# unauth: 30KB of garbage that is not JSON
raw_junk="{"+"a"*30000
r={}
def go2():
    t0=time.time(); r['st']=req(raw=raw_junk,token=None,timeout=120)[0]; r['t']=time.time()-t0
th=threading.Thread(target=go2); th.start(); time.sleep(0.3)
t0=time.time(); st,_=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},timeout=120); d=time.time()-t0
th.join(); print(f"NO token, 30KB non-JSON -> http={r['st']} in {r['t']:.2f}s; legit waited {d:.2f}s")
proc.kill()
