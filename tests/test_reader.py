import json,tempfile,unittest,zipfile
from pathlib import Path
from reader import Backup,sha,safe
class BackupTests(unittest.TestCase):
 def test_restore(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);data=b'hello';h=sha(data)
   with zipfile.ZipFile(p/'duplicati-a.dblock.zip','w') as z:z.writestr(h.replace('+','-').replace('/','_'),data)
   with zipfile.ZipFile(p/'duplicati-a.dindex.zip','w') as z:
    z.writestr('vol/duplicati-a.dblock.zip',json.dumps({'blocks':[{'hash':h,'size':len(data)}]}))
   with zipfile.ZipFile(p/'duplicati-a.dlist.zip','w') as z:z.writestr('filelist.json',json.dumps([{'Path':'test/a.txt','Type':'File','Size':5,'Hash':h}]))
   b=Backup(p);self.assertEqual(b.index()['versions_added'],1);self.assertEqual(b.index()['versions_added'],0)
   self.assertEqual(len(b.list(1,'a.txt')),1);b.restore(1,['test/a.txt'],p/'dest')
   self.assertEqual((p/'dest/test/a.txt').read_bytes(),data)
   with self.assertRaises(FileExistsError):b.restore(1,['test/a.txt'],p/'dest')
 def test_traversal(self):
  with self.assertRaises(ValueError):safe('../bad')
if __name__=='__main__':unittest.main()
