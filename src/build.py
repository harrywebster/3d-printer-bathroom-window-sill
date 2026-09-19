# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Regenerate the deliverables from one geometry module.

    python3 src/build.py geom02 v2             # -> build/v2/  everything
    python3 src/build.py geom02 v2 --concept   # -> build/v2/  views + schematic only
    SILL_OUT=somewhere python3 src/build.py geom02 v2

Normally driven by `make v2` (build and ship) or `make concept-v2` (pictures
for sign-off, nothing printable — see "Sign-off before CAD" in CLAUDE.md).
Both paths run the same model through the same drawing code, so the pictures
signed off and the files printed cannot come from different geometry.
"""
import sys, os, importlib
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Rectangle
from shapely.geometry import box as sbox
from shapely.affinity import translate
import trimesh, render

OUT = os.path.join(os.environ.get('SILL_OUT', 'build'), '')
BED, BRIM = 256.0, 5.0                    # Bambu Lab A1
GREY = (0.60, 0.62, 0.64)                 # PLA Basic Grey
PART_TINT = [(0.60, 0.62, 0.64), (0.55, 0.57, 0.60), (0.60, 0.62, 0.64),
             (0.55, 0.57, 0.60), (0.60, 0.62, 0.64)]
TILE, POT, LEAF, BOTTLE, SOAP = (0.95, 0.95, 0.94), (0.78, 0.42, 0.28), (0.30, 0.55, 0.30), \
    (0.93, 0.93, 0.95), (0.96, 0.90, 0.78)
INK, HID, FILL, CUT = '#1b1f24', '#8a949e', '#eef1f4', '#cfd7de'
LONG = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1.]])    # x-cut -> (y, z)
CROSS = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1.]])  # y-cut -> (x, z)


def _crop(mesh, lo, hi):
    return trimesh.boolean.intersection([mesh, trimesh.creation.box(bounds=[lo, hi])],
                                        engine='manifold')


# ----------------------------------------------------------------- views
def views(g, parts, tag, concept=True):
    board = [(p, GREY) for p in parts]
    pr = g.props()
    scene = board + [(m, TILE) for m in pr['tile']] + [(m, POT) for m in pr['pot']] + \
        [(m, LEAF) for m in pr['leaves']] + [(m, BOTTLE) for m in pr['bottle']] + \
        [(m, SOAP) for m in pr['soap']]
    exploded = []
    for i, p in enumerate(parts):
        q = p.copy(); q.apply_translation([(i - 2) * 40, 0, 0]); exploded.append((q, PART_TINT[i]))
    centre = [(parts[2], GREY)]
    # The right-hand end of part 2, cropped to the seam region.
    seam = _crop(parts[1], [g.seams[1] - 60, -1, -1], [g.seams[1] + 1, g.depth + 1, 40])
    # The left end of part 1 over the sill and wall, seen end on.
    lo, hi = [g.part_x[0] - 1, g.sill_d - 70, -45], [g.part_x[0] + 40, g.depth + 1, 40]
    lip = [(_crop(parts[0], lo, hi), GREY)] + [(_crop(m, lo, hi), TILE) for m in pr['sill']]

    big = [
        ('In place — from the bath', scene, 62, 24, 1500, 760),
        ('The board — three-quarter', board, 58, 30, 1500, 620),
    ]
    small = [
        ('Plan', board, 90, 89.5, 1500, 520),
        ('Exploded — five parts', exploded, 60, 34, 1500, 620),
        ('Centre part — the level plant pad', centre, 55, 30, 900, 760),
        ('Seam face — magnet pockets', [(seam, GREY)], 20, 18, 900, 760),
        ('The overhang — end on, clear of the wall', lip, 180, 7, 900, 520),
        ('Underside — runners, air channels, drip groove', [(parts[1], GREY)], -62, -32, 900, 760),
    ]
    # The underside faces away from the default headlight; light it from below.
    lights = {len(big) + len(small) - 1: [0.35, -0.45, -0.82]}
    imgs = [(t, render.trim(render.render(it, azim=a, elev=e, W=W, H=H, light=lights.get(i))))
            for i, (t, it, a, e, W, H) in enumerate(big + small)]

    fig = plt.figure(figsize=(12, 19), dpi=150, facecolor='white')
    gs = fig.add_gridspec(5, 2, height_ratios=[1.35, 0.9, 0.75, 0.95, 0.9],
                          hspace=0.16, wspace=0.04, left=0.02, right=0.98, top=0.95, bottom=0.02)
    slots = [gs[0, :], gs[1, :], gs[2, 0], gs[2, 1], gs[3, 0], gs[3, 1], gs[4, 0], gs[4, 1]]
    for s, (t, img) in zip(slots, imgs):
        ax = fig.add_subplot(s); ax.imshow(img); ax.axis('off')
        ax.set_title(t, fontsize=11, weight='bold', color='#222', pad=4)
    fig.suptitle('Window-sill draining board — %.0f × %.0f mm, five parts'
                 % (g.width, g.depth), fontsize=15, weight='bold', color='#111', y=0.975)
    fig.text(0.5, 0.004, 'PLA Basic Grey. Pot, bottle, soap and tiling are for scale only. ' +
             ('Concept %s — for sign-off, nothing printable yet.' % tag if concept else
              'Revision %s.' % tag),
             ha='center', fontsize=9, color='#666')
    p = OUT + 'windowsill-%s-views.png' % tag
    fig.savefig(p, bbox_inches='tight', facecolor='white'); plt.close(fig)
    return p


# ------------------------------------------------------------- schematic
def _poly(ax, p, fc=FILL, ec=INK, lw=1.0, z=2, ls='-'):
    for q in (p.geoms if hasattr(p, 'geoms') else [p]):
        ax.add_patch(MPoly(np.array(q.exterior.coords), closed=True, fc=fc, ec=ec,
                           lw=lw, zorder=z, ls=ls))
        for h in q.interiors:
            ax.add_patch(MPoly(np.array(h.coords), closed=True, fc='white', ec=ec,
                               lw=lw*0.8, zorder=z+1))

def _dim(ax, p0, p1, text, off=0, vert=False, fs=8, side=1):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    n = np.array([1.0, 0]) if vert else np.array([0, 1.0])
    a, b = p0 + n*off, p1 + n*off
    ax.annotate('', xy=a, xytext=b, arrowprops=dict(arrowstyle='<->', color='#4a5560', lw=0.8))
    for p, q in ((p0, a), (p1, b)):
        ax.plot([p[0], q[0]], [p[1], q[1]], color='#b6bec6', lw=0.5, zorder=1)
    m = (a + b) / 2
    if vert:
        ax.text(m[0] + side*2.5, m[1], text, ha='left' if side > 0 else 'right',
                va='center', fontsize=fs, color='#2a333c')
    else:
        ax.text(m[0], m[1] + side*2.5, text, ha='center', va='bottom' if side > 0 else 'top',
                fontsize=fs, color='#2a333c')

def _section(ax, mesh, origin, normal, basis, fc=CUT):
    s = mesh.section(plane_origin=origin, plane_normal=normal)
    p, _ = s.to_2D(to_2D=basis)
    for poly in p.polygons_full:
        _poly(ax, poly, fc=fc, lw=1.0)

def _sill(ax, g, y_lo=-12):
    """The sill and the wall below it, dashed — context, not part of the model."""
    kw = dict(color='#9aa4ad', lw=0.9, ls=(0, (4, 3)), zorder=0)
    ax.plot([y_lo, g.sill_d, g.sill_d], [0, 0, -22], **kw)
    ax.plot([0, 0], [0, 40], **kw)
    ax.text(g.sill_d - 3, -4, 'sill', ha='right', va='top', fontsize=7.5, color='#7d8790')
    ax.text(g.sill_d + 2, -18, 'wall', ha='left', va='center', fontsize=7.5, color='#7d8790')
    ax.text(1.5, 34, 'window', ha='left', va='center', fontsize=7.5, color='#7d8790', rotation=90)

def schematic(g, board, parts, tag):
    fig = plt.figure(figsize=(12, 21), dpi=160, facecolor='white')
    gs = fig.add_gridspec(5, 2, height_ratios=[1.25, 0.95, 0.95, 0.75, 1.05], hspace=0.12,
                          wspace=0.10, left=0.04, right=0.97, top=0.945, bottom=0.035)
    lab = dict(fontsize=7.8, color='#2a333c',
               arrowprops=dict(arrowstyle='->', color='#6b7680', lw=0.7))
    ex_s = 2.2   # vertical exaggeration of the long sections, stated on each

    # ---- plan, drawn from the same plan shapes the solids are built from ----
    ax = fig.add_subplot(gs[0, :])
    _poly(ax, g.plan_outline(), fc=FILL, lw=1.2)
    _poly(ax, sbox(-g.width/2, 0, g.width/2, g.rim_w), fc='#dde3e8', lw=0.6)
    for sx in (-1, 1):
        x0 = sx*g.width/2 - (g.rim_w if sx > 0 else 0)
        _poly(ax, sbox(x0, 0, x0 + g.rim_w, g.sill_d), fc='#dde3e8', lw=0.6)
    for r in g.rib_plans():
        _poly(ax, r, fc='#c3cbd2', lw=0.35)
    _poly(ax, g.pad_plan().union(g.prow_plan()), fc='#e7ecef', lw=0.6)
    _poly(ax, g.pad_plan(), fc='#f4f1e6', lw=1.1, z=3)
    ax.text(0, (g.pad_y0 + g.pad_y1)/2, 'LEVEL PAD\n%.0f × %.0f' % (g.pad, g.pad),
            ha='center', va='center', fontsize=9, weight='bold', color='#5a4e2e', zorder=5)
    for s in g.seams:
        ax.plot([s, s], [-4, g.depth + 4], color='#c0392b', lw=0.9, ls=(0, (5, 3)), zorder=6)
        for y in g.mag_y:
            ax.plot(s, y, 'o', ms=3.2, mfc='#c0392b', mec='none', zorder=7)
    ax.plot([-g.width/2 - 20, g.width/2 + 20], [g.sill_d, g.sill_d], color='#7d8790',
            lw=0.8, ls=(0, (2, 2)), zorder=6)
    ax.text(g.width/2 + 22, g.sill_d, 'sill edge', va='center', fontsize=7.5, color='#7d8790')
    ax.plot([-g.width/2 - 20, g.width/2 + 20], [g.drip_y]*2, color='#2c7fb8', lw=0.7,
            ls=(0, (1, 2)), zorder=6)
    ax.text(g.width/2 + 22, g.drip_y + 5, 'drip groove\n(underneath)', va='top', fontsize=7.5,
            color='#2c7fb8')
    for i, (x0, x1) in enumerate(zip(g.part_x[:-1], g.part_x[1:])):
        ax.text((x0 + x1)/2, g.depth + 22, 'part %d' % (i + 1), ha='center', fontsize=8.5,
                weight='bold', color=INK)
        _dim(ax, (x0, g.depth + 8), (x1, g.depth + 8), '%.0f' % (x1 - x0), fs=7.5)
    clear = (' (sill %.0f, %.0f clear each end)' % (g.sill_w, g.fit_clr)) if g.fit_clr else \
        ' — fills the sill exactly'
    _dim(ax, (-g.width/2, -24), (g.width/2, -24), '')
    ax.text(0, -30, '%.0f overall%s' % (g.width, clear), ha='center', va='bottom', fontsize=8,
            color='#2a333c', bbox=dict(fc='white', ec='none', pad=1))
    _dim(ax, (g.width/2 + 14, 0), (g.width/2 + 14, g.sill_d), '%.0f on the sill' % g.sill_d,
         vert=True, fs=7.5)
    _dim(ax, (-g.width/2 - 12, 0), (-g.width/2 - 12, g.depth), '%.0f' % g.depth, vert=True,
         side=-1)
    _dim(ax, (-g.width/2 - 34, g.sill_d), (-g.width/2 - 34, g.depth), 'overhang %.0f' % g.overhang,
         vert=True, side=-1, fs=7.5)
    _dim(ax, (g.pad/2 + 8, 0), (g.pad/2 + 8, g.pad_y0), '%.0f' % g.pad_y0, vert=True, fs=7.5)
    _dim(ax, (g.pad/2 + 8, g.pad_y1), (g.pad/2 + 8, g.sill_d), '%.0f' % (g.sill_d - g.pad_y1),
         vert=True, fs=7.5)
    ax.annotate('prow parts the run-off\naround the pad', xy=(-20, g.prow_y + 14),
                xytext=(-190, -44), **lab)
    ax.annotate('%d tapered ribs, %.1f → %.1f wide,\n%.1f tall at %.2f pitch' %
                (len(g.rib_plans()), g.rib_wb, g.rib_wf, g.rib_h, g.rib_pitch),
                xy=(-340, 120), xytext=(-470, -48), **lab)
    ax.annotate('magnet pockets, 2 per seam', xy=(g.seams[3], g.mag_y[1]),
                xytext=(300, -44), **lab)
    ax.annotate('back rim %.0f wide, %.0f tall' % (g.rim_w, g.rim_h), xy=(200, 3),
                xytext=(120, -44), **lab)
    ax.set_title('Plan — seen from above, window at the top', fontsize=11.5, weight='bold',
                 color=INK, pad=24)
    ax.set_xlim(-g.width/2 - 60, g.width/2 + 90); ax.set_ylim(g.depth + 40, -60)
    ax.set_aspect('equal'); ax.axis('off')

    # ---- section through the ribbed field, between two channels ----
    xr = g.rib_xs[len(g.rib_xs)//2 - 22]
    ax2 = fig.add_subplot(gs[1, :])
    _section(ax2, board, [xr, 0, 0], [1, 0, 0], LONG); _sill(ax2, g)
    _dim(ax2, (-8, 0), (-8, g.back_t), '%.1f' % g.back_t, vert=True, side=-1, fs=7.5)
    _dim(ax2, (g.depth + 6, 0), (g.depth + 6, g.tip_t), '%.1f' % g.tip_t, vert=True, fs=7.5)
    _dim(ax2, (0, -30), (g.sill_d, -30), 'sill %.0f' % g.sill_d, side=-1, fs=7.5)
    _dim(ax2, (g.sill_d, -30), (g.depth, -30), '%.0f' % g.overhang, side=-1, fs=7.5)
    ax2.annotate('fall %.1f° — %.1f mm over the %.0f depth' % (g.slope_deg, g.back_t - g.tip_t, g.depth),
                 xy=(120, float(g.z_top(120)) + g.rib_h), xytext=(80, 40), **lab)
    ax2.annotate('back rim %.0f above the surface' % g.rim_h, xy=(g.rim_w/2, g.back_t + g.rim_h),
                 xytext=(18, 46), **lab)
    ax2.annotate('rib %.1f tall' % g.rib_h, xy=(g.rib_y0 + 20, float(g.z_top(g.rib_y0 + 20)) + g.rib_h),
                 xytext=(40, 32), **lab)
    ax2.annotate('V drip groove %.1f × %.1f,\n45° flanks, prints unsupported' % (g.drip_w, g.drip_d),
                 xy=(g.drip_y, 0.9), xytext=(g.depth - 70, -24), **lab)
    ax2.annotate('magnet pockets (at the seams)', xy=(g.mag_y[0], g.mag_z), xytext=(30, -24), **lab)
    for y in g.mag_y:
        ax2.add_patch(plt.Circle((y, g.mag_z), g.pocket_d/2, fill=False, ec='#c0392b', lw=0.7,
                                 ls='--', zorder=5))
    ax2.set_title('Section through the ribbed field (x = %.0f) — water runs left to right' % xr,
                  fontsize=11.5, weight='bold', color=INK)
    ax2.set_xlim(-30, g.depth + 30); ax2.set_ylim(-40, 54); ax2.set_aspect(ex_s); ax2.axis('off')
    ax2.text(g.depth + 28, -38, 'vertical scale ×%.1f' % ex_s, ha='right', fontsize=7, color='#8a949e')

    # ---- section through the pad ----
    ax3 = fig.add_subplot(gs[2, :])
    _section(ax3, board, [0, 0, 0], [1, 0, 0], LONG); _sill(ax3, g)
    ax3.plot([g.pad_y0, g.pad_y1], [g.pad_z + 2.5]*2, color='#b08d2c', lw=0.8)
    ax3.text((g.pad_y0 + g.pad_y1)/2, g.pad_z + 4, 'level — %.0f, top at %.1f' % (g.pad, g.pad_z),
             ha='center', va='bottom', fontsize=8, color='#7a6320')
    _dim(ax3, (g.pad_y0, -30), (g.pad_y1, -30), 'pad %.0f, central on the %.0f sill' % (g.pad, g.sill_d),
         side=-1, fs=7.5)
    ax3.annotate('prow ramps from the pad down\nto the surface, apex %.0f from the window' % g.prow_y,
                 xy=(g.prow_y + 14, float(g.z_top(g.prow_y + 14)) + 1.5), xytext=(-25, 44), **lab)
    ax3.annotate('%.1f step at the front of the pad' % (g.pad_z - float(g.z_top(g.pad_y1))),
                 xy=(g.pad_y1, (g.pad_z + float(g.z_top(g.pad_y1)))/2), xytext=(g.pad_y1 + 15, 34), **lab)
    ax3.set_title('Section on the centreline — the plant pad', fontsize=11.5, weight='bold', color=INK)
    ax3.set_xlim(-30, g.depth + 30); ax3.set_ylim(-40, 54); ax3.set_aspect(ex_s); ax3.axis('off')
    ax3.text(g.depth + 28, -38, 'vertical scale ×%.1f' % ex_s, ha='right', fontsize=7, color='#8a949e')

    # ---- section across the runners ----
    ax6 = fig.add_subplot(gs[3, :])
    ys = 100.0
    x_lo, x_hi = g.seams[0] - 14, g.seams[1] + 14
    sec = _crop(board, [x_lo, -1, -1], [x_hi, g.depth + 1, 60])
    _section(ax6, sec, [0, ys, 0], [0, 1, 0], CROSS)
    ax6.plot([x_lo - 6, x_hi + 6], [0, 0], color='#9aa4ad', lw=0.9, ls=(0, (4, 3)), zorder=0)
    for s in g.seams[:2]:
        ax6.plot([s, s], [-3, float(g.z_top(ys)) + 3], color='#c0392b', lw=0.8, ls=(0, (5, 3)), zorder=6)
    if g.chan_w:
        cx = [x for x in g.channel_xs() if g.seams[0] < x < g.seams[1]]
        _dim(ax6, (cx[0] - g.chan_w/2, -1.5), (cx[0] + g.chan_w/2, -1.5), '%.1f' % g.chan_w,
             side=-1, fs=7)
        _dim(ax6, (cx[0] + g.chan_w/2, -1.5), (cx[1] - g.chan_w/2, -1.5),
             '%.1f' % (g.chan_pitch - g.chan_w), side=-1, fs=7)
        ax6.annotate('%d air channels per part, %.1f tall, 45° gable roof — no bridging'
                     % (g.chan_n, g.chan_d), xy=(cx[4], g.chan_d*0.7), xytext=(cx[0] - 8, -10), **lab)
        ax6.annotate('%.1f runners rest on the tile ridges' % (g.chan_pitch - g.chan_w),
                     xy=(cx[11] + g.chan_pitch/2, 0.2), xytext=(cx[11] + 6, -10), **lab)
        ax6.annotate('solid next to the seam\nfor the magnet pockets', xy=(g.seams[1] - 3, 4),
                     xytext=(g.seams[1] - 70, float(g.z_top(ys)) + 6), **lab)
    ax6.set_title('Section across part 2 at %.0f from the window — the runners' % ys,
                  fontsize=11.5, weight='bold', color=INK)
    ax6.set_xlim(x_lo - 8, x_hi + 8); ax6.set_ylim(-13, float(g.z_top(ys)) + 12)
    ax6.set_aspect(1.6); ax6.axis('off')
    ax6.text(x_hi + 6, -12, 'vertical scale ×1.6, sill dashed', ha='right', fontsize=7, color='#8a949e')

    # ---- seam face ----
    ax4 = fig.add_subplot(gs[4, 0])
    _section(ax4, board, [g.seams[1] - g.pocket_t/2, 0, 0], [1, 0, 0], LONG)
    for y in g.mag_y:
        ax4.add_patch(plt.Circle((y, g.mag_z), g.mag_d/2, fc='#7f8c99', ec=INK, lw=0.6, zorder=6))
        ax4.text(y, g.mag_z - g.pocket_d/2 - 3, 'Ø%.1f × %.1f deep' % (g.pocket_d, g.pocket_t),
                 ha='center', va='top', fontsize=7.2, color='#2a333c')
    _dim(ax4, (g.depth + 5, 0), (g.depth + 5, g.tip_t), '%.1f' % g.tip_t, vert=True, fs=7)
    ax4.annotate('teardrop roof, 45° —\nprints on the vertical face', xy=(g.mag_y[1], g.mag_z + 4.2),
                 xytext=(g.mag_y[1] + 25, 32), **lab)
    ax4.annotate('pocket centre %.1f above the sill' % g.mag_z, xy=(g.mag_y[0] - 3, g.mag_z),
                 xytext=(-10, 34), **lab)
    ax4.set_title('Seam face — CA007 Ø%.0f × %.0f magnets' % (g.mag_d, g.mag_t),
                  fontsize=11, weight='bold', color=INK)
    ax4.set_xlim(-12, g.depth + 18); ax4.set_ylim(-14, 46); ax4.set_aspect(1.6); ax4.axis('off')
    ax4.text(g.depth + 16, -13, 'vertical scale ×1.6', ha='right', fontsize=7, color='#8a949e')

    # ---- one part on the A1 bed ----
    ax5 = fig.add_subplot(gs[4, 1])
    ax5.add_patch(Rectangle((0, 0), BED, BED, fc='#f7f7f5', ec=INK, lw=1.0))
    wmax = max(g.part_w)
    ox, oy = (BED - wmax)/2, (BED - g.depth)/2
    part3 = g.plan_outline().intersection(sbox(g.part_x[2], 0, g.part_x[3], g.depth))
    _poly(ax5, translate(part3, ox - g.part_x[2], oy).buffer(BRIM, join_style=2), fc='none',
          ec='#b6bec6', lw=0.7, ls='--')
    _poly(ax5, translate(part3, ox - g.part_x[2], oy), fc=CUT, lw=1.0, z=3)
    _dim(ax5, (ox, oy + g.depth + 8), (ox + wmax, oy + g.depth + 8), '%.0f' % wmax, fs=7.5)
    _dim(ax5, (ox + wmax + 10, oy), (ox + wmax + 10, oy + g.depth), '%.0f' % g.depth, vert=True, fs=7.5)
    ax5.text(BED/2, -8, 'A1 bed %.0f × %.0f — one part per plate, %.0f mm brim dashed'
             % (BED, BED, BRIM), ha='center', va='top', fontsize=7.8, color='#2a333c')
    ax5.text(ox + wmax/2, oy + g.depth/2, 'printed flat,\nas it sits,\nrunners down', ha='center',
             va='center', fontsize=8, color='#2a333c', zorder=5)
    ax5.set_title('Print layout — %d plates' % len(parts), fontsize=11, weight='bold', color=INK)
    ax5.set_xlim(-10, BED + 40); ax5.set_ylim(-30, BED + 25); ax5.set_aspect('equal'); ax5.axis('off')

    fig.suptitle('Window-sill draining board — general arrangement (%s)' % tag,
                 fontsize=15, weight='bold', color='#111', y=0.975)
    fig.text(0.5, 0.012, 'All dimensions in millimetres. Red dashes = seams between parts, red dots = '
             'magnet pairs. Sill, wall and window dashed for reference.', ha='center',
             fontsize=8.5, color='#666')
    p = OUT + 'windowsill-%s-schematic.png' % tag
    fig.savefig(p, bbox_inches='tight', facecolor='white'); plt.close(fig)
    return p


# ---------------------------------------------------------------- checks
def checks(g, board, parts):
    """The numbers reported with every build. Each returns (label, value, ok)."""
    r = g.pocket_d / 2
    out = []
    for i, p in enumerate(parts):
        out.append(('part %d — closed mesh, one body' % (i + 1), '%.1f cm³' % (p.volume/1000),
                    p.is_watertight and p.body_count == 1))
    ext = [p.bounds[1] - p.bounds[0] for p in parts]
    worst = max(max(e[0], e[1]) for e in ext) + 2*BRIM
    out.append(('largest part + brim vs A1 bed', '%.1f of %.0f' % (worst, BED), worst <= BED))
    span = parts[-1].bounds[1][0] - parts[0].bounds[0][0]
    out.append(('parts side by side', '%.2f (model %.1f)' % (span, g.width),
                abs(span - g.width) < 0.01))
    lap = sum(trimesh.boolean.intersection([a, b], engine='manifold').volume
              for a, b in zip(parts[:-1], parts[1:]))
    out.append(('overlap between neighbours', '%.3f mm³' % abs(lap), abs(lap) < 0.01))
    cover_top = min(float(g.z_top(y)) - (g.mag_z + r*np.sqrt(2)) for y in g.mag_y)
    cover_bot = g.mag_z - r
    out.append(('magnet pocket cover, top / bottom', '%.2f / %.2f mm' % (cover_top, cover_bot),
                min(cover_top, cover_bot) >= 1.6))
    if g.chan_w:
        near = min(abs(x - s) for x in g.channel_xs() for s in g.seams) - g.chan_w/2 - g.pocket_t
        out.append(('solid between channel and pocket', '%.1f mm' % near, near >= 1.6))
        roof = float(g.z_top(g.chan_y1)) - g.chan_d
        out.append(('cover over channel at its front end', '%.2f mm' % roof, roof >= 1.6))
        gap = (g.drip_y - g.drip_w/2) - g.chan_y1
        out.append(('channel end to drip groove', '%.1f mm' % gap, gap >= 2.0))
    out.append(('tip thickness', '%.2f mm' % g.tip_t, g.tip_t >= 4.0))
    return out


# ---------------------------------------------------------------- export
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
GREY_HEX = '#8E9089'                      # Bambu PLA Basic Grey
PLATE_GAP = 1 / 5                         # Bambu Studio lays plates out bed + 20% apart

def part_name(g, i):
    n = len(g.part_w)
    where = 'left end' if i == 0 else 'right end' if i == n - 1 else \
        'centre, plant pad' if i == n // 2 else 'middle'
    return 'Part %d — %s' % (i + 1, where)

def plate_origin(i, n):
    """Where Bambu Studio puts plate i of n: a grid ceil(sqrt(n)) wide, rows running -y."""
    cols = int(np.ceil(np.sqrt(n)))
    step = BED * (1 + PLATE_GAP)
    return np.array([(i % cols) * step, -(i // cols) * step, 0.0])

BBL_NS = ('xmlns="%s" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
          'requiredextensions="p"' % NS)

def _mesh_xml(mesh):
    v = ''.join('<vertex x="%.4f" y="%.4f" z="%.4f"/>' % tuple(p) for p in mesh.vertices)
    t = ''.join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in mesh.faces)
    return '<mesh><vertices>%s</vertices><triangles>%s</triangles></mesh>' % (v, t)

def _uuid(kind, i):
    return '%08x-0000-4000-8000-%012x' % (i, kind)

def export(g, parts, tag):
    """One STL per part, each at the origin; one Bambu Studio project 3MF with
    one part per plate.

    The 3MF is written in Bambu Studio's own project layout — mesh in
    3D/Objects/, a component per object, plates in model_settings.config —
    because Bambu Studio only reads plates from files that declare themselves
    as its own. A plain 3MF loses the plates and lands every part on plate 1,
    outside the bed — that is what v2 shipped. The layout was taken from a
    project Bambu Studio 2.08 wrote itself; `make slice-check` proves it by
    slicing every plate headless.
    """
    import zipfile
    n = len(parts)
    stls, local = [], []
    for i, p in enumerate(parts):
        m = p.copy()
        m.apply_translation(-m.bounds[0])                  # corner at the origin, z=0 underneath
        m.merge_vertices(); m.fix_normals()
        path = OUT + 'windowsill-part%d-%s.stl' % (i + 1, tag)
        m.export(path); stls.append(path)
        c = m.copy(); c.apply_translation(-(m.bounds[0] + m.bounds[1]) / 2)   # centred on itself
        local.append(c)

    comps, items, rels, objfiles = [], [], [], {}
    for i, c in enumerate(local):
        mesh_id, obj_id = 2*i + 1, 2*i + 2
        f = '3D/Objects/object_%d.model' % (i + 1)
        objfiles[f] = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" '
                       'xml:lang="en-US" %s>\n<metadata name="BambuStudio:3mfVersion">1</metadata>\n'
                       '<resources><object id="%d" p:UUID="%s" type="model">%s</object></resources>\n'
                       '<build/>\n</model>\n' % (BBL_NS, mesh_id, _uuid(1, mesh_id), _mesh_xml(c)))
        rels.append('<Relationship Target="/%s" Id="rel-%d" Type="http://schemas.microsoft.com/'
                    '3dmanufacturing/2013/01/3dmodel"/>' % (f, i + 1))
        comps.append('<object id="%d" p:UUID="%s" type="model"><components><component '
                     'p:path="/%s" objectid="%d" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 0 0 %.4f"/>'
                     '</components></object>' % (obj_id, _uuid(2, obj_id), f, mesh_id,
                                                 _uuid(3, mesh_id), -c.bounds[0][2]))
        x, y, _ = plate_origin(i, n) + [BED/2, BED/2, 0]
        items.append('<item objectid="%d" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 %.4f %.4f 0" '
                     'printable="1"/>' % (obj_id, _uuid(4, obj_id), x, y))

    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" %s>\n'
             '<metadata name="Application">BambuStudio-02.08.02.61</metadata>\n'
             '<metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             '<metadata name="Title">Window-sill draining board %s</metadata>\n'
             '<resources>%s</resources>\n<build p:UUID="%s">%s</build>\n</model>\n'
             % (BBL_NS, tag, ''.join(comps), _uuid(5, 0), ''.join(items)))
    ms = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n']
    for i, c in enumerate(local):
        ms.append('  <object id="%d">\n    <metadata key="name" value="%s"/>\n'
                  '    <metadata key="extruder" value="1"/>\n'
                  '    <part id="%d" subtype="normal_part">\n'
                  '      <metadata key="name" value="%s"/>\n'
                  '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 %.4f 0 0 0 1"/>\n'
                  '    </part>\n  </object>\n'
                  % (2*i + 2, part_name(g, i), 2*i + 1, part_name(g, i), -c.bounds[0][2]))
    for i in range(n):
        ms.append('  <plate>\n    <metadata key="plater_id" value="%d"/>\n'
                  '    <metadata key="plater_name" value="%s"/>\n'
                  '    <metadata key="locked" value="false"/>\n'
                  '    <model_instance>\n      <metadata key="object_id" value="%d"/>\n'
                  '      <metadata key="instance_id" value="0"/>\n'
                  '      <metadata key="identify_id" value="%d"/>\n    </model_instance>\n'
                  '  </plate>\n' % (i + 1, part_name(g, i), 2*i + 2, 100 + i))
    ms.append('  <assemble>\n  </assemble>\n</config>\n')

    # A Bambu Studio project must carry a complete settings block: with only a
    # key or two Bambu Studio 2.08 segfaults on load. src/bambu/ holds one that
    # Bambu Studio wrote from its own A1 0.4 / 0.20mm Standard / PLA Basic
    # system presets, with 4 walls, a 5 mm brim, supports off (auto-support
    # would fill the air channels) and the grey filament colour.
    ps = open(os.path.join(os.path.dirname(__file__), 'bambu', 'project_settings.config')).read()
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org'
          '/package/2006/content-types"><Default Extension="rels" ContentType="application/'
          'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" '
          'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '<Default Extension="config" ContentType="application/xml"/>'
          '<Default Extension="txt" ContentType="text/plain"/></Types>')
    rel_root = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.'
                'openxmlformats.org/package/2006/relationships"><Relationship Target='
                '"/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/'
                '3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    rel_model = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.'
                 'openxmlformats.org/package/2006/relationships">%s</Relationships>' % ''.join(rels))
    readme = ('Window-sill draining board %s\n%d parts, one per plate, PLA Basic Grey %s.\n'
              'Every part flat on the plate as modelled, runners down. No rotation.\n\n'
              'NO SUPPORTS. project_settings.config sets enable_support to 0.\n'
              'Nothing on this board is unsupported: the air channels underneath,\n'
              'the magnet pockets and the drip groove all have 45 degree roofs.\n'
              'If the slicer proposes support anywhere, the orientation is wrong.\n'
              % (tag, n, GREY_HEX))
    path = OUT + 'windowsill-%s.3mf' % tag
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', rel_root)
        z.writestr('3D/3dmodel.model', model)
        z.writestr('3D/_rels/3dmodel.model.rels', rel_model)
        for f, body in objfiles.items():
            z.writestr(f, body)
        z.writestr('Metadata/model_settings.config', ''.join(ms))
        z.writestr('Metadata/project_settings.config', ps)
        z.writestr('Metadata/README.txt', readme)
    return path, stls


# ---------------------------------------------------------------- readme
HISTORY = [
    ('v1', 'concept only, never shipped: 848 wide, 2.5° fall, flat base'),
    ('v2', 'first shipped: 845 wide to the re-measured sill, 3.5° fall, underside '
           'runners with air channels for the ridged tile, front magnet pockets moved '
           'back to keep 1.6 mm cover. Its 3MF opens with every part off the bed — '
           'use v3'),
    ('v3', 'geometry unchanged from v2; the 3MF is now a Bambu Studio project, one '
           'part per plate, with the print settings built in'),
]

def readme(g, parts, tag, res):
    n = len(parts)
    vols = [p.volume/1000 for p in parts]
    rows = '\n'.join('| %s | %.0f × %.0f × %.0f | %.0f cm³ |' % (
        part_name(g, i), *(p.bounds[1] - p.bounds[0]), vols[i]) for i, p in enumerate(parts))
    chk = '\n'.join('| %s | %s |' % (lbl.replace('—', '·'), val if ok else '**FAIL** ' + val)
                    for lbl, val, ok in res)
    hist = '\n'.join('| %s | %s |' % h for h in HISTORY)
    files = '\n'.join('├── windowsill-part%d.stl' % (i + 1) for i in range(n))
    r = g.pocket_d / 2
    txt = f"""# Window-sill draining board

