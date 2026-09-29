# REST clap endpoint also reads its count via jf_field_any -> jf_raw_go. Time it with a padded body.
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"adv.py") if False else __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
st,t=req({"title":"a","body":"b"},path="/v1/articles"); aid=json.loads(t)["id"]
for n in (8000,16000,32000):
    t0=time.time(); st,t=req(raw='{"count":1,"pad":"%s"}'%("x"*n),path=f"/v1/articles/{aid}/clap",timeout=120); print(f"clap +{n} pad: http={st} {time.time()-t0:.3f}s {t[:60]}",flush=True)
proc.kill()
