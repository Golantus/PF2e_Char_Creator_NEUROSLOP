import argparse,sqlite3,zipfile,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--database',type=Path,default=root/'data'/'builder.sqlite3')
parser.add_argument('--output',type=Path,default=root.parent/'pf2e-builder.zip')
args=parser.parse_args()
output=args.output
with tempfile.TemporaryDirectory() as temporary:
    database=args.database
    snapshot=Path(temporary)/'builder.sqlite3'
    if database.exists():
        with sqlite3.connect(database) as source,sqlite3.connect(snapshot) as dest: source.backup(dest)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(root.rglob('*')):
            if not p.is_file() or any(x in p.parts for x in ['node_modules','.venv','__pycache__','.pytest_cache','.git']): continue
            if p.suffix in ['.sqlite3','.pyc','.log'] or p.name.endswith(('-wal','-shm','-journal')): continue
            archive.write(p,'pf2e-builder/'+str(p.relative_to(root)))
        if snapshot.exists(): archive.write(snapshot,'pf2e-builder/data/builder.sqlite3')
print(output,round(output.stat().st_size/1024**2,2),'MiB')