## Why this exists

Water and soap collect on the bathroom window sill above the bath, then dribble
down the wall. I wanted a draining board that fits the sill exactly, sends
everything into the bath instead, and gives the plant a level place to sit — in
the style of the silicone draining mat we already have in the kitchen.

## What it is

A ribbed draining board for an {g.sill_w:.0f} × {g.sill_d:.0f} mm tiled sill, printed in
{n} parts on a Bambu Lab A1 and held together with magnets. The top falls
{g.slope_deg:.1f}° towards the bath and runs {g.overhang:.0f} mm past the sill edge, so
run-off drops into the bath rather than down the wall. A level
{g.pad:.0f} × {g.pad:.0f} mm pad in the middle takes a plant pot.

Everything below is generated from the model itself, so the numbers match the
files in this folder.

![Views](windowsill-{tag}-views.png)

## Dimensions

| | |
|---|---|
| Overall | {g.width:.0f} wide × {g.depth:.0f} deep ({g.sill_d:.0f} on the sill + {g.overhang:.0f} overhang) |
| Thickness | {g.back_t:.1f} at the window, {g.tip_t:.1f} at the front edge |
| Fall | {g.slope_deg:.1f}° — {g.back_t - g.tip_t:.1f} mm over the depth |
| Plant pad | {g.pad:.0f} × {g.pad:.0f}, level, top at {g.pad_z:.1f} — {g.pad_y0:.0f} from the window, {g.sill_d - g.pad_y1:.0f} from the sill edge |
| Rims | {g.rim_w:.0f} wide, {g.rim_h:.0f} above the surface, back and both ends; front open |
| Ribs | {len(g.rib_plans())}, tapering {g.rib_wb:.1f} → {g.rib_wf:.1f} wide, {g.rib_h:.1f} tall, {g.rib_pitch:.2f} pitch |

