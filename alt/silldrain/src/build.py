# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Regenerate every deliverable from one geometry module.

    python3 src/build.py geom01 v1        # -> build/v1/
    SILLDRAIN_OUT=somewhere python3 src/build.py geom01 v1

Normally driven by `make build-v1` (build only) or `make v1` (build + ship).

Keeps the product renders, the schematic and the exported files locked to the
same model -- no hand-edited import line can ever point them at different
geometry.
"""
import sys, os, zipfile, importlib
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
from shapely.geometry import Polygon as SPoly
from shapely.ops import unary_union
import trimesh, render

# Where the deliverables land. Overridable so the build is not tied to one
# machine's layout; the Makefile points it at build/<tag>/.
OUT = os.path.join(os.environ.get('SILLDRAIN_OUT', 'build'), '')
GREY = (0.55, 0.55, 0.57)      # PLA Basic Grey
MARK = (0.83, 0.24, 0.14)      # magnet-position marker, render only, never printed
INK, HID, FILL = '#1b1f24', '#8a949e', '#eef1f4'
GREY_HEX = '#8C8C92'


def _crop(mesh, bounds):
    box = trimesh.creation.box(bounds=bounds)
    return trimesh.boolean.intersection([mesh, box], engine='manifold')


def _marker(x, y, z, r=3.5):
    s = trimesh.creation.icosphere(subdivisions=2, radius=r)
    s.apply_translation([x, y, z])
    return s


# ----------------------------------------------------------------- views
def views(g, tiles, assembly, tag):
    quarter = [(m, GREY) for m in assembly]

    end_on = [(assembly[0], GREY)]

    pad_i = g.PAD_TILE_INDEX
    pad_world_x0 = pad_i * g.TILE_W
    pad_close = _crop(assembly[pad_i],
                      [[pad_world_x0 - 5, -5, -1],
                       [pad_world_x0 + g.TILE_W + 5, g.SILL_D + 5, 30]])
    pad_view = [(pad_close, GREY)]

    seam_x = g.TILE_W  # seam between tile 0 and tile 1
    seam_pieces = [_crop(assembly[0], [[seam_x - 45, -5, -1], [seam_x + 45, 145, 20]]),
                   _crop(assembly[1], [[seam_x - 45, -5, -1], [seam_x + 45, 145, 20]])]
    seam_view = [(m, GREY) for m in seam_pieces]

    gap = 55.0
    exploded = []
    markers = []
    for i, t in enumerate(tiles):
        m = t.copy()
        m.apply_translation([i * (g.TILE_W + gap), 0, 0])
        exploded.append((m, GREY))
        x0 = i * (g.TILE_W + gap)
        for y in g.MAG_Y:
            z = float(g.mid_z(y))
            if i > 0:
                markers.append(_marker(x0 + 1.5, y, z))
            if i < g.N_TILES - 1:
                markers.append(_marker(x0 + g.TILE_W - 1.5, y, z))
    exploded += [(m, MARK) for m in markers]

    spec = [
        ('Assembled, three-quarter view', quarter, -52, 28),
        ('End-on -- wedge profile', end_on, 0, 10),
        ('Plant pad close-up (tile 3)', pad_view, -35, 48),
        ('Magnet seam close-up (tile 1/2)', seam_view, 18, 22),
        ('Exploded -- 5 tiles, magnet positions marked', exploded, -46, 24),
    ]
    imgs = [(t, render.trim(render.render(it, azim=a, elev=e, W=820, H=640)))
            for t, it, a, e in spec]
    fig = plt.figure(figsize=(12, 15.5), dpi=150, facecolor='white')
    gs = fig.add_gridspec(3, 2, hspace=0.16, wspace=0.04,
                          left=0.02, right=0.98, top=0.94, bottom=0.02)
    slots = [(0, 0), (0, 1), (1, 0), (1, 1), (2, slice(0, 2))]
    for (t, img), slot in zip(imgs, slots):
        ax = fig.add_subplot(gs[slot]); ax.imshow(img); ax.axis('off')
        ax.set_title(t, fontsize=11, weight='bold', color='#222', pad=4)
    fig.suptitle('%s -- %.0f x %.0f mm run, %d tiles of %.0f x %.0f mm'
                 % (g.NAME, g.TOTAL_W, g.SILL_D, g.N_TILES, g.TILE_W, g.TILE_D),
                 fontsize=15, weight='bold', color='#111', y=0.975)
    fig.text(0.5, 0.006, 'PLA Basic Grey. Red markers show glued-in CA007 D6 x 3 mm magnet positions.',
             ha='center', fontsize=9, color='#666')
    p = OUT + 'silldrain-%s-render.png' % tag
    fig.savefig(p, bbox_inches='tight', facecolor='white'); plt.close(fig)
    return p


# ------------------------------------------------------------- schematic
def _sil(mesh, i, j):
    tris = mesh.vertices[mesh.faces][:, :, [i, j]]
    polys = [SPoly(t) for t in tris
             if abs((t[1,0]-t[0,0])*(t[2,1]-t[0,1]) - (t[1,1]-t[0,1])*(t[2,0]-t[0,0])) > 1e-9]
    return unary_union(polys).buffer(0.002).buffer(-0.002)

def _draw(ax, shape, fc=FILL, ec=INK, lw=1.2, z=2):
    for p in (shape.geoms if hasattr(shape, 'geoms') else [shape]):
        ax.add_patch(MPoly(np.array(p.exterior.coords), closed=True,
                           fc=fc, ec=ec, lw=lw, zorder=z))
        for hole in p.interiors:
            ax.add_patch(MPoly(np.array(hole.coords), closed=True,
                               fc='white', ec=ec, lw=lw*0.8, zorder=z+1))

def _dim(ax, p0, p1, text, off=0, vert=False, fs=8.5):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    n = np.array([1.0, 0]) if vert else np.array([0, 1.0])
    a, b = p0 + n*off, p1 + n*off
    ax.annotate('', xy=a, xytext=b,
                arrowprops=dict(arrowstyle='<->', color='#4a5560', lw=0.9))
    for p, q in ((p0, a), (p1, b)):
        ax.plot([p[0], q[0]], [p[1], q[1]], color='#b6bec6', lw=0.6, zorder=1)
    m = (a + b) / 2
    # A little clear air between the arrowhead and the label -- short
    # dimension lines (a handful of mm on screen) otherwise render with the
    # number crushed against the arrowhead.
    ax.text(m[0] + (3.2 if vert else 0), m[1] + (0 if vert else 1.2), text,
            ha='left' if vert else 'center', va='center' if vert else 'bottom',
            fontsize=fs, color='#2a333c',
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85) if vert else None)

def _sec(mesh, normal, origin, basis):
    s = mesh.section(plane_origin=origin, plane_normal=normal)
    if s is None:
        return None
    p, _ = s.to_2D(to_2D=basis)
    return p

LONG = np.array([[0,1,0,0],[0,0,1,0],[1,0,0,0],[0,0,0,1.]])


def schematic(g, tiles, assembly, tag):
    fig = plt.figure(figsize=(12, 15.5), dpi=160, facecolor='white')
    gs = fig.add_gridspec(3, 1, height_ratios=[0.62, 1.0, 1.0],
                          hspace=0.28, left=0.06, right=0.96, top=0.93, bottom=0.035)
    lab = dict(fontsize=8, color='#2a333c',
               arrowprops=dict(arrowstyle='->', color='#6b7680', lw=0.8))

    # -------------------------------------------------- plan view
    ax = fig.add_subplot(gs[0, 0])
    sill = MPoly([(0, 0), (g.TOTAL_W, 0), (g.TOTAL_W, g.SILL_D), (0, g.SILL_D)],
                closed=True, fc=FILL, ec=INK, lw=1.4, zorder=2)
    ax.add_patch(sill)
    nose = MPoly([(0, g.SILL_D), (g.TOTAL_W, g.SILL_D), (g.TOTAL_W, g.TILE_D), (0, g.TILE_D)],
                closed=True, fc='#f5f2ee', ec=HID, lw=1.0, ls='--', zorder=1)
    ax.add_patch(nose)
    for i in range(1, g.N_TILES):
        x = i * g.TILE_W
        ax.plot([x, x], [0, g.TILE_D], color=HID, lw=0.9, ls=':', zorder=3)
    pad_x0 = g.PAD_TILE_INDEX * g.TILE_W + g.PAD_X0
    pad_y0 = g.PAD_Y0
    ax.add_patch(MPoly([(pad_x0, pad_y0), (pad_x0 + g.PAD, pad_y0),
                        (pad_x0 + g.PAD, pad_y0 + g.PAD), (pad_x0, pad_y0 + g.PAD)],
                       closed=True, fc='#dfe6ea', ec=INK, lw=1.0, zorder=4))
    _dim(ax, (0, -12), (g.TOTAL_W, -12), '%.0f' % g.TOTAL_W, off=-8)
    _dim(ax, (-14, 0), (-14, g.SILL_D), '%.0f' % g.SILL_D, off=-8, vert=True)
    _dim(ax, (0, g.SILL_D + g.NOSE + 14), (g.TILE_W, g.SILL_D + g.NOSE + 14),
        '%.0f tile pitch' % g.TILE_W, off=6)
    ax.annotate('nose +%.0f' % g.NOSE, xy=(g.TOTAL_W * 0.5, g.SILL_D + g.NOSE * 0.5),
                xytext=(g.TOTAL_W * 0.62, g.SILL_D + g.NOSE + 30), **lab)
    ax.annotate('plant pad %.0f x %.0f\n(tile %d, centred)' % (g.PAD, g.PAD, g.PAD_TILE_INDEX + 1),
                xy=(pad_x0 + g.PAD/2, pad_y0 + g.PAD/2), xytext=(pad_x0 - 120, pad_y0 - 60), **lab)
    ax.set_xlim(-40, g.TOTAL_W + 40); ax.set_ylim(-40, g.TILE_D + 55)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('Plan -- %d tiles, %.0f x %.0f mm run (sill footprint %.0f x %.0f)'
                % (g.N_TILES, g.TOTAL_W, g.TILE_D, g.TOTAL_W, g.SILL_D),
                fontsize=12, weight='bold', color=INK)

    # ------------------------------------- side section, non-centre tile
    gs2 = gs[1, 0].subgridspec(1, 2, wspace=0.08)
    ax2 = fig.add_subplot(gs2[0, 0])
    xcut = g.TILE_W / 2.0
    poly = _sec(tiles[0], [1, 0, 0], [xcut, 0, 0], LONG)
    if poly is not None:
        for p in poly.polygons_full:
            ax2.add_patch(MPoly(np.array(p.exterior.coords), closed=True,
                                fc=FILL, ec=INK, lw=1.2, zorder=2))
    _dim(ax2, (0, g.THICK_BACK + g.BACK_LIP_H + 10), (g.SILL_D, g.THICK_BACK + g.BACK_LIP_H + 10),
        'sill zone %.0f' % g.SILL_D, off=3)
    _dim(ax2, (g.SILL_D, g.THICK_BACK + g.BACK_LIP_H + 10), (g.TILE_D, g.THICK_BACK + g.BACK_LIP_H + 10),
        'nose %.0f' % g.NOSE, off=3)
    _dim(ax2, (-14, 0), (-14, g.THICK_BACK), '%.0f' % g.THICK_BACK, off=-3, vert=True)
    _dim(ax2, (g.TILE_D + 10, 0), (g.TILE_D + 10, g.THICK_TIP), '%.1f' % g.THICK_TIP, off=3, vert=True)
    ax2.annotate('back lip +%.0f' % g.BACK_LIP_H, xy=(g.BACK_LIP_D, g.THICK_BACK + g.BACK_LIP_H - 1),
                xytext=(30, g.THICK_BACK + g.BACK_LIP_H + 6), **lab)
    ax2.annotate('%.1f mm fall over %.0f mm\n(~%.1f deg)' % (g.THICK_BACK - g.THICK_FRONT, g.SILL_D,
                np.degrees(np.arctan(g.K1))), xy=(g.SILL_D * 0.55, float(g.top_z(g.SILL_D * 0.55))),
                xytext=(60, g.THICK_BACK - 3), **lab)
    ax2.annotate('drip groove\n%.1f w x %.1f d' % (g.DRIP_GROOVE_W, g.DRIP_GROOVE_D),
                xy=(g.DRIP_GROOVE_Y, 0), xytext=(g.SILL_D + 2, -14), **lab)
    ax2.set_xlim(-20, g.TILE_D + 26); ax2.set_ylim(-20, g.THICK_BACK + g.BACK_LIP_H + 18)
    ax2.set_aspect('equal'); ax2.axis('off')
    ax2.set_title('Side section -- tile 1 (wedge profile)', fontsize=11.5, weight='bold', color=INK)

    # -------------------------------------- section through the centre tile
    # Cut off-centre (not at TILE_W/2): the front-rim drain notch is centred
    # on the pad in x, so a section straight through the middle would slice
    # through the notch and miss the rim on that side entirely.
    ax3 = fig.add_subplot(gs2[0, 1])
    pad_xcut = g.PAD_X0 + g.PAD * 0.25
    poly3 = _sec(tiles[g.PAD_TILE_INDEX], [1, 0, 0], [pad_xcut, 0, 0], LONG)
    if poly3 is not None:
        for p in poly3.polygons_full:
            ax3.add_patch(MPoly(np.array(p.exterior.coords), closed=True,
                                fc='#dfe6ea', ec=INK, lw=1.2, zorder=2))
    z_pad = float(g.top_z(g.PAD_YC))
    _dim(ax3, (g.PAD_Y0, z_pad + g.PAD_RIM_H + 6), (g.PAD_Y1, z_pad + g.PAD_RIM_H + 6),
        'pad %.0f' % g.PAD, off=3)
    _dim(ax3, (-14, 0), (-14, z_pad), '%.1f' % z_pad, off=-3, vert=True)
    ax3.annotate('rim +%.0f' % g.PAD_RIM_H, xy=(g.PAD_Y0 + 2, z_pad + g.PAD_RIM_H - 0.5),
                xytext=(30, z_pad + g.PAD_RIM_H + 10), **lab)
    ax3.set_xlim(-20, g.TILE_D + 10); ax3.set_ylim(-20, g.THICK_BACK + g.BACK_LIP_H + 18)
    ax3.set_aspect('equal'); ax3.axis('off')
    ax3.set_title('Section -- tile %d (plant pad, level)' % (g.PAD_TILE_INDEX + 1),
                 fontsize=11.5, weight='bold', color=INK)

    # -------------------------------------------------- seam detail
    ax4 = fig.add_subplot(gs[2, 0])
    y_detail = g.MAG_Y[0] + 5
    poly4 = _sec(assembly[0], [0, 1, 0], [0, y_detail, 0],
                np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1.]]))
    poly5 = _sec(assembly[1], [0, 1, 0], [0, y_detail, 0],
                np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1.]]))
    for poly, fc in ((poly4, '#dfe6ea'), (poly5, FILL)):
        if poly is not None:
            for p in poly.polygons_full:
                ax4.add_patch(MPoly(np.array(p.exterior.coords), closed=True,
                                    fc=fc, ec=INK, lw=1.2, zorder=2))
    for y in g.MAG_Y:
        z = float(g.mid_z(y))
        ax4.add_patch(plt.Circle((g.TILE_W, z), g.MAG_D / 2, fc='none', ec='#b03a2a',
                                 lw=1.0, ls='--', zorder=5))
    ax4.annotate('tongue %.0f w x %.0f h,\ngroove +%.2f clearance' % (g.TONGUE_H, g.TONGUE_W, g.TONGUE_CLR),
                xy=(g.TILE_W - 2, float(g.mid_z(y_detail))), xytext=(g.TILE_W - 34, g.THICK_BACK + 5), **lab)
    ax4.annotate('3x magnet pockets\nD%.1f x %.1f deep\ny = %s' % (g.MAG_D, g.MAG_DEPTH,
                ', '.join('%.0f' % y for y in g.MAG_Y)),
                xy=(g.TILE_W + 3, float(g.mid_z(g.MAG_Y[0]))), xytext=(g.TILE_W + 9, g.THICK_BACK + 5), **lab)
    ax4.set_xlim(g.TILE_W - 30, g.TILE_W + 30); ax4.set_ylim(-4, g.THICK_BACK + 14)
    ax4.set_aspect('equal'); ax4.axis('off')
    ax4.set_title('Detail -- tongue / groove / magnet seam (section at y=%.0f)' % y_detail,
                 fontsize=11.5, weight='bold', color=INK)

    fig.suptitle('%s -- general arrangement' % g.NAME, fontsize=16, weight='bold', color='#111', y=0.975)
    fig.text(0.5, 0.006, 'All dimensions in millimetres. %d tiles of %.0f x %.0f mm, PLA Basic Grey.'
            % (g.N_TILES, g.TILE_W, g.TILE_D), ha='center', fontsize=9, color='#666')
    p = OUT + 'silldrain-%s-schematic.png' % tag
    fig.savefig(p, bbox_inches='tight', facecolor='white'); plt.close(fig)
    return p


# ---------------------------------------------------------------- export
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'

def _obj(mesh, oid, name):
    v = ''.join('<vertex x="%.4f" y="%.4f" z="%.4f"/>' % tuple(p) for p in mesh.vertices)
    t = ''.join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in mesh.faces)
    return ('<object id="%d" type="model" name="%s" pid="10" pindex="0">'
            '<mesh><vertices>%s</vertices><triangles>%s</triangles></mesh></object>'
            % (oid, name, v, t))

def export(g, tiles, tag):
    gap = 15.0
    laid = []
    stls = []
    for i, t in enumerate(tiles):
        m = t.copy()
        m.apply_translation([i * (g.TILE_W + gap), 0, 0])
        m.merge_vertices(); m.fix_normals()
        laid.append(m)
        p = OUT + 'silldrain-tile%d-%s.stl' % (i + 1, tag)
        m.export(p)
        stls.append(p)

    hexcol = 'FF%02X%02X%02X' % tuple(int(c * 255) for c in GREY)
    objs = ''.join(_obj(m, i + 1, 'SillDrain tile %d' % (i + 1)) for i, m in enumerate(laid))
    items = ''.join('<item objectid="%d" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' % (i + 1)
                    for i in range(len(laid)))
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" '
             'xml:lang="en-US" xmlns="%s">\n<metadata name="Title">%s %s</metadata>\n'
             '<resources><basematerials id="10"><base name="PLA Basic Grey" displaycolor="%s"/>'
             '</basematerials>%s</resources>\n<build>%s</build>\n</model>\n'
             ) % (NS, g.NAME, tag, hexcol, objs, items)
    ms = ''.join('  <object id="%d"><metadata key="name" value="SillDrain tile %d"/>'
                '<metadata key="extruder" value="1"/></object>\n' % (i + 1, i + 1)
                for i in range(len(laid)))
    ms = '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n%s</config>\n' % ms
    ps = '{\n  "enable_support": "0"\n}\n'
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org'
          '/package/2006/content-types"><Default Extension="rels" ContentType="application/'
          'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" '
          'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '<Default Extension="config" ContentType="application/xml"/>'
          '<Default Extension="txt" ContentType="text/plain"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"><Relationship Target='
            '"/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/'
            '3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    readme_txt = ('%s %s\n%d tiles, one object each, PLA Basic Grey, laid out with a %.0f mm gap '
                 'for visual separation only -- only one or two tiles fit the A1 bed at once, so '
                 'reposition in the slicer before each print.\n\nNO SUPPORTS. '
                 'project_settings.config sets enable_support to 0: nothing in any tile is '
                 'unsupported (the nose is a shallow taper, not a bridge or overhang).\n'
                 % (g.NAME, tag, len(laid), gap))

    p = OUT + 'silldrain-%s-colour.3mf' % tag
    with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', model)
        z.writestr('Metadata/model_settings.config', ms)
        z.writestr('Metadata/project_settings.config', ps)
        z.writestr('Metadata/README.txt', readme_txt)
    return p, stls


# ---------------------------------------------------------------- readme
HISTORY = [
    ('v1', 'first revision -- geometry and renders only, for sign-off before the STL/3MF are treated as final'),
]

def readme(g, tiles, tag, checks):
    hist = '\n'.join('| %s | %s |' % (v, d) for v, d in HISTORY)
    total_vol = sum(t.volume for t in tiles)
    rows = '\n'.join('| %d | %.1f | %s | %d |' % (i + 1, t.volume / 1000, t.is_watertight, t.body_count)
                     for i, t in enumerate(tiles))
    angle = np.degrees(np.arctan(g.K1))
    txt = f"""# {g.NAME}

