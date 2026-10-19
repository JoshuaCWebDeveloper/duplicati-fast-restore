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

Run `python3 app.py /backup/folder index` once without `--db` to create
`.fast-restore.sqlite`. The command reports each `.dlist.zip` and `.dindex.zip`
archive as it is processed, showing completed/total archives, elapsed time, and
an estimated time remaining based on throughput so far. A repeat invocation
skips unchanged archive files (using file size and modification time).

Indexing reads the compressed file lists and indexes, **not** the large
`.dblock.zip` contents. Initial indexing time depends mainly on snapshot
count, number of files per snapshot, SQLite insertion speed and the drive.
The ETA is approximate and may vary considerably between archives. Existing
indexes from earlier versions can be reused, and new `.dindex.zip` mappings
are appended. If a Duplicati backup has no `.dindex.zip` files, the indexer
cannot locate its data blocks; only file listings will be available.
