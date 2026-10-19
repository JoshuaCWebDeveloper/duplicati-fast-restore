"""Directory-oriented adapter over the selected snapshot catalog."""
def browse(db, version, directory="", search="", limit=500):
    # LazyBackup loads one snapshot on first use; ordinary Backup already has it.
    if hasattr(db, "_load_version"):
        db._load_version(version)
    directory = directory.replace("\\", "/")
    absolute = directory.startswith("/")
    directory = directory.lstrip("/")
    if directory and not directory.endswith("/"):
        directory += "/"
    if directory and (".." in directory.split("/") or "\0" in directory):
        raise ValueError("Invalid directory")
    # Path-prefix filtering is applied before materializing rows, avoiding
    # full snapshot transfers to the browser.
    if search:
        rows=db.db.execute('SELECT path,type,size FROM files WHERE version=? AND instr(lower(path),lower(?))>0 ORDER BY path LIMIT ?',(version,search,limit+1)).fetchall()
        return {"directory":directory,"search":search,"entries":[{"path":r["path"],"name":r["path"].replace("\\","/").rstrip("/").split("/")[-1],"type":r["type"],"size":r["size"]} for r in rows[:limit]],"truncated":len(rows)>limit}
    rows=db.db.execute('SELECT path,type,size FROM files WHERE version=? ORDER BY path',(version,)).fetchall()
    entries={}
    for r in rows:
        path=r["path"].replace("\\","/")
        normalized=path.lstrip("/")
        if directory and not normalized.startswith(directory):continue
        remainder=normalized[len(directory):] if directory else normalized
        if not remainder:continue
        first=remainder.split("/",1)[0]
        # At root, leading '/' is a virtual root; on Windows, C: remains visible.
        has_child="/" in remainder.rstrip("/")
        is_folder=has_child or r["type"].lower() in ("folder","directory")
        child_path=("/" if (absolute or (not directory and path.startswith("/"))) else "")+directory+first+("/" if is_folder else "")
        if first not in entries or not has_child:
            entries[first]={"name":first,"path":child_path if has_child else path,"type":"Folder" if is_folder else r["type"],"size":None if is_folder else r["size"]}
    ordered=sorted(entries.values(),key=lambda e:(e["type"].lower() not in ("folder","directory"),e["name"].lower()))
    return {"directory":directory,"search":"","entries":ordered[:limit],"truncated":len(ordered)>limit}