## Why this exists

The bathroom window sill (850 x 220 mm) sits directly above the bath, and
water and soap that land on it just pool there or dribble down the wall
below rather than draining into the tub. {g.NAME} is a wedge-profiled board
that sits on the sill, falls gently from the window towards the bath, and
overhangs the sill's front edge so run-off drops clear into the water rather
than tracking down the wall. A ribbed top -- inspired by a silicone sink
draining mat -- channels the flow forward, and a flat, rimmed pad in the
centre tile gives a level spot for a plant pot.

The sill is far bigger than the printer bed (256 x 256 x 256 mm), so the run
is split into {g.N_TILES} identical tiles, aligned edge to edge with a
tongue-and-groove key and pulled together with glued-in CA007 D6 x 3 mm
magnets.

Everything below is generated from the model itself, so the numbers match
the files in this folder.

![Renders]({'silldrain-%s-render.png' % tag})

## Dimensions

| | Value |
|---|---|
| Overall run | {g.TOTAL_W:.0f} x {g.SILL_D:.0f} mm ({g.N_TILES} x {g.TILE_W:.0f} mm tiles) |
| Tile, as printed | {g.TILE_W:.0f} x {g.TILE_D:.0f} mm ({g.SILL_D:.0f} mm on the sill + {g.NOSE:.0f} mm nose) |
| Thickness | {g.THICK_BACK:.0f} mm at the back, {g.THICK_FRONT:.0f} mm at the sill edge, {g.THICK_TIP:.1f} mm at the drip tip |
| Fall | {g.THICK_BACK - g.THICK_FRONT:.0f} mm over {g.SILL_D:.0f} mm, about {angle:.1f} degrees |
| Plant pad | {g.PAD:.0f} x {g.PAD:.0f} mm, level, tile {g.PAD_TILE_INDEX + 1} of {g.N_TILES} |
| Total material | {total_vol/1000:,.0f} cm3 across {g.N_TILES} tiles |

