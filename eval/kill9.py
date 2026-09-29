# Single acknowledged write, then SIGKILL, then restart: the post must be there.
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
ok=0
for i in range(20):
    st,j,p=call("blog_create_post",{"title":f"k9-{i}","body":"b","tags":["k9"]}); kid=(p or {}).get("id")
    assert kid, (st,j)
    os.kill(proc.pid, signal.SIGKILL); proc.wait(); assert start()
    _,gj,g=call("blog_get_post",{"id":kid})
    ok += (g or {}).get("title")==f"k9-{i}"
    time.sleep(0.2)
print(f"acked-then-SIGKILL survived: {ok}/20")
proc.kill()
