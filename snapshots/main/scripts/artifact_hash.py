"""Cross-platform artifact identity, matching repository LF text attributes."""
from pathlib import Path
import hashlib

TEXT_SUFFIXES={'.svg','.md','.json','.txt','.py','.yml','.yaml'}

def artifact_sha256(path,data=None):
    path=Path(path)
    if data is None:data=path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()
