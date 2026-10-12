"""Code-only update for an existing installation. Never includes user data."""
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
output=root.parent/'pf2e-builder-update.zip'
files=[p for p in (root/'backend').rglob('*') if p.is_file()
       and not any(part in {'__pycache__','.pytest_cache','.venv'} for part in p.parts)
       and p.suffix not in {'.pyc','.log','.sqlite3'}]
files += [root/'README.md',root/'docs/coverage.md',root/'docs/export-update.md',
          root/'docs/verification.md',root/'frontend/package.json',root/'frontend/package-lock.json']
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for path in sorted(files):
        archive.write(path,str(path.relative_to(root)))
    archive.write(root/'docs/export-update.md','UPDATE.md')
print(output,round(output.stat().st_size/1024,1),'KiB')
