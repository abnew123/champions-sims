"""Process names (user, 2026-10-06): every program the team search starts runs through a symlink named teamsearch-<program>, so top and
Activity Monitor show whose it is (macOS and Linux name a process after the file it was started from; names over 15 characters are
cut, which keeps the prefix). Links live in teamsearch/bin/, which is git-ignored because links hold machine paths.
  procs.battle(path) -> teamsearch-battle-vN    procs.node() -> teamsearch-node    procs.py() -> teamsearch-py (Python.app on macOS)
  procs.py_env()     -> env additions so teamsearch-py still sees the project's venv packages
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); BIN = os.path.join(HERE, 'bin')

def link(name, target):
    os.makedirs(BIN, exist_ok=True)
    p, target = os.path.join(BIN, f'teamsearch-{name}'), os.path.realpath(target)
    if not (os.path.islink(p) and os.readlink(p) == target):
        tmp = f'{p}.{os.getpid()}.tmp'
        os.symlink(target, tmp); os.replace(tmp, p)            # atomic, so parallel workers never see a missing link
    return p

def battle(path): return link(os.path.basename(path).replace('champ-battle-', 'battle-'), path)
def node(): return link('node', shutil.which('node'))
def py():
    app = os.path.join(sys.base_prefix, 'Resources', 'Python.app', 'Contents', 'MacOS', 'Python')   # Homebrew python3 hands over to this
    return link('py', app if os.path.exists(app) else os.path.realpath(sys.executable))
def py_env():
    import site
    return {'PYTHONPATH': os.pathsep.join(site.getsitepackages() + [HERE])}

if __name__ == '__main__':                                       # python3 procs.py: make the links and print them
    print(battle(os.path.join(HERE, '..', 'native', 'champ', 'bin', 'champ-battle-v16')), node(), py(), sep='\n')
