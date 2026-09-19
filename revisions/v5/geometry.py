# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""Bathroom window-sill draining board — v5 geometry. Every parameter lives here.

v5: flat base. The first v4 print (part 1) lifted at the edges within its
first 10 layers. The underside runners gave the first layers only ~37% contact,
as thin separate strips 240 mm long, and the channels filled the first 3 mm
(15 layers) — exactly where it lifted. The base is now flat and full-contact.
The air gap over the ridged tile, which is what the runners were for, now
comes from the owner's stick-on rubber feet; `feet_xy` says where they go.
Everything else is v4 unchanged.

v4 changed no geometry. It changed the print settings carried in the 3MF
(src/bambu/project_settings.config): stock 0.20mm Standard with 10% infill
instead of 15%, declared as a change to the preset so Bambu Studio keeps it.

v2, from the v1 sign-off review:
  - 845 wide: the sill re-measured, and the board now fills it exactly
  - 3.5 degree fall instead of 2.5, for the best drainage — more filament,
    same look
  - underside runners with air channels between them: the sill is ridged
    split-face tile whose grooves run along the sill, so a flat base would
    trap water in them. Runners, not separate feet — between separate feet
    the base would be an unsupported ceiling; the channels have 45 degree
    roofs and print without support
  - front magnet pockets moved back so every pocket has >= 1.6 mm cover
    (v1's front pocket had 0.85 mm under the drain surface)

Axes, used everywhere in this repo:

    x  along the sill, 0 at the centre, + to the right seen from the bath
       (standing in the bath facing the window, part 1 is on your left)
    y  front-to-back, 0 at the window (back), + towards the bath
    z  up, 0 on the sill

The board is a solid wedge: thick against the window, thin at the bath edge, so
the top falls towards the bath. It sits on the sill and runs `overhang` past
the sill's front edge so the run-off drops clear of the wall instead of
tracking down it; a V drip groove under that overhang breaks any film that
tries to creep back underneath.

Too long for the A1 bed (256 mm), so it is cut into five parts along x. The
centre part carries the whole plant pad, so no seam runs under the pot. Parts
are held together by CA007 D6 x 3 mm magnets glued into pockets in each seam
face.
"""
import numpy as np, trimesh
from shapely.geometry import Polygon, box as sbox

# ---- the sill (measured) ----
sill_w, sill_d = 845.0, 220.0          # re-measured for v2
fit_clr = 0.0                          # the board is the full 845

# ---- board ----
overhang = 20.0                        # past the sill's front edge, over the bath
depth = sill_d + overhang              # 240 — front to back, as printed
width = sill_w - 2*fit_clr             # 845
slope_deg = 3.5                        # fall of the top towards the bath
back_t = 19.0                          # thickness of the drain surface at the window
tip_ch = 1.0                           # chamfer on the top front edge
front_r = 10.0                         # plan radius on the two outer front corners

# ---- parts: widths left to right, sum = width. Odd count so the pad is whole ----
part_w = [169.0] * 5

# ---- rims: back full width, ends as far as the sill edge. Front is open ----
rim_w, rim_h, rim_ch = 6.0, 3.0, 1.0   # width, height above the surface, top chamfer
end_rim_ramp = 10.0                    # end rims ramp down to the surface over this length

# ---- ribs: tapered, running downhill, as on the kitchen mat ----
rib_pitch = 8.45                       # 169/20, so every seam falls midway between ribs
rib_wb, rib_wf = 3.2, 1.2              # width at the back / front end (0.4 multiples)
rib_h = 1.6                            # height above the surface
rib_top_in = 0.4                       # top is inset, so the rib sides are drafted
rib_y0, rib_y1 = rim_w + 8.0, 200.0    # rib field, from behind to in front
rib_clear = 4.0                        # minimum gap from a rib to the pad or a rim

# ---- plant pad: 120 x 120, level, exactly central on the sill ----
pad = 120.0
pad_r = 6.0                            # plan corner radius
pad_y0 = (sill_d - pad) / 2            # 50 from the window
pad_y1 = pad_y0 + pad                  # 170, 50 from the sill edge
prow_y = rim_w + 10.0                  # apex of the wedge that parts water around the pad

# ---- magnets: CA007, D6 x 3 mm, one pair per pocket position per seam ----
mag_d, mag_t = 6.0, 3.0
pocket_d, pocket_t = 6.2, 3.2          # 0.2 over for glue, magnet sits 0.2 below the face
mag_y = (30.0, 120.0)                  # pocket centres; 120 is as far forward as keeps 1.6 cover
mag_z = 5.4                            # pocket centre height

# ---- drip groove under the overhang ----
drip_y = sill_d + 11.0                 # 11 past the sill edge, 9 in from the tip
drip_w, drip_d = 3.2, 1.6              # V groove, 45 degree flanks — no bridge

# ---- underside: flat from v5, on stick-on rubber feet ----
# No channels (v2-v4 had runners; they lifted off the plate). The feet are
# bought parts stuck on after printing, not modelled: these are where they go,
# four per part, all on the part of the board that sits on the sill.
chan_w = 0.0                           # no underside channels
foot_d = 10.0                          # assumed foot diameter, for the drawings only
foot_inset_x = 20.0                    # centre, in from each end of a part
foot_y = (25.0, 195.0)                 # centres, from the window — both on the sill

# ---- derived ----
tan_s = np.tan(np.radians(slope_deg))
def z_top(y):
    """Height of the drain surface at depth y."""
    return back_t - np.asarray(y, float) * tan_s

tip_t = float(z_top(depth))            # thickness at the bath edge
pad_z = float(z_top(pad_y0)) + rib_h   # pad top — level with the rib tops at its back edge
seams = list(np.cumsum([-width/2] + part_w)[1:-1])
part_x = list(np.cumsum([-width/2] + part_w))
rib_xs = [x for x in np.arange(-width/2, width/2, rib_pitch) + rib_pitch/2
          if abs(x) + rib_wb/2 <= width/2 - rim_w - rib_clear]

# ------------------------------------------------------------------ helpers
YZ_TO_XYZ = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1.]])

def along_x(profile, x0, x1):
    """Extrude a (y, z) profile along x from x0 to x1."""
    m = trimesh.creation.extrude_polygon(profile, x1 - x0)
    m.apply_transform(YZ_TO_XYZ)
    m.apply_translation([x0, 0, 0])
    return m

def on_slope(poly, below, above, top_inset=0.0):
    """Hull of a plan outline dropped `below` under the drain surface and raised
    `above` it. The surface is a plane, so the hull is exact."""
    pts = []
    for p, dz in ((poly, -below), (poly.buffer(-top_inset) if top_inset else poly, above)):
        xy = np.array(p.exterior.coords)
        pts.append(np.column_stack([xy, z_top(xy[:, 1]) + dz]))
    return trimesh.convex.convex_hull(np.vstack(pts))

def round_corners(poly, r):
    return poly.buffer(-r, join_style=1).buffer(r, join_style=1)

# ------------------------------------------------------------------ plan shapes
def plan_outline():
    """Square at the back (it meets the reveals), rounded on the outer front corners."""
    r = front_r
    front = sbox(-width/2 + r, depth/2, width/2 - r, depth - r).buffer(r, resolution=24)
    return sbox(-width/2, 0, width/2, depth/2 + 1).union(front).intersection(
        sbox(-width/2, 0, width/2, depth))

def pad_plan():
    return round_corners(sbox(-pad/2, pad_y0, pad/2, pad_y1), pad_r)

def prow_plan():
    return Polygon([(-pad/2, pad_y0 + 0.5), (0, prow_y), (pad/2, pad_y0 + 0.5)])

def rib_w(y):
    return rib_wb + (rib_wf - rib_wb) * (y - rib_y0) / (rib_y1 - rib_y0)

def rib_plans():
    """Plan outline of every rib segment. Ribs that would run into the pad or
    its prow keep only the stretch in front of the pad."""
    out = []
    for x in rib_xs:
        spans = [(rib_y0, rib_y1)]
        if abs(x) - rib_wb/2 < pad/2 + rib_clear:
            spans = [(pad_y1 + 6.0, rib_y1)]
        for ya, yb in spans:
            wa, wb = rib_w(ya), rib_w(yb)
            p = Polygon([(x - wa/2, ya), (x + wa/2, ya), (x + wb/2, yb), (x - wb/2, yb)])
            out.append(round_corners(p, 0.5))
    return out

def channel_xs():
    """Centres of the underside channels (none from v5)."""
    return []

def feet_xy():
    """Where the stick-on rubber feet go: four per part, (x, y) centres."""
    return [(x, y) for x0, x1 in zip(part_x[:-1], part_x[1:])
            for x in (x0 + foot_inset_x, x1 - foot_inset_x) for y in foot_y]

# ------------------------------------------------------------------ solids
def wedge():
    """The sloped slab, top front edge chamfered, flat underneath."""
    prof = Polygon([(0, 0), (depth, 0), (depth, tip_t - tip_ch),
                    (depth - tip_ch, tip_t), (0, back_t)])
    slab = along_x(prof, -width/2, width/2)
    clip = trimesh.creation.extrude_polygon(plan_outline(), 60)
    return trimesh.boolean.intersection([slab, clip], engine='manifold')

def rim_bar(x0, x1, y_end, ramp):
    """A rim running from the window to y_end, following the slope, top chamfered."""
    c = rim_ch
    def section(y, h):
        zt = float(z_top(y))
        return [(x0, y, 0), (x1, y, 0), (x1, y, zt + h - c), (x0, y, zt + h - c),
                (x0 + c, y, zt + h), (x1 - c, y, zt + h)]
    pts = section(0, rim_h) + section(y_end - ramp, rim_h) + section(y_end, 0.01)
    return trimesh.convex.convex_hull(np.array(pts))

def rims():
    back = trimesh.creation.box(extents=[width, rim_w, back_t + rim_h])
    back.apply_translation([0, rim_w/2, (back_t + rim_h)/2])
    ch = trimesh.convex.convex_hull(np.array(      # chamfer the front top edge of the back rim
        [[x, y, z] for x in (-width/2 - 1, width/2 + 1)
         for y, z in ((rim_w - rim_ch - 0.01, back_t + rim_h + 1), (rim_w + 1, back_t + rim_h + 1),
                      (rim_w + 1, back_t + rim_h - rim_ch - 0.01))]))
    back = trimesh.boolean.difference([back, ch], engine='manifold')
    ends = [rim_bar(-width/2, -width/2 + rim_w, sill_d, end_rim_ramp),
            rim_bar(width/2 - rim_w, width/2, sill_d, end_rim_ramp)]
    return [back] + ends

def ribs():
    return [on_slope(p, 0.3, rib_h, rib_top_in) for p in rib_plans()]

def plant_pad():
    """Level 120 x 120 pad, with a sloped prow behind it pointing at the window.

    Water coming down the slope meets the prow's two faces obliquely and runs
    along them to either side of the pad instead of ponding against its back.
    Hull of the pad block and the prow apex: the flat top stays exactly the
    120 x 120 square, the prow ramps from the pad's back edge down to the apex.
    """
    xy = np.array(pad_plan().exterior.coords)
    top = np.column_stack([xy, np.full(len(xy), pad_z)])
    bot = np.column_stack([xy, z_top(xy[:, 1]) - 0.3])
    apex = np.array([[0, prow_y, float(z_top(prow_y)) + 0.6],
                     [0, prow_y, float(z_top(prow_y)) - 0.3]])
    return trimesh.convex.convex_hull(np.vstack([top, bot, apex]))

def teardrop():
    """(y, z) outline of one magnet pocket: circle plus a 45 degree roof."""
    r = pocket_d / 2
    return [Polygon([(y + r*np.cos(a), mag_z + r*np.sin(a))
                     for a in np.linspace(0, 2*np.pi, 48, endpoint=False)]
                    + [(y, mag_z + r*np.sqrt(2))]).convex_hull for y in mag_y]

def magnet_pockets():
    """Teardrop pockets straddling every seam, 3.2 deep into each face. The
    45 degree roof prints without support on the vertical seam face."""
    return [along_x(t, s - pocket_t, s + pocket_t) for t in teardrop() for s in seams]

def drip_groove():
    v = Polygon([(drip_y - drip_w/2, -0.5), (drip_y + drip_w/2, -0.5),
                 (drip_y + drip_w/2 - 0.5, 0.0), (drip_y, drip_d), (drip_y - drip_w/2 + 0.5, 0.0)])
    return along_x(v, -width/2 - 1, width/2 + 1)

def underside_cuts():
    return [drip_groove()]

def make_board():
    body = trimesh.boolean.union([wedge(), *rims(), *ribs(), plant_pad()], engine='manifold')
    return trimesh.boolean.difference([body, *magnet_pockets(), *underside_cuts()], engine='manifold')

def make_parts(board=None):
    """The board cut at the seams, left to right."""
    board = make_board() if board is None else board
    parts = []
    for x0, x1 in zip(part_x[:-1], part_x[1:]):
        b = trimesh.creation.box(bounds=[[x0, -1, -1], [x1, depth + 1, 60]])
        parts.append(trimesh.boolean.intersection([board, b], engine='manifold'))
    return parts

# ------------------------------------------------------------------ props for the renders only
def props():
    """Sill, wall, reveals, a pot and a soap bottle — context, never exported."""
    sill = trimesh.creation.box(bounds=[[-sill_w/2, 0, -40], [sill_w/2, sill_d, -0.05]])
    wall = trimesh.creation.box(bounds=[[-sill_w/2 - 120, sill_d, -190], [sill_w/2 + 120, sill_d + 1, -0.05]])
    wall_face = trimesh.creation.box(bounds=[[-sill_w/2 - 120, sill_d - 40, -190], [sill_w/2 + 120, sill_d, -40]])
    reveals = [trimesh.creation.box(bounds=[[-sill_w/2 - 60, 0, -40], [-sill_w/2, sill_d, 70]]),
               trimesh.creation.box(bounds=[[sill_w/2, 0, -40], [sill_w/2 + 60, sill_d, 70]])]
    frame = trimesh.creation.box(bounds=[[-sill_w/2, -45, -40], [sill_w/2, 0, 70]])
    pot = trimesh.creation.cone(radius=62, height=260, sections=64)
    pot = trimesh.boolean.intersection([pot, trimesh.creation.box(bounds=[[-80, -80, 0], [80, 80, 105]])],
                                       engine='manifold')
    pot.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    pot.apply_translation([0, 0, 105])
    rim = trimesh.creation.annulus(r_min=52, r_max=60, height=12, sections=64)
    rim.apply_translation([0, 0, 99])
    pot = trimesh.util.concatenate([pot, rim])
    pot.apply_translation([0, (pad_y0 + pad_y1)/2, pad_z])
    rng = np.random.default_rng(3)
    leaves = []
    for _ in range(9):
        s = trimesh.creation.icosphere(subdivisions=2, radius=rng.uniform(26, 38))
        s.apply_scale([1, 1, 1.25])
        a, r = rng.uniform(0, 2*np.pi), rng.uniform(0, 34)
        s.apply_translation([r*np.cos(a), (pad_y0 + pad_y1)/2 + r*np.sin(a),
                             pad_z + 115 + rng.uniform(0, 60)])
        leaves.append(s)
    bottle = trimesh.creation.cylinder(radius=28, height=150, sections=48)
    bottle.apply_translation([-300, 90, float(z_top(90)) + rib_h + 75])
    pump = trimesh.creation.cylinder(radius=8, height=30, sections=24)
    pump.apply_translation([-300, 90, float(z_top(90)) + rib_h + 165])
    soap = trimesh.creation.box(extents=[90, 60, 28])
    soap.apply_translation([300, 110, float(z_top(110)) + rib_h + 14])
    return dict(tile=[sill, wall, wall_face, *reveals, frame], sill=[sill, wall, wall_face], pot=[pot],
                leaves=leaves, bottle=[bottle, pump], soap=[soap])


if __name__ == '__main__':
    print('width %.1f  depth %.1f  back %.1f  tip %.2f  pad top %.2f' % (width, depth, back_t, tip_t, pad_z))
    print('seams', [round(s, 1) for s in seams], ' ribs', len(rib_xs))
    parts = make_parts()
    for i, p in enumerate(parts):
        print('part %d  %.0f cm3  closed=%s bodies=%d  bounds %s' % (
            i + 1, p.volume/1000, p.is_watertight, p.body_count, np.round(p.bounds, 1).tolist()))