| Part | Size (mm) | Material |
|---|---|---|
{rows}

Total {sum(vols):,.0f} cm³ of solid model; the printed weight depends on the
infill, so read it from the slicer.

![Schematic](windowsill-{tag}-schematic.png)

## How it goes together

```mermaid
flowchart LR
    P1["Part 1<br/>left end"] -->|"2 magnet pairs"| P2["Part 2"]
    P2 -->|"2 magnet pairs"| P3["Part 3<br/>plant pad"]
    P3 -->|"2 magnet pairs"| P4["Part 4"]
    P4 -->|"2 magnet pairs"| P5["Part 5<br/>right end"]
```

Part 1 is the left end as you stand in the bath facing the window.

## How water leaves it

```mermaid
flowchart TD
    A["Splash lands on the ribs"] --> B["Runs down the {g.slope_deg:.1f}° fall<br/>between the ribs"]
    B --> C{{"Meets the plant pad?"}}
    C -->|"yes"| D["The prow sends it<br/>round either side"]
    C -->|"no"| E
    D --> E["Crosses the open front edge"]
    E --> F["Drops off the {g.overhang:.0f} mm overhang"]
    F -->|"a film creeping back underneath"| G["Stopped by the drip groove"]
    F --> H["Into the bath"]
    G --> H
```