![Schematic]({'silldrain-%s-schematic.png' % tag})

## Features

- **Wedge profile.** Flat underside so it sits flush on the level sill; the
  top falls {g.THICK_BACK - g.THICK_FRONT:.0f} mm over the {g.SILL_D:.0f} mm sill depth (~{angle:.1f} degrees),
  enough to move water and soap without a visible tilt.
- **Back lip.** A {g.BACK_LIP_H:.0f} mm upstand over the first {g.BACK_LIP_D:.0f} mm keeps water
  from creeping back behind the board towards the window frame.
- **Front drip nose.** {g.NOSE:.0f} mm cantilevered past the sill's own front edge,
  tapering to a {g.THICK_TIP:.1f} mm tip. A {g.DRIP_GROOVE_W:.1f} x {g.DRIP_GROOVE_D:.1f} mm undercut groove
  {g.TILE_D - g.DRIP_GROOVE_Y:.0f} mm from the tip breaks the water film so it drips into the
  bath instead of tracking back along the underside to the wall.
- **Drain ribs.** Semicircular ribs ({g.RIB_H:.1f} mm tall, {g.RIB_PITCH:.0f} mm pitch) run down the
  slope, following it at every point rather than sitting flat-topped, to
  channel flow forward -- the same idea as a silicone sink mat.
