import tempfile,unittest
from pathlib import Path
from lazy_reader import LazyBackup
from file_manager import browse
from test_real_duplicati import FIXTURE

class FileManagerTests(unittest.TestCase):
 def test_folder_navigation_and_search(self):
  with tempfile.TemporaryDirectory() as d:
   db=LazyBackup(FIXTURE/'backup',Path(d)/'catalog.sqlite')
   try:
    version=db.snapshots()[0]['id']
    root=browse(db,version)
    self.assertEqual(len(root['entries']),1)
    self.assertEqual(root['entries'][0]['name'],'home')
    parent=root['entries'][0]['path']
    while True:
     next_level=browse(db,version,parent)
     self.assertTrue(next_level['entries'],parent)
     if any(x['name']=='example.txt' for x in next_level['entries']):break
     self.assertEqual(len(next_level['entries']),1)
     parent=next_level['entries'][0]['path']
    found=browse(db,version,search='example.txt')
    self.assertEqual(len(found['entries']),1)
   finally:db.close()
if __name__=='__main__':unittest.main()
