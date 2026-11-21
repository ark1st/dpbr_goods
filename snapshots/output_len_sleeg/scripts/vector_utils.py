"""Small SVG helpers and installed VectorCraft CLI integration."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SVG = 'http://www.w3.org/2000/svg'

def cli_path():
    override = os.environ.get('VECTORCRAFT_CLI')
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(f'VECTORCRAFT_CLI does not point to a file: {candidate}')
        return candidate.resolve()
    executable = 'vectorcraft-cli.exe' if os.name == 'nt' else 'vectorcraft-cli'
    candidates = [Path(sys.executable).with_name(executable), shutil.which(executable)]
    if os.environ.get('LOCALAPPDATA'):
        candidates.append(str(Path(os.environ['LOCALAPPDATA'])/'Programs/ArtCraft/VectorCraft/vectorcraft-cli.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError('Install the separate VectorCraft CLI on PATH or set VECTORCRAFT_CLI to its executable.')

def runvc(args):
    result = subprocess.run([cli_path(), *map(str, args)], capture_output=True,
                            text=True, encoding='utf-8',
                            env={**os.environ, 'VECTORCRAFT_NO_PREFS':'1'})
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout

def svg_doc(w,h,content,title=''):
    return f'<svg xmlns="{SVG}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w:.6f}mm" height="{h:.6f}mm" viewBox="0 0 {w:.6f} {h:.6f}"><title>{title}</title>{content}</svg>'

def path(d,fill,stroke=None,sw=4.5):
    s=f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"' if stroke else ''
    return f'<path d="{d}" fill="{fill}"{s}/>'

def ellipse(cx,cy,rx,ry,fill,stroke=None,sw=4.5):
    s=f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}"{s}/>'

def poly_path(p):
    return 'M'+' L'.join(f'{x:.4f} {y:.4f}' for x,y in list(p.exterior.coords)[:-1])+' Z'

def layer(name,content):
    return f'<g inkscape:groupmode="layer" inkscape:label="{name}" id="{name}" data-name="{name}">{content}</g>'
