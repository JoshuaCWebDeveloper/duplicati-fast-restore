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
    # Group child names inside SQLite. Never transfer all snapshot rows to Python.
    # Normalise leading slashes; only the selected directory is considered.
    base = "ltrim(replace(path, char(92), '/'), '/')"
    suffix = f'substr({base}, ? + 1)'
    sql = f"""
    WITH candidates AS (
      SELECT path,type,size,{suffix} AS rest
      FROM files WHERE version=? AND substr({base},1,?)=?
    ), names AS (
      SELECT path,type,size,rest,
        CASE WHEN instr(rest,'/')>0
          THEN substr(rest,1,instr(rest,'/')-1) ELSE rest END AS child
      FROM candidates WHERE rest!=''
    ), grouped AS (
      SELECT child,
        MAX(CASE WHEN instr(rest,'/')>0 OR lower(type) IN ('folder','directory')
                 THEN 1 ELSE 0 END) AS folder,
        MAX(CASE WHEN instr(rest,'/')=0 THEN size ELSE NULL END) AS size
      FROM names WHERE child!='' GROUP BY child
    )
    SELECT child,folder,size FROM grouped ORDER BY folder DESC,child COLLATE NOCASE LIMIT ?
    """
    # Detect whether there are more than the display limit.
    rows=db.db.execute(sql,(len(directory),version,len(directory),directory,limit+1)).fetchall()
    entries=[]
    prefix=('/' if absolute else '')+directory
    for r in rows[:limit]:
        is_folder=bool(r['folder'])
        entries.append({'name':r['child'],'path':prefix+r['child']+('/' if is_folder else ''),
                        'type':'Folder' if is_folder else 'File',
                        'size':None if is_folder else r['size']})
    return {'directory':directory,'search':'','entries':entries,'truncated':len(rows)>limit}
