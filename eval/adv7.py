# v1-vs-v2 regression + perf comparison. Run with BOCHT_BIN=<binary>.
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"adv.py") if False else __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
def rpc_raw(params, method="tools/call", rid=1):
    st,t=req({"jsonrpc":"2.0","id":rid,"method":method,"params":params}); 
    try: return st, json.loads(t)
    except Exception: return st, t
def inner(j):
    try: return json.loads(j["result"]["content"][0]["text"])
    except Exception: return None
def show(label, v): print(f"{label:62s} {json.dumps(v)[:170] if not isinstance(v,str) else v[:170]}", flush=True)
# seed
_,_,p=call("blog_create_post",{"title":"seed","body":"b","tags":["t"]}); seed=p["id"]
# a. key order: arguments before name
st,j=rpc_raw({"arguments":{"title":"order","body":"b","tags":[]},"name":"blog_create_post"}); show("a. arguments-before-name create", inner(j) or j)
# b. 'name' key inside arguments, placed first
st,j=rpc_raw({"arguments":{"name":"blog_delete_post","id":seed},"name":"blog_get_post"}); show("b. get_post w/ args.name=blog_delete_post -> tool run", inner(j) or j)
_,gj,g=call("blog_get_post",{"id":seed}); show("   ...seed post still exists?", "NO (deleted)" if (isinstance(gj,dict) and gj.get("result",{}).get("isError")) else "YES")
# c. _meta with title before arguments
st,j=rpc_raw({"_meta":{"title":"META-TITLE","progressToken":1},"name":"blog_create_post","arguments":{"title":"real","body":"b","tags":[]}}); show("c. params._meta.title + args.title=real -> stored title", (inner(j) or {}).get("title", j))
# e. body text containing an escaped "title": before real title
st,j=rpc_raw({"name":"blog_create_post","arguments":{"body":"x \"title\":\"HACK\" y","title":"real","tags":[]}}); show("e. body contains escaped \"title\":\"HACK\" -> stored title", (inner(j) or {}).get("title", j))
# f. arguments not an object
st,j=rpc_raw({"name":"blog_create_post","arguments":"nope"}); show("f. arguments=\"nope\"", j)
st,j=rpc_raw({"name":"blog_create_post","arguments":["title","x"]}); show("f2. arguments=[array]", j)
# g. malformed tags
st,j=rpc_raw({"name":"blog_create_post","arguments":{"title":"t","body":"b","tags":"notarray"}}); show("g. tags=\"notarray\"", inner(j) or j)
st,j=rpc_raw({"name":"blog_create_post","arguments":{"title":"t","body":"b","tags":[1,2]}}); show("g2. tags=[1,2]", inner(j) or j)
# h. params not an object
st,j=rpc_raw("notobj"); show("h. params=\"notobj\"", j)
st,j=rpc_raw("notobj", method="initialize"); show("h2. initialize params=\"notobj\"", j)
# i. tool name only inside arguments (no params.name)
st,j=rpc_raw({"arguments":{"name":"blog_list_posts"}}); show("i. no params.name, args.name=blog_list_posts", (lambda x: {"posts":len(x.get("posts",[]))} if isinstance(x,dict) and "posts" in x else x)(inner(j) or j))
# j. REST nested-key regression
st,t=req({"meta":{"title":"NESTED"},"title":"real","body":"b"},path="/v1/articles")
try:
    aid=json.loads(t)["id"]; st2,t2=req(None,path=f"/v1/articles/{aid}",method="GET"); show("j. REST {meta:{title:NESTED},title:real} -> stored", json.loads(t2).get("title", t2))
except Exception as e: show("j. REST nested", (st,t[:150]))
# perf
for n in (4000, 8000, 16000, 32000):
    t0=time.time(); st,j,p=call("blog_create_post",{"title":"big","body":"x"*n,"tags":[]},timeout=200); dt=time.time()-t0
    print(f"perf create {n:>6}: http={st} ok={bool((p or {}).get('id'))} {dt:7.2f}s", flush=True)
    if n==16000 and (p or {}).get("id"):
        big=p["id"]
        t0=time.time(); st,j,p2=call("blog_update_post",{"id":big,"body":"y"*n},timeout=200); print(f"perf update {n:>6}: http={st} ok={(p2 or {}).get('body','')[:1]=='y'} {time.time()-t0:7.2f}s", flush=True)
        t0=time.time(); st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"pad":"x"*n}},timeout=200); print(f"perf tools/list +{n} pad: http={st} {time.time()-t0:7.2f}s", flush=True)
    if dt>60: break
proc.kill()
