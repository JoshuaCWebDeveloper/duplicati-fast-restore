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
