import argparse,json,sys
from pathlib import Path
from file_manager import browse
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlparse,parse_qs
from reader import Backup
from lazy_reader import LazyBackup
from duplicati_db import DuplicatiDB

PAGE = (Path(__file__).with_name('web_ui.html')).read_text(encoding='utf-8')

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
    if u.path=='/browse':return self.send(browse(db,int(q['version'][0]),q.get('directory',[''])[0],q.get('search',[''])[0]))
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
 p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('command',choices=['index','snapshots','list','restore','web']);p.add_argument('items',nargs='*');p.add_argument('--search',default='');p.add_argument('--catalog');p.add_argument('--db',help='Duplicati per-backup SQLite database');p.add_argument('--port',type=int,default=8765);p.add_argument('--overwrite',action='store_true');a=p.parse_args()
 if a.command=='index':
  print(f'Initializing backup index for {a.backup}...',file=sys.stderr,flush=True)
 b=DuplicatiDB(a.backup,a.db) if a.db else LazyBackup(a.backup,a.catalog)

 try:
  if a.command=='index':
   def progress(x):
    eta='estimating' if x['eta_seconds'] is None else str(x['eta_seconds'])+'s'
    records=(f" | records {x['records_processed']}/{x['records_total']}" if 'records_total' in x else '')
    pending=(', awaiting '+', '.join(x['eta_pending'])+' timing' if x.get('eta_pending') else '')
    print(f"[{x['archives_processed']}/{x['archives_total']}] {x['phase']} {x['kind']} {x['volume']}{records} | elapsed {x['elapsed_seconds']}s | ETA {eta}{pending}",file=sys.stderr,flush=True)
   result=b.index(progress=progress)
  elif a.command=='snapshots':result=b.snapshots()
  elif a.command=='list':result=b.list(int(a.items[0]),a.search)
  elif a.command=='restore':result=b.restore(int(a.items[0]),a.items[2:],a.items[1],a.overwrite)
  else:return web(b,a.port)
  print(json.dumps(result,indent=2))
 finally:b.close() if hasattr(b,'close') else b.db.close()
if __name__=='__main__':main()
