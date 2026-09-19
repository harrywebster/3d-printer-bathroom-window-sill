# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Bambu Studio's installed system presets, with their `inherits` chains flattened.

Used by slicecheck.py to prove that every setting in the shipped 3MF which
differs from a stock preset is declared in `different_settings_to_system`.
Bambu Studio silently resets any undeclared difference to stock when the
project is opened in the app — v3 lost its 4 walls and 5 mm brim that way.
Needs Bambu Studio installed; build.py does not import this.
"""
import json, os

PROFILES = '/opt/BambuStudio/resources/profiles/BBL'
# Keys that name or describe a preset rather than set anything.
META = {'name', 'inherits', 'from', 'setting_id', 'instantiation', 'type', 'version',
        'filament_id', 'compatible_printers', 'compatible_printers_condition',
        'compatible_prints', 'compatible_prints_condition', 'description'}

def _find(kind, name):
    d = os.path.join(PROFILES, kind)
    for f in os.listdir(d):
        if f.endswith('.json'):
            j = json.load(open(os.path.join(d, f)))
            if j.get('name') == name:
                return j
    raise KeyError('%s preset %r not found under %s' % (kind, name, PROFILES))

def flat(kind, name):
    """One preset with everything it inherits merged in, parent first."""
    j = _find(kind, name)
    out = flat(kind, j['inherits']) if j.get('inherits') else {}
    out.update({k: v for k, v in j.items() if k != 'inherits'})
    return out

def _norm(v):
    """Compare values the way the app does: '100%' == '100', '1' == '1.0', and a
    one-per-filament list against its preset's single value."""
    if isinstance(v, list):
        return [_norm(x) for x in v[:1]]
    s = str(v).rstrip('%').replace('x', ',')
    try:
        return float(s)
    except ValueError:
        return s

def undeclared(project):
    """Settings in a project config that differ from its named system presets
    but are not listed in different_settings_to_system. Returns
    [(group, key, project value, stock value)]; empty means Bambu Studio will
    open the project with every setting as written."""
    declared = project.get('different_settings_to_system') or ['', '', '']
    groups = [('process', 'print_settings_id', declared[0], lambda v: v),
              ('filament', 'filament_settings_id', declared[1], lambda v: v[0] if isinstance(v, list) else v),
              ('machine', 'printer_settings_id', declared[-1], lambda v: v)]
    out = []
    # A filament preset overrides the process preset for any key both define
    # (pre_start_fan_time is one), so such keys are judged as filament keys.
    fil = flat('filament', groups[1][3](project['filament_settings_id']))
    for kind, id_key, listed, pick in groups:
        stock = flat(kind, pick(project[id_key]))
        ok = set(filter(None, listed.split(';'))) | {id_key}
        for k, v in stock.items():
            if k in META or k not in project or k in ok or (kind != 'filament' and k in fil):
                continue
            a, b = _norm(project[k]), _norm(v)
            if isinstance(a, list) and not isinstance(b, list):
                b = [b]
            if a != b:
                out.append((kind, k, project[k], v))
    return out
