# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Slice the shipped 3MF headless in Bambu Studio and report every plate.

    python3 src/slicecheck.py [path/to/windowsill.3mf]

Proves what the volume checks cannot: that Bambu Studio opens the file with
one part on each plate, inside the bed, and slices every plate using only the
settings inside the 3MF. Needs Bambu Studio installed (bambu-studio on PATH);
writes only into build/slicecheck/, and keeps no G-code.
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main(argv):
    src = argv[0] if argv else os.path.join(ROOT, 'windowsill.3mf')
    exe = shutil.which('bambu-studio')
    if not exe:
        sys.exit('bambu-studio is not on PATH — cannot slice-check')
    out = os.path.join(ROOT, 'build', 'slicecheck')
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    r = subprocess.run([exe, '--debug', '1', '--slice', '0', '--outputdir', out, src],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    res = os.path.join(out, 'result.json')
    if not os.path.isfile(res):
        print(r.stdout[-2000:])
        sys.exit('Bambu Studio exited %d without a result' % r.returncode)
    j = json.load(open(res))
    plates = j.get('sliced_plates', [])
    grams = hours = 0.0
    for p in plates:
        g = sum(f['main_used_g'] for f in p['filaments'])
        h = p['total_predication'] / 3600
        sup = p['feature_type_times'].get('Support', 0) + p['feature_type_times'].get('Support interface', 0)
        o = p['objects'][0]
        print('plate %d  %-28s %6.1f g  %5.2f h  supports %s  bbox %.0f x %.0f at (%.1f, %.1f)'
              % (p['id'], o['name'], g, h, 'none' if not sup else '%.0f s' % sup,
                 o['bbox']['width'], o['bbox']['depth'], o['bbox']['x'], o['bbox']['y']))
        grams += g; hours += h
    for f in os.listdir(out):
        if f.endswith('.gcode'):
            os.remove(os.path.join(out, f))          # G-code is never kept
    print('total %d plates  %.0f g  %.1f h  walls %s  infill %s%%  — %s'
          % (len(plates), grams, hours, j.get('wall_loops'), j.get('sparse_infill_density'),
             j.get('error_string')))
    if j.get('return_code') != 0:
        sys.exit('slice-check FAILED')

if __name__ == '__main__':
    main(sys.argv[1:])
