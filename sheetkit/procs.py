"""Every process a sheet thread starts is named after that thread, so `top` and Activity Monitor show whose it is: <prefix>-<program>
(trsheet-node, trsheet-py, trsheet-champ-battle-v16, ...). The prefix is sheet.json "proc_prefix" (default: the team folder's name).
macOS and Linux name a process after the file it was started from, so each program is started through a link with that name in the
team's work/bin (made on first use; git-ignored, since the links hold this machine's paths). Python is linked at its real interpreter:
Homebrew's python3 hands over to Python.app, which would show as plain "Python"; the project venv's packages come along on PYTHONPATH."""
import os, sys, glob, shutil
from common import ROOT, VENV_PY

def prefix(sheet): return sheet.cfg.get('proc_prefix') or sheet.slug

def exe(sheet, prog, path=None, name=None):
    """the link <prefix>-<name or program> to the program (found on PATH unless path is given); the plain program if no link can be made"""
    real = os.path.realpath(path or shutil.which(prog) or prog)
    try:
        d = sheet.w('bin'); os.makedirs(d, exist_ok=True); link = os.path.join(d, f"{prefix(sheet)}-{name or os.path.basename(prog)}")
        if not (os.path.islink(link) and os.readlink(link) == real):
            if os.path.lexists(link): os.remove(link)
            os.symlink(real, link)
        return link
    except OSError:
        return real

def _base_python():
    app = os.path.join(sys.base_prefix, 'Resources', 'Python.app', 'Contents', 'MacOS', 'Python')
    return app if os.path.exists(app) else os.path.realpath(sys.executable)

def python(sheet, venv=False):
    """(interpreter link <prefix>-py, extra environment): with venv=True the project venv's packages (numpy, scipy) are put on PYTHONPATH,
    since the base interpreter started through a link does not see the venv"""
    env = {}
    if venv and os.path.exists(VENV_PY):
        site = glob.glob(os.path.join(ROOT, '.venv', 'lib', 'python*', 'site-packages'))
        if site: env['PYTHONPATH'] = os.pathsep.join(site + [x for x in [os.environ.get('PYTHONPATH')] if x])
    return exe(sheet, 'python', _base_python(), name='py'), env

def own(sheet):
    """re-start the running kit command under the <prefix>-py name, once"""
    if os.environ.get('SHEETKIT_NAMED'): return
    py, env = python(sheet, venv=False)
    if os.path.basename(py) == os.path.basename(sys.executable): return
    env = dict(os.environ, **env, SHEETKIT_NAMED='1')
    site = [p for p in sys.path if p.endswith('site-packages')] + [x for x in [env.get('PYTHONPATH')] if x]
    if site: env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(site))
    sys.stdout.flush(); sys.stderr.flush()
    try: os.execve(py, [py] + sys.argv, env)
    except OSError: pass                                         # carry on under the plain name
