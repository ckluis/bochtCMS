exec(open("adv.py").read().split("R=[]")[0])
def fresh():
    global proc
    if proc and proc.poll() is None: proc.kill(); proc.wait()
    shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
def health(): 
    st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list"},timeout=5); return st
# titles alone
fresh()
for v in ['He said "hi" \\ ok',"Café 日本語","Launch 🎉🚀","<b>x</b> &"]:
    st,j,p=call("blog_create_post",{"title":v,"body":"b","tags":[]})
    ok=(p or {}).get("id"); g=call("blog_get_post",{"id":ok})[2] if ok else {}
    print("title",repr(v),"->", "roundtrip OK" if g.get("title")==v else (json.dumps(j)[:150] if isinstance(j,dict) else j))
for v in ["two words","café","UPPER","a-b_c"]:
    st,j,p=call("blog_create_post",{"title":"t","body":"b","tags":[v]}); print("tag",repr(v),"->","ok" if (p or {}).get("id") else json.dumps(j)[:120])
# find the size threshold and whether the server wedges
for n in (32000, 40000, 50000, 55000, 60000, 64000):
    fresh()
    t0=time.time(); st,j,p=call("blog_create_post",{"title":"big","body":"x"*n,"tags":[]},timeout=10); dt=time.time()-t0
    h=[health() for _ in range(3)]
    print(f"body={n}: create http={st} ok={bool((p or {}).get('id'))} {dt:.1f}s | alive={alive()} health after={h}", flush=True)
    if st==-1:
        time.sleep(20); print("   after 20s: health", health(), "alive", alive(), flush=True)
        # does it hang on the socket itself? raw request
        body=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"big","body":"x"*n,"tags":[]}}}).encode()
        print("   request bytes:", len(body))
        subprocess.run(["sh","-c",f"ps -o pid,stat,%cpu,rss,command -p {proc.pid}"])
        print("   server.log tail:", open(WD+"/server.log").read()[-600:])
        break
proc.kill()
