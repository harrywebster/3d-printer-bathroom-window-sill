# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Copy one build into revisions/vNN and refresh the root aliases.

    python3 src/ship.py v1 [--force]

This script only copies and renames. It never regenerates a deliverable --
if the pictures and the printable files ever disagree, it has to be because
build.py made them that way, not because half of them were rebuilt here.

build.py names its output with the tag in it (silldrain-tile1-v1.stl). The
shipped names drop the tag, because the directory already carries it
(revisions/v1/) and the root always holds the latest. The README links are
rewritten to match, so the images resolve in both places.
"""
import os, re, shutil, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N_TILES = 5   # kept in step with src/geomNN.py's N_TILES by the missing-file check below


def aliases(tag):
    fixed = [
        ('silldrain-%s-render.png' % tag,     'render.png'),
        ('silldrain-%s-schematic.png' % tag,  'schematic.png'),
        ('silldrain-%s-colour.3mf' % tag,     'silldrain.3mf'),
    ]
    tiles = [('silldrain-tile%d-%s.stl' % (i + 1, tag), 'silldrain-tile%d.stl' % (i + 1))
             for i in range(N_TILES)]
    return fixed + tiles


def rewrite(readme, tag):
    """Point the README at the shipped names instead of the build names."""
    for src, dst in aliases(tag):
        readme = readme.replace(src, dst)
    return readme


def main(argv):
    if not argv or not re.fullmatch(r'v\d+', argv[0]):
        sys.exit('usage: ship.py vNN [--force]')
    tag = argv[0]
    force = '--force' in argv[1:]

    build = os.path.join(ROOT, 'build', tag)
    if not os.path.isdir(build):
        sys.exit('%s does not exist -- run the build first (make build-%s)' % (build, tag))

    als = aliases(tag)
    wanted = [src for src, _ in als] + ['README.md']
    missing = [f for f in wanted if not os.path.isfile(os.path.join(build, f))]
    if missing:
        sys.exit('build is incomplete, refusing to ship. Missing: %s' % ', '.join(missing))

    geom = os.path.join(ROOT, 'src', 'geom%s.py' % tag[1:].zfill(2))
    if not os.path.isfile(geom):
        sys.exit('%s does not exist' % geom)

    rev = os.path.join(ROOT, 'revisions', tag)
    if os.path.isdir(rev) and not force:
        sys.exit('revisions/%s already exists. A released revision is not edited in '
                 'place -- bump the version instead. (make %s FORCE=1 to override.)'
                 % (tag, tag))

    readme = rewrite(open(os.path.join(build, 'README.md')).read(), tag)

    os.makedirs(rev, exist_ok=True)
    for dest in (rev, ROOT):
        for src, dst in als:
            shutil.copy2(os.path.join(build, src), os.path.join(dest, dst))
        with open(os.path.join(dest, 'README.md'), 'w') as f:
            f.write(readme)

    # The revision keeps its own copy of the model it was built from, so an old
    # revision stays rebuildable even after src/ has moved on.
    shutil.copy2(geom, os.path.join(rev, 'geometry.py'))

    print('shipped %s' % tag)
    print('  revisions/%s/  %s' % (tag, ', '.join([d for _, d in als] + ['README.md', 'geometry.py'])))
    print('  root aliases   %s' % ', '.join([d for _, d in als] + ['README.md']))


if __name__ == '__main__':
    main(sys.argv[1:])