## Features

- **Tapered ribs** running downhill, {g.rib_wb:.1f} mm at the back narrowing to
  {g.rib_wf:.1f} mm, like the kitchen mat. Bottles and soap sit on the rib tops, out
  of the water. The seams between parts always fall midway between two ribs.
- **Level plant pad** with a prow behind it. Water running down the slope meets
  the prow's two angled faces and is steered round the pad instead of ponding
  against it.
- **Drip groove** — a {g.drip_w:.1f} × {g.drip_d:.1f} mm V under the overhang,
  {g.drip_y - g.sill_d:.0f} mm past the sill edge. Any water creeping back along the
  underside drops off there instead of reaching the wall.
- **Runners and air channels underneath.** The sill is ridged split-face tile,
  and its grooves run along the sill, so a flat base would hold water in them
  where it could never dry. Instead the board stands on {g.chan_pitch - g.chan_w:.1f} mm
  runners with {g.chan_n} channels per part between them, {g.chan_w:.1f} wide and
  {g.chan_d:.1f} tall, running from the window to just past the wall face. The
  channel roofs are 45° gables, so they print without support.
- **Magnets, not glue, between parts.** {2*len(g.mag_y)*len(g.seams)} CA007
  Ø{g.mag_d:.0f} × {g.mag_t:.0f} mm magnets in teardrop pockets, two pairs per seam, so the
  board lifts apart for cleaning.
