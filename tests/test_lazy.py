import tempfile
import unittest
from pathlib import Path
from lazy_reader import LazyBackup
from test_real_duplicati import FIXTURE, EXPECTED

class LazyTests(unittest.TestCase):
    def test_browse_and_restore_without_eager_indexing(self):
        with tempfile.TemporaryDirectory() as d:
            db=LazyBackup(FIXTURE/'backup',Path(d)/'index.sqlite')
            try:
                versions=db.snapshots()
                self.assertEqual(len(versions),1)
                self.assertEqual(db.db.execute('SELECT COUNT(*) FROM files').fetchone()[0],0)
                self.assertEqual(db.db.execute('SELECT COUNT(*) FROM blocks').fetchone()[0],0)
                v=versions[0]['id']
                entry=next(x for x in db.list(v) if x['path'].endswith('example.txt'))
                self.assertEqual(db.db.execute('SELECT COUNT(*) FROM blocks').fetchone()[0],0)
                target=Path(db.restore_file(v,entry['path'],d))
                self.assertEqual(target.read_bytes(),EXPECTED)
                self.assertGreater(db.db.execute('SELECT COUNT(*) FROM blocks').fetchone()[0],0)
                self.assertEqual(db.index()['snapshots'],1)
            finally:
                db.close()
if __name__=='__main__':unittest.main()
