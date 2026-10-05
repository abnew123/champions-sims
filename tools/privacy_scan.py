#!/usr/bin/env python3
"""Privacy scan for this repo: nothing tracked may carry a person's name, an email, an absolute home path, a server address, a key or
Showdown replay lines with usernames. Installed as the pre-commit and commit-msg hooks (.githooks/), it refuses the commit and lists
what it found; it also scans the whole tracked tree or the history for the pre-public check.

Generic patterns are below. Private strings (the user's names, opponents' names, key-pair names) are NOT in this file: they live
outside the tree in <git common dir>/private-patterns.txt (one case-insensitive regular expression per line, '#' comments), so the
list itself is never committed. The hooks refuse to run without that file; `install` creates it.

usage: python3 tools/privacy_scan.py staged                 what the next commit would add (pre-commit hook)
       python3 tools/privacy_scan.py msg <file>             a commit message (commit-msg hook)
       python3 tools/privacy_scan.py tree [rev]             every tracked file at rev (default HEAD) and its path
       python3 tools/privacy_scan.py history [range]        every commit in range (default HEAD): added lines, paths, messages
       python3 tools/privacy_scan.py install                point core.hooksPath at .githooks, create the private patterns file
Exit status 1 when anything matched (or the private list is missing), else 0. The report goes to stderr."""
import os, re, subprocess, sys

GENERIC = [  # (label, regex, flags): strings that are private whoever wrote them
    ('absolute home path', r'/Users/[A-Za-z0-9_]', 0),
    ('email address', r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}', 0),
    ('IPv4 address', r'(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])', 0),
    ('EC2 host name', r'[A-Za-z0-9.-]*compute(?:-1)?\.amazonaws\.com', re.I),
    ('AWS access key id', r'\bAKIA[0-9A-Z]{16}\b', 0),
    ('AWS instance id', r'\bi-[0-9a-f]{17}\b', 0),
    ('private key block', r'-----BEGIN [A-Z ]*PRIVATE KEY-----', 0),
    ('key file name', r'[A-Za-z0-9_-]+\.pem\b', 0),
    ('Showdown replay line with a username', r'^\|(?:player\|p[1-4]\|[^|]+|c\||j\||l\||n\||raw\|)', 0),
]
ALLOW = [  # removed from a line before matching: placeholders and addresses that identify no one
    r'[A-Za-z0-9._%+-]+@users\.noreply\.github\.com', r'noreply@anthropic\.com', r'[A-Za-z0-9._%+-]+@example\.(?:com|org|net)',
    r'\bKEY\.pem\b', r'\b0\.0\.0\.0\b', r'\b127\.0\.0\.1\b', r'\b255\.255\.255\.\d{1,3}\b',
]
SKIP = re.compile(r'(^|/)(package-lock\.json|Cargo\.lock)$|^licenses/')   # third-party metadata and licence texts: public attribution
PRIVATE_NAME = 'private-patterns.txt'
TEMPLATE = """# Private strings the privacy scan refuses in commits (tools/privacy_scan.py): one case-insensitive regular expression per
# line, '#' starts a comment. This file lives in the git directory and is never tracked; keep it that way. Put here: the user's
# names and usernames, email, opponents' and other people's names, server names, key-pair names, anything else personal.
"""


def git(*args, text=True):
    return subprocess.run(['git', *args], capture_output=True, text=text, check=True).stdout


def private_file():
    return os.path.join(os.path.abspath(git('rev-parse', '--git-common-dir').strip()), PRIVATE_NAME)


def load_patterns(need_private):
    pats = [(lab, re.compile(rx, fl)) for lab, rx, fl in GENERIC]
    pf = private_file()
    if not os.path.exists(pf):
        if need_private:
            sys.exit(f"privacy scan: {pf} is missing, so private names cannot be checked. Run `python3 tools/privacy_scan.py install`"
                     f" to create it, add the strings that must stay out of the repo, then commit again.")
        print(f"privacy scan: note, {pf} is missing; only the generic patterns are checked", file=sys.stderr)
        return pats
    for n, line in enumerate(open(pf, encoding='utf-8'), 1):
        s = line.strip()
        if not s or s.startswith('#'): continue
        try: pats.append((f'private string {n}', re.compile(s, re.I)))
        except re.error as e: sys.exit(f"privacy scan: bad regex on line {n} of {pf}: {e}")
    return pats


ALLOW_RE = [re.compile(a) for a in ALLOW]