- **No seam under the pot.** {n} parts, the centre one carrying the whole pad.

## Printing

| | |
|---|---|
| Printer | Bambu Lab A1, 0.4 nozzle |
| Layer | 0.20 mm |
| Walls | 4 loops |
| Material | PLA Basic Grey |
| Supports | None — the 3MF has supports switched off |
| Orientation | Flat, runners down, as laid out in the 3MF |
| Plates | {n}, one part each |
| Brim | {BRIM:.0f} mm — the largest part plus brim is {max(max(p.bounds[1][:2] - p.bounds[0][:2]) for p in parts) + 2*BRIM:.0f} of {BED:.0f} mm |

Print part 1 first and try it on the sill before printing the rest: it checks
the fit against the reveal and over the front edge trim.

Files: `windowsill.3mf` is a Bambu Studio project with all {n} parts, one per
plate, and the settings above already in it (A1 0.4 nozzle, 0.20mm Standard,
PLA Basic). Open it, pick a plate, slice and print.
`windowsill-part1.stl` … `windowsill-part{n}.stl` are the same geometry separately.

## Fitting the magnets

Each seam face has two pockets, Ø{g.pocket_d:.1f} × {g.pocket_t:.1f} mm deep, so a magnet sits
flush or just below the face. Polarity matters: every magnet in a **right-hand**
end must show the same pole outward, and every magnet in a **left-hand** end the
opposite pole, so any part mates with its neighbour.

