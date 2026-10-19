"""Lazy Duplicati archive browser: no full backup scan before browsing."""
import base64
import json
import time
import zipfile
from reader import Backup


class LazyBackup(Backup):
    def __init__(self, folder, catalog=None):
        super().__init__(folder, catalog)
        self.db.execute('CREATE TABLE IF NOT EXISTS indexed_volumes(name TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER)')
        self._sync_snapshots()

    def _sync_snapshots(self):
        # Filename-only discovery: no backup archive payloads are read.
        archives=self.volumes('dlist')
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO versions(volume) VALUES(?)', ((p.name,) for p in archives))
        self._snapshots=archives

    def index(self, lists_only=False, progress=None):
        if progress:
            progress(dict(phase='discovering filenames',kind='',volume='',
                          archives_processed=0,archives_total=0,elapsed_seconds=0,eta_seconds=None))
        self._sync_snapshots()
        result=dict(snapshots=len(self._snapshots),files_loaded_on_demand=True,
                    block_indexes_loaded_on_demand=True)
        if progress:
            progress(dict(phase='ready',kind='',volume='',archives_processed=len(self._snapshots),
                          archives_total=len(self._snapshots),elapsed_seconds=0,eta_seconds=0))
        return result

    def _load_version(self, version):
        row=self.db.execute('SELECT volume FROM versions WHERE id=?',(version,)).fetchone()
        if row is None:
            raise ValueError('Unknown snapshot')
        p=self.folder/row['volume']
        st=p.stat()
        done=self.db.execute('SELECT size,mtime_ns FROM indexed_volumes WHERE name=?',(p.name,)).fetchone()
        if done and tuple(done)==(st.st_size,st.st_mtime_ns):
            return
        with zipfile.ZipFile(p) as z:
            entries=json.loads(z.read('filelist.json').decode('utf-8-sig'))
        records={}
        for f in entries:
            path=f.get('path',f.get('Path'))
            if path:
                records[path]=(version,path,f.get('type',f.get('Type','File')),
                               f.get('size',f.get('Size',0)),f.get('hash',f.get('Hash')),
                               json.dumps(f.get('blocklists',f.get('Blocklists',[]))))
        with self.db:
            self.db.execute('DELETE FROM files WHERE version=?',(version,))
            self.db.executemany('INSERT INTO files VALUES(?,?,?,?,?,?)',records.values())
            self.db.execute('INSERT OR REPLACE INTO indexed_volumes VALUES(?,?,?)',
                            (p.name,st.st_size,st.st_mtime_ns))

    def list(self, version, search=''):
        self._load_version(version)
        return super().list(version,search)

    def restore_file(self, version, path, dest, overwrite=False):
        self._load_version(version)
        return super().restore_file(version,path,dest,overwrite)

    def restore(self, version, paths, dest, overwrite=False):
        self._load_version(version)
        return super().restore(version,paths,dest,overwrite)

    def block(self, name):
        try:
            return super().block(name)
        except FileNotFoundError:
            pass
        key=name.replace('+','-').replace('/','_')
        # dindex is the only source of hash->volume mapping without a job DB.
        # Read on demand; never touch a dblock ZIP merely to discover hashes.
        for p in self.volumes('dindex'):
            stat=p.stat()
            old=self.db.execute('SELECT size,mtime_ns FROM indexed_volumes WHERE name=?',(p.name,)).fetchone()
            if old and tuple(old)==(stat.st_size,stat.st_mtime_ns):
                continue
            with zipfile.ZipFile(p) as z:
                mapping=[]
                for member in z.namelist():
                    if not member.startswith('vol/') or not member.endswith('.dblock.zip'):
                        continue
                    volume=member[4:]
                    obj=json.loads(z.read(member).decode('utf-8-sig'))
                    mapping.extend((item['hash'].replace('+','-').replace('/','_'),
                                    volume,item['hash'].replace('+','-').replace('/','_'))
                                   for item in obj.get('blocks',[]))
            with self.db:
                self.db.executemany('INSERT OR IGNORE INTO blocks VALUES(?,?,?)',mapping)
                self.db.execute('INSERT OR REPLACE INTO indexed_volumes VALUES(?,?,?)',
                                (p.name,stat.st_size,stat.st_mtime_ns))
            if self.db.execute('SELECT 1 FROM blocks WHERE hash=?',(key,)).fetchone():
                return super().block(name)
        raise FileNotFoundError('Block not found in available indexes: '+name)
