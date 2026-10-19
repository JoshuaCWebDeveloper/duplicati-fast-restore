"""Duplicate paths in a real-format Duplicati filelist must not abort indexing."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from reader import Backup

class DuplicatePathTests(unittest.TestCase):
    def test_duplicate_path_preserves_last_record(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "duplicati-20210101T000000Z.dlist.zip"
            entries = [
                {"type":"File","path":"C:/repeat.txt","size":1,"hash":"first"},
                {"type":"File","path":"C:/repeat.txt","size":2,"hash":"second"},
            ]
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("filelist.json", json.dumps(entries))
            db = Backup(folder)
            try:
                report = db.index()
                self.assertEqual(report["duplicate_paths"], 1)
                self.assertEqual(db.list(1), [{"path":"C:/repeat.txt","type":"File","size":2,"hash":"second"}])
                self.assertEqual(db.index()["duplicate_paths"], 0)
            finally:
                db.close()