1. Stack all {2*len(g.mag_y)*len(g.seams)} magnets into one column and mark the top face of the
   stack with a pen. Take them off one at a time without flipping them.
2. **Right-hand ends** (parts 1–{n - 1}): glue each magnet in **marked face out**.
3. **Left-hand ends** (parts 2–{n}): glue each magnet in **marked face in**.
4. Before the glue sets, offer each pair of parts together — they should pull
   in, not push apart. Fix a flipped magnet now; it is much harder later.

Use a gel superglue (CA), a small drop in the pocket, and keep glue off the
seam faces.

## Care

Wipe it down with warm water and let it dry. Every so often, lift the parts
apart, rinse them and wipe the sill underneath. Keep the water warm rather than
hot — PLA starts to soften around 55–60 °C, so no dishwasher. The window gets
no direct sun, so PLA is fine here; on a sunny sill, print it in PETG or ASA
instead.

## Checks run at build time

| Check | Result |
|---|---|
{chk}

Mesh volumes are compared, not triangle counts: the boolean and hull
libraries tessellate flat regions a few triangles differently between
versions, which changes how the shape is written down and not the shape
itself. `make verify` rebuilds this revision and checks it.

## Repository layout

```
.                             latest revision, aliased in the root
├── README.md                 this file (regenerated every revision)
├── CLAUDE.md                 working rules for the project
├── LICENSE                   CERN-OHL-S v2
├── Makefile                  make vNN — build and ship in one step
├── requirements.txt          pinned build dependencies
├── views.png  schematic.png  latest renders
├── windowsill.3mf            latest, all parts, one per plate
{files}
├── revisions/                every shipped version, exactly as shipped
│   └── vNN/                  deliverables + geometry.py it was built from
├── alt/silldrain/            a parallel design, set aside — not printed
└── src/                      the generator
    ├── geomNN.py             the model — all parameters live here
    ├── render.py             z-buffer renderer for the views
    ├── build.py              one command: views, schematic, README, 3MF, STLs
    ├── ship.py               copies a build into revisions/ and the root
    └── verify.py             rebuilds a revision and diffs it against shipped
```

