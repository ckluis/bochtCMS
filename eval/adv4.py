exec(open("adv.py").read().split("R=[]")[0])
import threading
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
for n in (1000, 2000, 4000, 8000, 16000, 24000, 32000, 48000, 60000):
    t0=time.time(); st,j,p=call("blog_create_post",{"title":"big","body":"x"*n,"tags":[]},timeout=180); dt=time.time()-t0
    print(f"body={n:>6}: http={st} ok={bool((p or {}).get('id'))} {dt:7.2f}s", flush=True)
    if dt>100: break
# does a slow request block others?
res={}
def slow(): 
    t0=time.time(); res['slow']=call("blog_create_post",{"title":"big","body":"x"*32000,"tags":[]},timeout=180)[0]; res['slow_t']=time.time()-t0
th=threading.Thread(target=slow); th.start(); time.sleep(0.5)
t0=time.time(); st,_=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},timeout=180); print(f"tools/list while 32KB create in flight: http={st} took {time.time()-t0:.2f}s", flush=True)
th.join(); print("slow create:",res)
# GET of the big post: is read also slow?
_,_,lst=call("blog_list_posts",{"status":"all"},timeout=180)
big=[p for p in (lst or {}).get("posts",[])]
print("posts:",len(big))
t0=time.time(); st,j,p=call("blog_list_posts",{"status":"all"},timeout=180); print(f"list with big posts: {time.time()-t0:.2f}s bytes={len(json.dumps(j))}")
proc.kill()
