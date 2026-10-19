# Duplicati Fast Restore

Experimental **standalone local Duplicati ZIP backup reader and restorer** using Python 3.10+ and the standard library.

## Run

```sh
python app.py /path/to/backup index
python app.py /path/to/backup web
```

Open http://127.0.0.1:8765. Select a snapshot, search by path, and select files to restore.

CLI commands:

```sh
python app.py /path/to/backup snapshots
python app.py /path/to/backup list 1 --search report
python app.py /path/to/backup restore 1 /tmp/recovered 'C:\Users\me\Documents\report.pdf'
```

The tool indexes snapshot metadata and volume hashes into an SQLite file (.fast-restore.sqlite by default). Files are reconstructed from ZIP blocks with SHA-256 verification, written to temporary files, and renamed into the restore destination. It does not modify backup volumes or restore into original absolute locations. By default it refuses to overwrite existing files; the CLI accepts --overwrite.

**Important:** This is a prototype. Supports local unencrypted ZIP backups only. Does not support AES/GPG volumes, other compression formats, cloud backends, metadata, permissions, links, or all historical Duplicati formats. Multiblock blocklist support is preliminary. There are no real Duplicati compatibility fixtures or measured speed comparisons yet. Use copies of backups and verify restored files before relying on this for recovery. The built-in web UI is localhost-only; do not expose it to untrusted users.

Backup format documentation: https://docs.duplicati.com/technical-details/understanding-restore

## Fast path: use Duplicati's existing SQLite database

Pass `--db` pointing to the **per-backup local database**, which is normally
stored outside the backup-volume directory. For example:

```sh
python app.py /mnt/d/Backup/Media-Drive snapshots --db /path/to/job.sqlite
python app.py /mnt/d/Backup/Media-Drive web --db /path/to/job.sqlite
```

In this mode snapshot listing, browsing, and block location lookup query the
original database **read-only**, without rebuilding an index. The database must
match the backup volumes. Never point `--db` to `Duplicati-server.sqlite` or
`.fast-restore.sqlite`. Direct restores currently support ZIP dblock volumes
and ordinary files (not symlinks/metadata); test recovered data independently.

Without `--db`, the reader requires a previously built local catalog and
returns an explicit error if none exists. Run `index` explicitly to build it,
which scans dblock ZIP entries and can be slow on large backups.

## Index progress and performance

Run `python3 app.py /backup/folder index` without `--db` to create
`.fast-restore.sqlite`. The command now only discovers snapshot filenames. It avoids upfront content indexing; browse and restore progressively load metadata as needed.

Browsing an individual snapshot reads its file list on first access, while
block index volumes are only read during restores when the mapping is missing.
The ETA is approximate and may vary considerably between archives. Existing
indexes from earlier versions can be reused, and new `.dindex.zip` mappings
are appended. If a Duplicati backup has no `.dindex.zip` files, the indexer
cannot locate its data blocks; only file listings will be available.

### Duplicate paths in historical file lists

Some Duplicati snapshots contain repeated exact path entries. The indexer
records one row per snapshot/path and keeps the **last** occurrence when
duplicates are encountered, reporting their count as `duplicate_paths`
in the final JSON statistics. This avoids aborting an otherwise useful
archive index. It does not imply the duplicated records are equivalent;
inspect and verify any restored files that may be affected.

### Slow indexing on Windows or external backup disks

If backup archives live on a slow drive, keep the catalog on your faster local
SSD (this is especially important for SQLite workloads):

```powershell
python .\app.py D:\Backup\Media-Drive\ index --catalog C:\Users\carte\fast-restore.sqlite
python .\app.py D:\Backup\Media-Drive\ snapshots --catalog C:\Users\carte\fast-restore.sqlite
```

Using `--catalog` must be consistent across index, browse, and restore commands.
The initial ETA waits until at least one `.dlist` and `.dindex` is completed,
so it does not extrapolate a large snapshot's time across thousands of tiny
index files. Large snapshot inserts report their own record counts every
10,000 records.

## Lazy, selective backup access (default)

The default CLI and web UI now use `LazyBackup`:

- **snapshots / index**: discovers `.dlist.zip` filenames only; does not open
  snapshot data, `.dindex.zip`, or `.dblock.zip` archives. The `index`
  command is now quick snapshot discovery, not a full index.
- **list / browsing**: loads just the selected snapshot's `filelist.json` from
  its `.dlist.zip`, then caches that snapshot's file paths in SQLite. It will
  not eagerly process all historical snapshots.
- **restore**: looks up content hashes in cached indexes first; if needed it
  reads small `.dindex.zip` volumes until the required hashes are found,
  caching the mappings. It opens only the referenced `.dblock.zip` archives
  and extracts required members. Large archive contents are not fully scanned.

**Limits and tradeoffs:** Without an original Duplicati job DB or existing
catalog, a complete arbitrary-path search requires reading metadata from the
relevant snapshot file lists. The ZIP format does not provide a global
path-to-archive lookup. Similarly, finding an uncached block may require
searching many dindex volumes; there is no direct hash-to-volume lookup without
an index. ZIP central directories must be read to locate members, but the
restorer does not decompress unrelated members. The first search in a 30 MB
snapshot may still be slow; subsequent searches of that snapshot use SQLite.
This design minimizes initial I/O, not necessarily first-access latency.

## Web file manager

The localhost web interface offers folder navigation with breadcrumbs, virtual
root folders for backed-up absolute paths, snapshot selection, file and folder
checkboxes, path search, and a restore destination field. Loading indicators
are displayed while fetching snapshot listings, opening folders, searching, or
restoring. Opening a previously uncached snapshot can take time as its dlist
must be read once. Search results and directory contents are capped at 500
entries per request; narrow a search to see items beyond the limit.