def hits(text, pats):
    """labels of the patterns that match text (after removing allowed placeholders)"""
    for a in ALLOW_RE: text = a.sub('', text)
    return [lab for lab, rx in pats if rx.search(text)]


class Report:
    def __init__(self): self.n = 0
    def add(self, where, labels, text):
        self.n += 1; t = text.rstrip('\n')
        print(f"  {where}: {', '.join(labels)}: {t[:150]}{'…' if len(t) > 150 else ''}", file=sys.stderr)


def scan_lines(lines, where, pats, rep):
    for k, line in lines:
        h = hits(line, pats)
        if h: rep.add(f'{where}:{k}', h, line)


def scan_patch(patch, pats, rep, prefix=''):
    """added lines and paths of a unified diff (-U0)"""
    path, k = None, 0
    for line in patch.split('\n'):
        if line.startswith('+++ '):
            path = line[6:] if line.startswith('+++ b/') else line[4:]
            if SKIP.search(path): path = None; continue
            h = hits(path, pats)
            if h: rep.add(f'{prefix}{path}', h, 'file name')
        elif line.startswith('@@'):
            m = re.match(r'@@ -\S+ \+(\d+)', line); k = int(m.group(1)) if m else 0
        elif line.startswith('+') and not line.startswith('+++'):
            if path is None: continue
            h = hits(line[1:], pats)
            if h: rep.add(f'{prefix}{path}:{k}', h, line[1:])
            k += 1
        elif line.startswith('diff --git'):
            path = None


def finish(rep, what):
    if rep.n:
        print(f"privacy scan: {rep.n} match(es) in {what}. Rewrite them (\"the user\" / \"the player\", relative paths, placeholders) "
              f"and retry; `git commit --no-verify` skips this check and should not be used.", file=sys.stderr)
        sys.exit(1)
    print(f"privacy scan: clean ({what})", file=sys.stderr)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'staged'
    if mode == 'install':
        top = os.path.abspath(git('rev-parse', '--show-toplevel').strip()); hooks = os.path.join(top, '.githooks')
        subprocess.run(['git', 'config', 'core.hooksPath', hooks], check=True)   # absolute: worktrees share this config and run the
        for h in os.listdir(hooks): os.chmod(os.path.join(hooks, h), 0o755)     # same hooks whatever their checkout contains
        pf = private_file()
        if not os.path.exists(pf): open(pf, 'w', encoding='utf-8').write(TEMPLATE); print(f"created {pf}: add the private strings to it")
        else: print(f"kept {pf} ({sum(1 for l in open(pf) if l.strip() and not l.startswith('#'))} patterns)")
        print(f"hooks installed: core.hooksPath = {hooks} (pre-commit scans staged changes, commit-msg scans the message)"); return
    rep = Report()
    if mode == 'staged':
        pats = load_patterns(True)
        scan_patch(git('diff', '--cached', '-U0', '--no-color', '--diff-filter=ACMR'), pats, rep)
        finish(rep, 'the staged changes')
    elif mode == 'msg':
        pats = load_patterns(True)
        lines = [(k, l) for k, l in enumerate(open(sys.argv[2], encoding='utf-8', errors='replace'), 1) if not l.startswith('#')]
        scan_lines(lines, 'commit message', pats, rep); finish(rep, 'the commit message')
    elif mode == 'tree':
        rev = sys.argv[2] if len(sys.argv) > 2 else 'HEAD'; pats = load_patterns(False)
        for path in git('ls-tree', '-r', '-z', '--name-only', rev).split('\0'):
            if not path or SKIP.search(path): continue
            h = hits(path, pats)
            if h: rep.add(path, h, 'file name')
            blob = git('show', f'{rev}:{path}', text=False)
            if b'\0' in blob[:8000]: continue   # binary
            scan_lines(enumerate(blob.decode('utf-8', 'replace').split('\n'), 1), path, pats, rep)
        finish(rep, f'the tracked tree at {rev}')
    elif mode == 'history':
        rng = sys.argv[2] if len(sys.argv) > 2 else 'HEAD'; pats = load_patterns(False)
        revs = git('rev-list', rng).split(); bad = 0
        for c in revs:
            before = rep.n
            scan_lines(enumerate(git('log', '-1', '--format=%B', c).split('\n'), 1), f'{c[:7]} message', pats, rep)
            scan_patch(git('show', '--format=', '-U0', '--no-color', '--diff-filter=ACMR', c), pats, rep, prefix=f'{c[:7]} ')
            bad += rep.n > before
        print(f"privacy scan: {len(revs)} commits, {bad} with matches", file=sys.stderr); finish(rep, f'the history {rng}')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
