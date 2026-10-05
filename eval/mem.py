# Peak resident memory of the server across a fixed workload. BOCHT_BIN selects the binary.
exec(open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)),"adv.py")).read().split("R=[]")[0])
import resource
def rss(): return int(subprocess.run(["ps","-o","rss=","-p",str(proc.pid)],capture_output=True,text=True).stdout.strip() or 0)
shutil.rmtree(WD,ignore_errors=True); os.makedirs(WD); assert start()
peak=rss(); base=peak
for i in range(300):
    call("blog_create_post",{"title":f"p{i}","body":"x"*8000,"tags":["t"]}); peak=max(peak,rss()) if i%20==0 else peak
for i in range(30):
    call("blog_list_posts",{"status":"all"},timeout=60); peak=max(peak,rss())
for n in (16000,32000,60000):
    call("blog_create_post",{"title":"big","body":"y"*n,"tags":[]},timeout=60); peak=max(peak,rss())
print(json.dumps({"idle_kb":base,"peak_kb":peak,"end_kb":rss()})); proc.kill()
