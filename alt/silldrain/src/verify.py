# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Rebuild the revision the root currently ships, and diff it against what is
actually there. Ships nothing, touches nothing outside build/.

    python3 src/verify.py

Answers one question: does this checkout still reproduce its own output? Run
it after changing a dependency, moving to a new machine, or before trusting a
file you are about to print.

Meshes are compared by volume and bounding box, not byte-for-byte. The
boolean library tessellates flat regions slightly differently between
versions -- a few triangles either way on the same surface. That is a
difference in how the shape is written down, not in the shape. A real
regression moves a volume or a bound.
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

VOL_TOL = 1e-3     # mm3
BOUND_TOL = 1e-6   # mm


def shipped_tag():
    """Which revision is in the root?

    Found by matching the root README against the revisions, not by parsing a
    version out of the prose -- the READMEs deliberately carry no version in
    their text. ship.py writes the same README to both places, so exactly one
    revision matches byte for byte.
    """
    root_path = os.path.join(ROOT, 'README.md')
    if not os.path.isfile(root_path):
        sys.exit('no README.md at the root -- nothing has been shipped yet (make vNN)')
    root = open(root_path, 'rb').read()
    revs = os.path.join(ROOT, 'revisions')
    if not os.path.isdir(revs):
        sys.exit('no revisions/ directory -- nothing has been shipped yet (make vNN)')
    hits = []
    for name in sorted(os.listdir(revs)):
        p = os.path.join(revs, name, 'README.md')
        if os.path.isfile(p) and open(p, 'rb').read() == root:
            hits.append(name)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit('the root README matches no revision in revisions/ -- the root '
                 'and the archive have diverged. Re-ship, or work out which is '
                 'right before trusting either.')
    sys.exit('the root README matches more than one revision (%s); cannot tell '
             'which is shipped' % ', '.join(hits))


def main():
    import trimesh
    import ship

    tag = shipped_tag()
    out = os.path.join(ROOT, 'build', 'verify-' + tag)
    print('root ships %s -- rebuilding it into build/verify-%s\n' % (tag, tag))

    env = dict(os.environ, SILLDRAIN_OUT=out)
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'src', 'build.py'),
                        'geom%s' % tag[1:].zfill(2), tag], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0:
        print(r.stdout)
        sys.exit('build failed -- this checkout does not reproduce %s' % tag)

    fails = []

    # --- README, including every number interpolated into it ---
    rebuilt = ship.rewrite(open(os.path.join(out, 'README.md')).read(), tag)
    current = open(os.path.join(ROOT, 'README.md')).read()
    if rebuilt == current:
        print('README.md              identical')
    else:
        import difflib
        d = list(difflib.unified_diff(current.splitlines(), rebuilt.splitlines(),
                                      'shipped', 'rebuilt', lineterm='', n=1))
        print('README.md              DIFFERS (%d changed lines)' % len(d))
        print('\n'.join('    ' + l for l in d[:40]))
        fails.append('README.md')

    # --- geometry: every tile ---
    for src, alias in ship.aliases(tag):
        if not alias.endswith('.stl'):
            continue
        a = trimesh.load(os.path.join(out, src))
        b = trimesh.load(os.path.join(ROOT, alias))
        dv = abs(a.volume - b.volume)
        db = abs(a.bounds - b.bounds).max()
        ok = dv <= VOL_TOL and db <= BOUND_TOL and a.is_watertight and a.body_count == 1
        print('%-24s %s  volume %.4f vs %.4f mm3 (delta %.5f), bounds delta %.6f mm, '
              'triangles %d vs %d'
              % (alias, 'matches' if ok else 'DIFFERS',
                 a.volume, b.volume, dv, db, len(a.faces), len(b.faces)))
        if not ok:
            fails.append(alias)

    print()
    if fails:
        sys.exit('FAIL -- %s did not reproduce' % ', '.join(fails))
    print('%s reproduces from src/geom%s.py on this machine.' % (tag, tag[1:].zfill(2)))


if __name__ == '__main__':
    main()
