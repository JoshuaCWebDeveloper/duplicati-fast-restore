"""Read Duplicati's per-job SQLite database without modifying it."""
import base64
import hashlib
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from reader import safe


class DuplicatiDB:
    def __init__(self, backup_folder, db_path):
        self.folder = Path(backup_folder).resolve()
        self.path = Path(db_path).resolve()
        self.db = sqlite3.connect("file:" + self.path.as_posix() + "?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.tables = {row[0].lower() for row in self.db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        required = {"fileset", "filesetentry", "file", "blockset", "blocksetentry", "block", "remotevolume"}
        if not required <= self.tables:
            raise ValueError("Not a supported Duplicati per-backup SQLite database (missing " +
                             ", ".join(sorted(required-self.tables)) + ")")
        self.columns = {}
        for table in ["File", "Fileset", "FilesetEntry", "Blockset", "BlocksetEntry", "Block", "Remotevolume"]:
            self.columns[table] = {r["name"].lower(): r["name"] for r in self.db.execute('PRAGMA table_info("' + table + '")')}
        self.has_prefix = "prefixid" in self.columns["File"]
        if self.has_prefix and "pathprefix" not in self.tables:
            raise ValueError("PathPrefix table missing")
        self.path_expr = 'COALESCE(pp."Prefix", \'\') || f."Path"' if self.has_prefix else 'f."Path"'
        self.path_join = 'LEFT JOIN "PathPrefix" pp ON pp."ID"=f."PrefixID"' if self.has_prefix else ''

    def snapshots(self):
        sql = 'SELECT fs."ID" AS id, fs."Timestamp" AS timestamp, rv."Name" AS volume FROM "Fileset" fs LEFT JOIN "Remotevolume" rv ON rv."ID"=fs."VolumeID" ORDER BY fs."Timestamp" DESC'
        return [dict(r) for r in self.db.execute(sql)]

    def list(self, version, search=""):
        sql = f'''SELECT {self.path_expr} AS path, bs."Length" AS size,
          bs."FullHash" AS hash, f."BlocksetID" AS blockset
          FROM "FilesetEntry" fe JOIN "File" f ON f."ID"=fe."FileID"
          {self.path_join}
          LEFT JOIN "Blockset" bs ON bs."ID"=f."BlocksetID"
          WHERE fe."FilesetID"=? AND instr({self.path_expr}, ?) > 0
          ORDER BY path LIMIT 2000'''
        return [dict(r) for r in self.db.execute(sql, (version, search))]

    def _record(self, version, path):
        sql = f'''SELECT f."BlocksetID" AS blockset, bs."Length" AS size,
         bs."FullHash" AS hash FROM "FilesetEntry" fe
         JOIN "File" f ON f."ID"=fe."FileID" {self.path_join}
         LEFT JOIN "Blockset" bs ON bs."ID"=f."BlocksetID"
         WHERE fe."FilesetID"=? AND {self.path_expr}=? LIMIT 1'''
        return self.db.execute(sql, (version,path)).fetchone()

    def _blocks(self, blockset):
        return self.db.execute('''SELECT b."Hash" AS hash, rv."Name" AS volume
          FROM "BlocksetEntry" be JOIN "Block" b ON b."ID"=be."BlockID"
          JOIN "Remotevolume" rv ON rv."ID"=b."VolumeID"
          WHERE be."BlocksetID"=? ORDER BY be."Index"''', (blockset,))

    def restore_file(self, version, path, destination, overwrite=False):
        record = self._record(version, path)
        if record is None:
            raise FileNotFoundError(path)
        if record["blockset"] is None or record["blockset"] < 0:
            raise ValueError("Metadata-only folder/symlink entry cannot be restored as a file")
        root = Path(destination).resolve()
        target = root / safe(path)
        if not target.resolve().is_relative_to(root):
            raise ValueError("Path escapes restore root")
        if target.exists() and not overwrite:
            raise FileExistsError(str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".restore-",dir=target.parent)
        try:
            whole = hashlib.sha256()
            count = 0
            with os.fdopen(fd, "wb") as output:
                for block in self._blocks(record["blockset"]):
                    source = self.folder / block["volume"]
                    with zipfile.ZipFile(source) as archive:
                        data = archive.read(block["hash"].replace("+", "-").replace("/", "_"))
                    calculated = base64.b64encode(hashlib.sha256(data).digest()).decode()
                    if calculated != block["hash"]:
                        raise ValueError("Block checksum mismatch: " + block["hash"])
                    whole.update(data)
                    count += len(data)
                    output.write(data)
            if record["size"] != count:
                raise ValueError("Restored file size mismatch")
            if record["hash"] and base64.b64encode(whole.digest()).decode() != record["hash"]:
                raise ValueError("Restored file checksum mismatch")
            if target.exists() and not overwrite:
                raise FileExistsError(str(target))
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return str(target)

    def restore(self, version, selected, destination, overwrite=False):
        sql = f'''SELECT {self.path_expr} AS path FROM "FilesetEntry" fe
          JOIN "File" f ON f."ID"=fe."FileID" {self.path_join}
          WHERE fe."FilesetID"=? ORDER BY path'''
        paths = [r["path"] for r in self.db.execute(sql,(version,))]
        restored = []
        for path in paths:
            if any(path == s or path.startswith(s.rstrip("/\\") + "/") for s in selected):
                r = self._record(version,path)
                if r is not None and r["blockset"] is not None and r["blockset"] >= 0:
                    self.restore_file(version,path,destination,overwrite)
                    restored.append(path)
        return restored

    def close(self):
        self.db.close()