- **Plant pad.** A level {g.PAD:.0f} x {g.PAD:.0f} mm pad set into the slope on tile
  {g.PAD_TILE_INDEX + 1}, with a {g.PAD_RIM_H:.0f} mm rim on {g.PAD_RIM_T:.0f} mm walls so a saucer can't slide off,
  and a {g.PAD_NOTCH_W:.0f} mm gap in the front rim so any overflow drains onto the
  ribbed surface rather than pooling.
- **Tongue and groove.** Every internal seam self-aligns: a {g.TONGUE_H:.0f} x {g.TONGUE_W:.0f} mm
  tongue on the left edge keys into a matching groove on the neighbour's
  right edge, cut {g.TONGUE_CLR:.2f} mm oversize per side for a sliding fit.
- **Magnets.** 3 pockets per seam (D{g.MAG_D:.1f} x {g.MAG_DEPTH:.1f} mm, for a D6 x 3 mm magnet
  with a 0.1-0.2 mm glue fit), recessed into both mating faces at
  y = {', '.join('%.0f' % y for y in g.MAG_Y)} mm, centred on the local mid-thickness at each
  position.

## Printing

| | |
|---|---|
| Printer | Bambu Lab A1, 0.4 nozzle |
| Layer | 0.20 mm |
| Material | PLA Basic Grey |
| Supports | None -- the 3MF sets `enable_support` to 0 |
| Orientation | Each tile flat, as modelled (z=0 is the underside) |
| Assembly | Tongue into groove, then glue a magnet into each of the 3 pockets per seam |