Build everything from the model, where NN is the revision:

```
make vNN
```

which is `python3 src/build.py geomNN vNN` followed by the copy into
`revisions/vNN/` and the root. G-code is not kept here — it is tied to the
printer, filament and calibration state, so slice it locally from the 3MF.

## Licence

CERN Open Hardware Licence Version 2 — Strongly Reciprocal (CERN-OHL-S v2).
The full text is in [LICENSE](LICENSE).

You may use, make, modify and sell this design. If you distribute a modified
version — as files or as printed parts — the licence requires you to release
your modified source under CERN-OHL-S v2 as well, and to state what you
changed. Modified designs therefore stay publicly available.

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
    concept = '--concept' in sys.argv[3:]
    os.makedirs(OUT, exist_ok=True)
    g = importlib.import_module(mod)
    board = g.make_board()
    parts = g.make_parts(board)
    res = checks(g, board, parts)
    print(schematic(g, board, parts, tag))
    print(views(g, parts, tag, concept))
    if not concept:
        path, stls = export(g, parts, tag)
        print(path); [print(s) for s in stls]
        back = list(trimesh.load(path).geometry.values())
        vb, vm = sum(m.volume for m in back), sum(p.volume for p in parts)
        stl_v = sum(trimesh.load(s).volume for s in stls)
        res.append(('shipped 3MF vs model volume', '%d objects, %.1f vs %.1f cm³'
                    % (len(back), vb/1000, vm/1000),
                    len(back) == len(parts) and abs(vb - vm) < 1.0))
        res.append(('shipped STLs vs model volume', '%.1f vs %.1f cm³' % (stl_v/1000, vm/1000),
                    abs(stl_v - vm) < 1.0))
        print(readme(g, parts, tag, res))
    for label, val, ok in res:
        print('CHECK %-40s %-32s %s' % (label, val, 'ok' if ok else 'FAIL'))
    if not all(ok for _, _, ok in res):
        sys.exit('checks failed — fix before shipping')
