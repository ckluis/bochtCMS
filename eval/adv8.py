exec(__import__("builtins").open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
ids=[call("blog_create_post",{"title":f"post{i}","body":"b","tags":[]})[2]["id"] for i in range(3)]
print("created", ids)
def lst(): return sorted(p["id"] for p in call("blog_list_posts",{"status":"all"})[2]["posts"])
print("before:", lst())
# Harmless-looking read whose arguments carry a "name" field (e.g. an author/display name)
st,t=req({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"arguments":{"id":ids[1],"name":"blog_delete_post"},"name":"blog_get_post"}})
print("get_post response:", t[:200])
print("after:", lst())
# More realistic: client sends name first, but arguments include a field called name
st,t=req({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"blog_get_post","arguments":{"id":ids[2],"name":"blog_delete_post"}}})
print("name-first get_post response:", t[:200]); print("after:", lst())
proc.kill()
