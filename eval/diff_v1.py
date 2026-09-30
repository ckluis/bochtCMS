# Differential test: replay one request script against two binaries and diff every response.
# Usage: python3 diff_v1.py <reference_bin> <candidate_bin>
import json, os, re, shutil, socket, subprocess, sys, time
HERE=os.path.dirname(os.path.abspath(__file__)); SECRET="diff-secret"
def run(binary):
    wd=os.path.join(HERE,"wd_diff"); shutil.rmtree(wd,ignore_errors=True); os.makedirs(wd)
    p=subprocess.Popen([binary],cwd=wd,env=dict(os.environ,MEDIUM_ADMIN_SECRET=SECRET),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(200):
        try: socket.create_connection(("127.0.0.1",18081),timeout=0.5).close(); break
        except OSError: time.sleep(0.1)
    out=[]
    def send(raw, path="/mcp", auth=True):
        s=socket.create_connection(("127.0.0.1",18081),timeout=30)
        body=raw.encode()
        head=f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n"
        if auth: head+=f"Authorization: Bearer {SECRET}\r\n"
        s.sendall(head.encode()+b"\r\n"+body); data=b""
        while True:
            c=s.recv(65536)
            if not c: break
            data+=c
        s.close()
        txt=data.decode("utf-8","replace"); status=txt.split(" ",2)[1] if " " in txt else "?"
        bodytxt=txt.split("\r\n\r\n",1)[1] if "\r\n\r\n" in txt else txt
        bodytxt=re.sub(r'(\\?"(created_at|updated_at|ts|at)\\?"\s*:\s*)\d+', r'\1T', bodytxt)
        out.append((raw[:90], status, bodytxt)); return bodytxt
    ids=['1','0','42','-7','1.5','2e3','-1.25E-2','null','true','false','"abc"','"a\\"b"','""','123456789012','  9  ','\n5\n']
    for i in ids:
        send('{"jsonrpc":"2.0","id":%s,"method":"tools/list"}' % i)
        send('{"jsonrpc":"2.0","method":"tools/list","id":%s}' % i)          # id last: terminated by }
        send('{"jsonrpc":"2.0","method":"tools/list","id":%s }' % i)
        send('{"jsonrpc":"2.0","id":%s,"method":"bogus"}' % i)
    send('{"jsonrpc":"2.0","method":"tools/list"}')                           # no id
    send('{"jsonrpc":"2.0","id":1x,"method":"tools/list"}')                   # junk id
    send('{"jsonrpc":"2.0","id":[1],"method":"tools/list"}')
    send('{"jsonrpc":"2.0","id":{"a":1},"method":"tools/list"}')
    send('{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"t","body":"%s","tags":["a"]}}}' % ("x"*20000))
    send('{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"arguments":{"id":"p1","name":"blog_delete_post"},"name":"blog_get_post"}}')
    send('{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"_meta":{"title":"META"},"name":"blog_create_post","arguments":{"title":"real","body":"b","tags":[]}}}')
    send('{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"blog_create_post","arguments":{"title":"t","body":"b","tags":"notarray"}}}')
    send('{"jsonrpc":"2.0","id":11,"method":"initialize","params":"notobj"}')
    send('{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"arguments":{"name":"blog_list_posts"}}}')
    send('{"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"blog_create_post","arguments":"nope"}}')
    send('{"jsonrpc":"2.0","id":15,"method":"tools/call","params":{"name":"blog_create_post","arguments":["title","x"]}}')
    send('{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"blog_list_posts","arguments":{"status":"all"}}}')
    a=send('{"title":"art","body":"b"}', path="/v1/articles")
    aid=json.loads(a).get("id","a1")
    for c in ['{"count":3}','{"count":"4"}','{"count": 5 }','{"count":-1}','{"count":1.5}','{"count":null}','{}','{"count":3','{"count":99999999999}','{"x":1,"count":2}']:
        send(c, path=f"/v1/articles/{aid}/clap")
    send('{"meta":{"title":"NESTED"},"title":"real","body":"b"}', path="/v1/articles")
    send('{"jsonrpc":"2.0","id":1,"method":"tools/list"}', auth=False)
    p.kill(); p.wait(); shutil.rmtree(wd,ignore_errors=True)
    return out
ref=run(sys.argv[1]); cand=run(sys.argv[2])
diffs=[(r,c) for r,c in zip(ref,cand) if r!=c]
print(f"{len(ref)} requests, {len(diffs)} differences")
for r,c in diffs[:20]:
    print("REQ ", r[0]); print("  ref ", r[1], r[2][:160]); print("  cand", c[1], c[2][:160])
sys.exit(1 if diffs or len(ref)!=len(cand) else 0)
