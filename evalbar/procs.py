"""Every process the Eval bar thread starts is named so that `top` and Activity Monitor show whose it is: evalbar-<program>.
macOS names a process after the file it was started from, so each program is started through a link with that name in
evalbar/out/bin (made on first use; git-ignored, since the links hold this machine's paths). Python is linked at its real interpreter:
Homebrew's python3 hands over to Python.app, which would show as plain "Python".
  python3 evalbar/procs.py               prints the evalbar-py interpreter path, for starting the thread's own scripts
  exe('ffmpeg')                          the evalbar-ffmpeg link, for subprocess calls
Start this thread's scripts with that interpreter: $(python3 evalbar/procs.py) evalbar/<script>.py ..."""
import os, sys, shutil
import common as C
BIN = os.path.join(C.HERE, 'out', 'bin')
def exe(prog, path=None, name=None):
    """the link evalbar-<name or prog> to the program (found on PATH unless path is given)"""
    real = os.path.realpath(path or shutil.which(prog) or prog)
    os.makedirs(BIN, exist_ok=True); link = os.path.join(BIN, 'evalbar-' + (name or os.path.basename(prog)))
    if not (os.path.islink(link) and os.readlink(link) == real):
        if os.path.lexists(link): os.remove(link)
        os.symlink(real, link)
    return link
def python():
    """the evalbar-py link to the running interpreter's real binary (inside Python.app for a framework build)"""
    app = os.path.join(sys.base_prefix, 'Resources', 'Python.app', 'Contents', 'MacOS', 'Python')
    return exe('python', app if os.path.exists(app) else sys.executable, name='py')
if __name__ == '__main__': print(python())