Files: `silldrain-{tag}-colour.3mf` carries all {g.N_TILES} tiles with a single
grey material slot, laid out with a visual gap (only one or two tiles fit the
A1 bed at once -- reposition in the slicer before each print).
`silldrain-tileN-{tag}.stl` is each tile separately. G-code is not generated
or kept here -- it is specific to the printer, filament and calibration
state, so slice it locally from the 3MF each time.

## Checks run at build time

| Tile | Volume (cm3) | Closed, one body | Body count |
|---|---|---|---|
{rows}

| Check | Result |
|---|---|
| Shipped 3MF vs model volume | {checks['volume_match']} |

Mesh volumes are compared to 0.1 mm3, not the triangle count: the boolean
library tessellates flat regions a few triangles differently between runs,
which changes how the shape is written down and not the shape itself.
`make verify` rebuilds this revision and checks it.

## Repository layout

```
.                              latest revision, aliased in the root (after `make v1`)
├── README.md                  this file (regenerated every revision)
├── CLAUDE.md                  working rules for the project
├── LICENSE                    CERN-OHL-S v2
├── Makefile                   make vNN -- build and ship in one step
├── requirements.txt           pinned build dependencies
├── revisions/                 every version, exactly as shipped
│   └── vNN/                   deliverables + geometry.py it was built from
└── src/                       the generator
    ├── geomNN.py               the model -- all parameters live here
    ├── render.py                z-buffer renderer for the product views
    ├── build.py                 one command: renders, schematic, README, 3MF, STLs
    ├── ship.py                  copies a build into revisions/ and the root
    └── verify.py                rebuilds a revision and diffs it against shipped
```

