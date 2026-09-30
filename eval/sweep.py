# Create-post timing sweep for chart data. BOCHT_BIN selects binary; SIZES comma list. Prints JSON.
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
out={}
for n in [int(x) for x in os.environ["SIZES"].split(",")]:
    ts=[]
    for rep in range(int(os.environ.get("REPS","1"))):
        t0=time.time(); st,j,p=call("blog_create_post",{"title":"big","body":"x"*n,"tags":[]},timeout=300); ts.append(time.time()-t0)
        assert (p or {}).get("id"), (n,st)
    out[n]=round(min(ts),4); print(n, out[n], flush=True)
print("JSON", json.dumps(out)); proc.kill()
