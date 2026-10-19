import base64,hashlib,json,os,sqlite3,tempfile,zipfile
from pathlib import Path

def sha(b): return base64.b64encode(hashlib.sha256(b).digest()).decode()
def safe(s):
 s=s.replace('\\','/')
 if len(s)>1 and s[1]==':': s=s[0]+'_'+s[2:]
 parts=[p for p in s.split('/') if p and p!='.']
 if not parts or '..' in parts or any('\0' in p for p in parts): raise ValueError('Unsafe path')
 return Path(*parts)

class Backup:
 def __init__(self,folder,catalog=None):
  self.folder=Path(folder).resolve()
  self.db=sqlite3.connect(str(catalog or self.folder/'.fast-restore.sqlite'))
  self.db.row_factory=sqlite3.Row
  self.db.executescript('CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY,volume TEXT UNIQUE);CREATE TABLE IF NOT EXISTS files(version INTEGER,path TEXT,type TEXT,size INTEGER,hash TEXT,blocklists TEXT,PRIMARY KEY(version,path));CREATE TABLE IF NOT EXISTS blocks(hash TEXT PRIMARY KEY,volume TEXT,member TEXT);')
 def volumes(self,kind): return sorted(p for p in self.folder.glob('duplicati-*') if ('.'+kind+'.zip') in p.name)
 def index(self):
  count=0
  for p in self.volumes('dlist'):
   if self.db.execute('SELECT 1 FROM versions WHERE volume=?',(p.name,)).fetchone():continue
   with zipfile.ZipFile(p) as z:
    names=[n for n in z.namelist() if n.endswith('.json')]
    if not names:raise ValueError('Missing JSON in '+p.name)
    files=json.loads(z.read(names[0]))
    if isinstance(files,dict):files=files.get('Files',[])
   with self.db:
    version=self.db.execute('INSERT INTO versions(volume) VALUES(?)',(p.name,)).lastrowid
    for f in files:
     if f.get('Path'):self.db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(version,f['Path'],f.get('Type','File'),f.get('Size',0),f.get('Hash'),json.dumps(f.get('Blocklists',[]))))
   count+=1
  blocks=0
  for p in self.volumes('dblock'):
   with zipfile.ZipFile(p) as z:
    with self.db:
     for member in z.namelist():
      if member.endswith('/'):continue
      name=member.rsplit('/',1)[-1]
      blocks+=self.db.execute('INSERT OR IGNORE INTO blocks VALUES(?,?,?)',(name,p.name,member)).rowcount
  return {'versions_added':count,'blocks_added':blocks}
 def snapshots(self):return [dict(r) for r in self.db.execute('SELECT * FROM versions ORDER BY id DESC')]
 def list(self,version,search=''):
  return [dict(r) for r in self.db.execute('SELECT path,type,size,hash FROM files WHERE version=? AND instr(path,?)>0 ORDER BY path LIMIT 2000',(version,search))]
 def block(self,name):
  r=self.db.execute('SELECT volume,member FROM blocks WHERE hash=?',(name,)).fetchone()
  if not r:raise FileNotFoundError('Missing block '+name)
  with zipfile.ZipFile(self.folder/r['volume']) as z:data=z.read(r['member'])
  if sha(data).rstrip('=')!=name.rstrip('='):raise ValueError('Block checksum mismatch')
  return data
 def restore_file(self,version,path,dest,overwrite=False):
  r=self.db.execute('SELECT * FROM files WHERE version=? AND path=?',(version,path)).fetchone()
  if not r:raise FileNotFoundError(path)
  root=Path(dest).resolve()
  target=root/safe(path)
  if not target.resolve().is_relative_to(root):raise ValueError('Destination escapes root')
  if r['type'].lower() in ('folder','directory'):
   target.mkdir(parents=True,exist_ok=True);return str(target)
  if target.exists() and not overwrite:raise FileExistsError(str(target))
  target.parent.mkdir(parents=True,exist_ok=True)
  hashes=[]
  lists=json.loads(r['blocklists'] or '[]')
  if lists:
   for h in lists:
    data=self.block(h)
    if len(data)%32:raise ValueError('Invalid blocklist')
    hashes += [base64.b64encode(data[i:i+32]).decode() for i in range(0,len(data),32)]
  elif r['size']:hashes=[r['hash']]
  fd,tmp=tempfile.mkstemp(dir=target.parent)
  try:
   total=0;check=hashlib.sha256()
   with os.fdopen(fd,'wb') as out:
    for h in hashes:
     data=self.block(h);out.write(data);check.update(data);total+=len(data)
   if total!=r['size'] or (r['hash'] and base64.b64encode(check.digest()).decode()!=r['hash']):raise ValueError('File verification failed')
   os.replace(tmp,target)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  return str(target)
 def restore(self,version,paths,dest,overwrite=False):
  done=[]
  for path in paths:
   rows=self.db.execute('SELECT path FROM files WHERE version=? ORDER BY path',(version,)).fetchall()
   for r in rows:
    if (r['path']==path or r['path'].startswith(path.rstrip('/\\')+'/')) and r['path'] not in done:
     self.restore_file(version,r['path'],dest,overwrite);done.append(r['path'])
  return done
