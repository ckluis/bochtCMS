exec(open("adv.py").read().split("R=[]")[0])
R=[]
def rec(n,ok,d=""): print(("PASS" if ok else "FAIL"),n,str(d)[:260],flush=True)
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
cases={"quotes+backslash":'He said "hi" \\ ok', "accents+CJK":"Café 日本語", "emoji":"Launch 🎉🚀", "html":"<b>x</b> & <script>", "newline":"a\nb", "tab":"a\tb"}
for k,v in cases.items():
    st,j,p=call("blog_create_post",{"title":v,"body":v,"tags":[v]})
    if not (p or {}).get("id"): rec(f"title={k}", False, json.dumps(j)[:200] if isinstance(j,dict) else j); 
    else:
        _,_,g=call("blog_get_post",{"id":p["id"]}); rec(f"title={k} roundtrip", g.get("title")==v and g.get("tags")==[v], (g.get("title"),g.get("tags")))
    for field in ("body",):
        st,j,p=call("blog_create_post",{"title":"t","body":v+" \u0001   end","tags":[]})
        if (p or {}).get("id"):
            _,_,g=call("blog_get_post",{"id":p["id"]}); rec(f"body={k}+ctrl roundtrip", g.get("body")==v+" \u0001   end", repr(g.get("body")))
        else: rec(f"body={k}+ctrl", False, json.dumps(j)[:200] if isinstance(j,dict) else j)
# max body size that fits
for n in (30000, 60000, 65000):
    st,j,p=call("blog_create_post",{"title":"big","body":"x"*n,"tags":[]}); rec(f"{n}-char body", bool((p or {}).get("id")), st)
# 30000 non-ASCII chars (utf8 bytes 3x)
st,j,p=call("blog_create_post",{"title":"big","body":"é"*20000,"tags":[]}); rec("20000 é body (40KB utf8, 120KB as \\u escapes?)", bool((p or {}).get("id")), (st, json.dumps(j)[:150] if isinstance(j,dict) else j))
time.sleep(3)
# kill -9 right after single ack
st,j,p=call("blog_create_post",{"title":"survive-kill9","body":"b","tags":["k9"]}); kid=(p or {}).get("id"); print("created",kid,st)
os.kill(proc.pid, signal.SIGKILL); proc.wait(); start()
_,_,g=call("blog_get_post",{"id":kid}); rec("post survives SIGKILL right after ack", (g or {}).get("title")=="survive-kill9", g)
# rate limiter behavior: who gets limited?
codes={}
for i in range(400):
    st,_,_=call("blog_list_posts",{"status":"all"}); codes[st]=codes.get(st,0)+1
rec("400 rapid list calls status codes", True, codes)
st,t=req(None,path="/help",method="GET",token=None); rec("GET /help", True, (st,t[:300]))
proc.terminate()