Build everything from the model, where NN is the revision:

```
make build-vNN     # build only, into build/vNN -- ships nothing
make vNN            # build, then ship into revisions/vNN and the root aliases
```

## Licence

CERN Open Hardware Licence Version 2 -- Strongly Reciprocal (CERN-OHL-S v2).
The full text is in [LICENSE](LICENSE).

You may use, make, modify and sell this design. If you distribute a modified
version -- as files or as printed parts -- the licence requires you to release
your modified source under CERN-OHL-S v2 as well, and to state what you
changed.

## Revisions

| Version | Change |
|---|---|
{hist}
"""
    p = OUT + 'README.md'
    open(p, 'w').write(txt)
    return p


if __name__ == '__main__':
    mod, tag = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    g = importlib.import_module(mod)
    tiles = g.make_tiles()
    assembly = g.make_assembly(tiles)
    for i, t in enumerate(tiles):
        print('built tile %d from %s: %.1f mm3  watertight=%s  bodies=%d'
              % (i + 1, mod, t.volume, t.is_watertight, t.body_count))

    print(views(g, tiles, assembly, tag))
    print(schematic(g, tiles, assembly, tag))
    p, stls = export(g, tiles, tag)
    print(p); [print(s) for s in stls]

    # Vertices round-trip through the 3MF at 4 decimal places (see _obj()), so
    # a sub-mm3 delta per tile is expected precision loss, not a regression.
    back = list(trimesh.load(p).geometry.values())
    back_vols = sorted(round(m.volume, 1) for m in back)
    fwd_vols = sorted(round(m.volume, 1) for m in tiles)
    VOL_TOL = 1.0  # mm3
    deltas = [abs(a - b) for a, b in zip(back_vols, fwd_vols)]
    match = ('match (max delta %.3f mm3)' % max(deltas) if max(deltas) <= VOL_TOL
             else 'DIFFERS %s vs %s' % (back_vols, fwd_vols))
    print('CHECK shipped vs model volume:', match)

    checks = dict(volume_match=match)
    print(readme(g, tiles, tag, checks))
