import argparse,json
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlparse,parse_qs
from reader import Backup

PAGE='''<!doctype html><meta charset=utf-8><title>Duplicati Fast Restore</title><style>body{font:15px system-ui;max-width:1000px;margin:35px auto;padding:12px}input,button,select{padding:8px;margin:6px}td{border-bottom:1px solid #ddd;padding:7px}</style><h1>Duplicati Fast Restore</h1><select id=v></select><input id=q placeholder="Search paths"><button onclick=load()>Search</button><table id=t></table><p>Destination: <input id=d size=55 placeholder="/tmp/recovered"><button onclick=restore()>Restore selected</button></p><pre id=status></pre><script>
async function api(url,opts){let r=await fetch(url,opts),j=await r.json();if(!r.ok)throw Error(j.error);return j}
async function init(){let x=await api('/snapshots');v.innerHTML=x.map(s=>'<option value="'+s.id+'">'+s.volume+'</option>').join('');await load()}
async function load(){try{let x=await api('/files?version='+v.value+'&q='+encodeURIComponent(q.value));t.innerHTML='';for(let f of x){let tr=document.createElement('tr'),td=document.createElement('td'),c=document.createElement('input');c.type='checkbox';c.value=f.path;td.append(c);tr.append(td);for(let y of [f.path,f.size]){td=document.createElement('td');td.textContent=y;tr.append(td)}t.append(tr)}}catch(e){status.textContent=e.message}}
async function restore(){try{let paths=[...document.querySelectorAll('input[type=checkbox]:checked')].map(c=>c.value);status.textContent=JSON.stringify(await api('/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:+v.value,paths,destination:d.value})}),null,2)}catch(e){status.textContent=e.message}}
init()</script>'''
def web(db,port):
 class Handler(BaseHTTPRequestHandler):
  def send(self,obj,code=200,html=False):
   data=(obj if html else json.dumps(obj)).encode()
   self.send_response(code);self.send_header('Content-Type','text/html' if html else 'application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  def do_GET(self):
   try:
    u=urlparse(self.path);q=parse_qs(u.query)
    if u.path=='/':return self.send(PAGE,html=True)
    if u.path=='/snapshots':return self.send(db.snapshots())
    if u.path=='/files':return self.send(db.list(int(q['version'][0]),q.get('q',[''])[0]))
    return self.send({'error':'Not found'},404)
   except Exception as e:self.send({'error':str(e)},400)
  def do_POST(self):
   try:
    if self.path!='/restore':return self.send({'error':'Not found'},404)
    length=int(self.headers.get('Content-Length','0'))
    if length>1000000:return self.send({'error':'Too large'},413)
    x=json.loads(self.rfile.read(length))
    self.send(db.restore(x['version'],x['paths'],x['destination']))
   except Exception as e:self.send({'error':str(e)},400)
 print('http://127.0.0.1:'+str(port))
 HTTPServer(('127.0.0.1',port),Handler).serve_forever()
def main():
 p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('command',choices=['index','snapshots','list','restore','web']);p.add_argument('items',nargs='*');p.add_argument('--search',default='');p.add_argument('--catalog');p.add_argument('--port',type=int,default=8765);p.add_argument('--overwrite',action='store_true');a=p.parse_args()
 b=Backup(a.backup,a.catalog)
 try:
  if a.command=='index':result=b.index()
  elif a.command=='snapshots':result=b.snapshots()
  elif a.command=='list':result=b.list(int(a.items[0]),a.search)
  elif a.command=='restore':result=b.restore(int(a.items[0]),a.items[2:],a.items[1],a.overwrite)
  else:return web(b,a.port)
  print(json.dumps(result,indent=2))
 finally:b.db.close()
if __name__=='__main__':main()
