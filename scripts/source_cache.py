"""Restore hash-pinned historical inputs outside the production output tree."""
from pathlib import Path
import hashlib, json, subprocess

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'tmp/source_cache'

def cached_input(source, cache=CACHE):
    """Never revive an obsolete production folder; reject altered cached bytes."""
    relative=Path(source['file'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Source path must stay inside the input cache')
    commit=source['commit']
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Input commit must be a full immutable SHA')
    dest=(cache/commit/relative).resolve()
    if not dest.is_relative_to(cache.resolve()):
        raise ValueError('Source path escaped the input cache')
    if dest.exists():
        data=dest.read_bytes()
    else:
        data=subprocess.check_output(['git','show',commit+':'+source.get('git_path',source['file'])],cwd=ROOT)
    if hashlib.sha256(data).hexdigest()!=source['sha256']:
        raise ValueError(f'Changed source; review before repacking: {source["file"]}')
    if not dest.exists():
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    return dest

def input_records():
    cfg=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))
    return cfg['sources']+cfg.get('archived_inputs',[])

def source_path(relative):
    matches=[s for s in input_records() if s['file']==relative]
    if len(matches)!=1:
        raise ValueError(f'Unregistered or ambiguous source: {relative}')
    return cached_input(matches[0])

def restore_inputs():
    return [cached_input(s) for s in input_records()]
