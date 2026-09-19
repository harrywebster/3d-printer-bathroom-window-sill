# SPDX-License-Identifier: CERN-OHL-S-2.0
# Copyright (C) 2026 Harry Webster
# Source location: https://github.com/harrywebster/3d-printer-bathroom-window-sill
"""SillDrain — bathroom window-sill draining board, v1 geometry. Every
dimension used anywhere else in the repo (schematic labels, README numbers,
the STL/3MF export) is read from here. Nothing is hand-typed downstream.

Axes, used everywhere in this repo:

    x   across the 850 mm run, 0 at the left end, increasing rightward
        across all N_TILES tiles
    y   across the 220 mm sill depth, 0 at the BACK edge (under the window
        glass), increasing towards the FRONT edge (overhanging the bath)
    z   up from a tile's flat underside; z=0 is the bottom face that rests
        on the sill

The sill (850 x 220 mm) is far bigger than the A1 bed (256 x 256 x 256 mm),
so the run is split into N_TILES identical-width tiles, each printed flat and
joined edge to edge with a tongue-and-groove alignment feature and glued-in
CA007 D6 x 3 mm magnets. Tile 2 (the centre one, so no seam runs under the
pot) carries a flat plant pad; the others are plain drain surface.

Each tile is a wedge: thick at the back (against the window) and thin at the
front (the sill's edge), so the top face falls towards the bath. Past the
sill's own front edge every tile keeps going for NOSE mm as a cantilevered
drip nose, so run-off drops clear of the wall instead of tracking down it. A
drip groove cut into the underside of that nose breaks the water film before
it can creep back along the underside to the wall.
"""
import numpy as np
import trimesh
from shapely.geometry import Polygon as SPoly

NAME = "SillDrain"

# ---------------------------------------------------------------- footprint
N_TILES = 5             # tiles across the run
TILE_W = 170.0           # mm, width of one tile (5 x 170 = 850 exactly)
SILL_D = 220.0           # mm, depth of sill the board rests on
TOTAL_W = N_TILES * TILE_W   # 850.0 mm, overall run width

# --------------------------------------------------------- wedge (drainage)
THICK_BACK = 16.0        # mm, top thickness at y=0 (against the window)
THICK_FRONT = 4.0        # mm, top thickness at y=SILL_D (the sill's front edge)
# gives close to a 3 degree fall across the SILL_D span, from back to front

# -------------------------------------------------------------- back lip
BACK_LIP_D = 4.0         # mm, depth (in y) of the upstand at the back edge
BACK_LIP_H = 6.0         # mm, height of the lip above the local sloped surface

# ------------------------------------------------------- front drip nose
NOSE = 25.0               # mm, extra depth cantilevered past the sill's front edge
TILE_D = SILL_D + NOSE    # 245.0 mm, full tile depth as printed
THICK_TIP = 3.0           # mm, top thickness at the drip tip, y=TILE_D

DRIP_GROOVE_W = 3.0        # mm, width (in y) of the underside drip groove
DRIP_GROOVE_D = 1.5        # mm, depth (in z) cut up from the underside
DRIP_GROOVE_Y = TILE_D - 10.0   # 235 mm: 10 mm back from the tip

# ----------------------------------------------------- drain ribs (sill zone)
RIB_H = 1.5               # mm, rib height above the local sloped surface
RIB_W = 3.0                # mm, rib width (RIB_W == 2*RIB_H: a true semicircle)
RIB_PITCH = 12.0            # mm, spacing across the tile's x width
RIB_Y_MARGIN = BACK_LIP_D + 1.0   # ribs start just clear of the back lip

# ------------------------------------------------- centre plant pad (tile 2)
PAD_TILE_INDEX = 2        # 0-indexed; tile 2 of 0..4 is the centre tile
PAD = 120.0                 # mm, square pad, level (not sloped)
PAD_RIM_H = 2.0              # mm, raised rim height above the pad
PAD_RIM_T = 3.0              # mm, rim wall thickness
PAD_NOTCH_W = 15.0            # mm, gap in the front rim edge so overflow can drain
PAD_APRON = 5.0               # mm, ribs are kept this far clear of the pad footprint

PAD_X0 = (TILE_W - PAD) / 2.0     # 25.0, tile-local
PAD_X1 = PAD_X0 + PAD              # 145.0
PAD_Y0 = (SILL_D - PAD) / 2.0     # 50.0
PAD_Y1 = PAD_Y0 + PAD               # 170.0
PAD_YC = (PAD_Y0 + PAD_Y1) / 2.0    # 110.0

# --------------------------------------------------------------- joinery
TONGUE_W = 4.0             # mm, tongue/groove height (in z)
TONGUE_H = 3.0              # mm, tongue protrusion / groove depth (in x)
TONGUE_CLR = 0.25            # mm, running clearance per side
JOINT_Y0, JOINT_Y1 = 0.0, SILL_D   # joinery runs across the sill zone only

MAG_D = 6.2                 # mm, magnet pocket diameter (D6 magnet + 0.2 mm glue fit)
MAG_DEPTH = 3.1               # mm, magnet pocket depth (3 mm magnet + 0.1 mm glue fit)
# Pocket positions "near" the back/middle/front of the sill zone (see the
# product brief). The literal front position (y=200) sits where the wedge has
# tapered to 5.1 mm thick -- too thin to hold a 6.2 mm pocket without
# breaching both the top and bottom faces. Moved to y=165, where the wedge is
# still 7.0 mm thick, leaving ~0.4 mm of material on each side of the pocket.
MAG_Y = (20.0, 110.0, 165.0)

EMBED = 0.05    # mm, small deliberate overlap so union/difference booleans
                # never meet at an exactly coincident face

# ------------------------------------------------------------- slope maths
K1 = (THICK_BACK - THICK_FRONT) / SILL_D    # fall per mm across the sill zone
K2 = (THICK_FRONT - THICK_TIP) / NOSE       # fall per mm across the nose


def top_z(y):
    """Height of the top (drain) surface at depth y. Piecewise linear: one
    slope across the sill zone, a shallower one across the nose."""
    y = np.asarray(y, dtype=float)
    return np.where(y <= SILL_D, THICK_BACK - K1 * y,
                    THICK_FRONT - K2 * (y - SILL_D))


def mid_z(y):
    """Mid-thickness height at depth y (bottom is always flat at z=0)."""
    return top_z(y) / 2.0


# ------------------------------------------------------------------ helpers
# Two axis-remapping matrices, both determinant +1 (pure rotations) so
# triangle winding -- and therefore face normals -- survive the transform.

_YZ_TO_XYZ = np.array([[0, 0, 1, 0],
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1.]])


def extrude_yz(points, x0, x1):
    """Extrude a profile in the (y, z) plane along x, from x0 to x1."""
    poly = SPoly(points)
    m = trimesh.creation.extrude_polygon(poly, x1 - x0)
    m.apply_transform(_YZ_TO_XYZ)
    m.apply_translation([x0, 0, 0])
    return m


def extrude_xz(points, y0, y1):
    """Extrude a profile in the (x, z) plane along y, from y0 to y1."""
    poly = SPoly(points)
    m = trimesh.creation.extrude_polygon(poly, y1 - y0)
    M = np.array([[1, 0, 0, 0],
                   [0, 0, -1, y1],
                   [0, 1, 0, 0],
                   [0, 0, 0, 1.]])
    m.apply_transform(M)
    return m


def shear_to_slope(mesh, k, z_at_y0, embed=0.0):
    """Shear a mesh built flat (baseline z=0) so that baseline instead follows
    the line z = z_at_y0 - k*y -- i.e. top_z or mid_z, which are each linear
    within one zone. `embed` drops the whole mesh slightly further, so a
    feature built to sit exactly on a surface actually overlaps it a little,
    which keeps boolean unions from ever meeting at a coincident face."""
    M = np.array([[1, 0, 0, 0],
                   [0, 1, 0, 0],
                   [0, -k, 1, z_at_y0 - embed],
                   [0, 0, 0, 1.]])
    mesh.apply_transform(M)
    return mesh


# -------------------------------------------------------------- tile solids
def _wedge(x0, x1):
    """The sloped slab: flat bottom, sloped top across the sill zone,
    continuing at a shallower slope across the drip nose."""
    pts = [(0, 0), (TILE_D, 0), (TILE_D, THICK_TIP),
           (SILL_D, THICK_FRONT), (0, THICK_BACK)]
    return extrude_yz(pts, x0, x1)


def _back_lip(x0, x1):
    """Upstand along the back edge, its top following the local slope plus
    BACK_LIP_H, so it stays a constant height above the drain surface."""
    y0, y1 = 0.0, BACK_LIP_D
    z0, z1 = float(top_z(y0)), float(top_z(y1))
    pts = [(y0, z0 - EMBED), (y1, z1 - EMBED),
           (y1, z1 + BACK_LIP_H), (y0, z0 + BACK_LIP_H)]
    return extrude_yz(pts, x0, x1)


def _drip_groove(x0, x1):
    """Cutter: a rectangular undercut channel in the underside of the nose,
    breaking surface tension so water drips clear instead of tracking back
    towards the wall."""
    ya, yb = DRIP_GROOVE_Y - DRIP_GROOVE_W / 2, DRIP_GROOVE_Y + DRIP_GROOVE_W / 2
    pts = [(ya, -1.0), (yb, -1.0), (yb, DRIP_GROOVE_D), (ya, DRIP_GROOVE_D)]
    return extrude_yz(pts, x0 - 0.5, x1 + 0.5)


def _rib_profile(x_center):
    """A true semicircle (RIB_W == 2*RIB_H), flat side down -- a rounded
    capsule-topped rib, per the sink-mat brief."""
    r = RIB_W / 2.0
    n = 12
    return [(x_center + r * np.cos(a), r * np.sin(a))
            for a in np.linspace(np.pi, 0.0, n + 1)]


def _rib(x_center, y0, y1):
    m = extrude_xz(_rib_profile(x_center), y0, y1)
    return shear_to_slope(m, K1, THICK_BACK, embed=EMBED)


def _rib_x_positions():
    n = int(TILE_W // RIB_PITCH)
    span = (n - 1) * RIB_PITCH
    start = (TILE_W - span) / 2.0
    return [start + i * RIB_PITCH for i in range(n)]


def _ribs(has_pad):
    ribs = []
    for x in _rib_x_positions():
        if has_pad and (PAD_X0 - RIB_W / 2 < x < PAD_X1 + RIB_W / 2):
            segs = []
            if RIB_Y_MARGIN < PAD_Y0 - PAD_APRON:
                segs.append((RIB_Y_MARGIN, PAD_Y0 - PAD_APRON))
            if PAD_Y1 + PAD_APRON < SILL_D:
                segs.append((PAD_Y1 + PAD_APRON, SILL_D))
        else:
            segs = [(RIB_Y_MARGIN, SILL_D)]
        for y0, y1 in segs:
            ribs.append(_rib(x, y0, y1))
    return ribs


def _tongue():
    """Left-edge alignment ridge, proud of the face, following the local
    mid-thickness slope."""
    pts = [(-TONGUE_H, -TONGUE_W / 2), (EMBED, -TONGUE_W / 2),
           (EMBED, TONGUE_W / 2), (-TONGUE_H, TONGUE_W / 2)]
    m = extrude_xz(pts, JOINT_Y0, JOINT_Y1)
    return shear_to_slope(m, K1 / 2.0, THICK_BACK / 2.0)


def _groove():
    """Cutter: right-edge alignment slot, sized with a running clearance so
    the neighbouring tile's tongue seats with no gap."""
    d = TONGUE_H + TONGUE_CLR
    w2 = TONGUE_W / 2 + TONGUE_CLR
    pts = [(-d, -w2), (EMBED, -w2), (EMBED, w2), (-d, w2)]
    m = extrude_xz(pts, JOINT_Y0, JOINT_Y1)
    m.apply_translation([TILE_W, 0, 0])
    return shear_to_slope(m, K1 / 2.0, THICK_BACK / 2.0)


def _magnet_cutter(x_face, side, y):
    """Cutter: a cylindrical magnet pocket recessed into a mating face,
    centred at that face's local mid-thickness."""
    over = 1.0
    h = MAG_DEPTH + over
    cyl = trimesh.creation.cylinder(radius=MAG_D / 2, height=h, sections=32)
    cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    cx = (x_face + (MAG_DEPTH - over) / 2 if side == 'left'
          else x_face - (MAG_DEPTH - over) / 2)
    cyl.apply_translation([cx, y, float(mid_z(y))])
    return cyl


def _plant_pad(body):
    """Flatten a level, rimmed pad into the sloped surface. The pad slab is
    unioned across the full footprint depth (z=0 upward) after the sloped
    material above the pad height is cut away, so the join is a short apron
    rather than a fragile vertical cliff."""
    z_pad = float(top_z(PAD_YC))
    cut = trimesh.creation.box(
        bounds=[[PAD_X0, PAD_Y0, z_pad - EMBED], [PAD_X1, PAD_Y1, 60.0]])
    body = trimesh.boolean.difference([body, cut], engine='manifold')

    slab = trimesh.creation.box(bounds=[[PAD_X0, PAD_Y0, 0.0], [PAD_X1, PAD_Y1, z_pad]])
    body = trimesh.boolean.union([body, slab], engine='manifold')

    outer = trimesh.creation.box(
        bounds=[[PAD_X0, PAD_Y0, z_pad], [PAD_X1, PAD_Y1, z_pad + PAD_RIM_H]])
    inner = trimesh.creation.box(
        bounds=[[PAD_X0 + PAD_RIM_T, PAD_Y0 + PAD_RIM_T, z_pad - 1.0],
                [PAD_X1 - PAD_RIM_T, PAD_Y1 - PAD_RIM_T, z_pad + PAD_RIM_H + 1.0]])
    rim = trimesh.boolean.difference([outer, inner], engine='manifold')

    xc = (PAD_X0 + PAD_X1) / 2.0
    notch = trimesh.creation.box(
        bounds=[[xc - PAD_NOTCH_W / 2, PAD_Y1 - PAD_RIM_T - 1.0, z_pad - 1.0],
                [xc + PAD_NOTCH_W / 2, PAD_Y1 + 1.0, z_pad + PAD_RIM_H + 1.0]])
    rim = trimesh.boolean.difference([rim, notch], engine='manifold')

    return trimesh.boolean.union([body, rim], engine='manifold')


def make_tile(i, has_pad=None):
    """Build tile `i` (0..N_TILES-1) in its own tile-local coordinates
    (x in [0, TILE_W]). `has_pad` defaults to True only for PAD_TILE_INDEX."""
    if has_pad is None:
        has_pad = (i == PAD_TILE_INDEX)

    pieces = [_wedge(0.0, TILE_W), _back_lip(0.0, TILE_W)]
    pieces += _ribs(has_pad)
    if i > 0:
        pieces.append(_tongue())
    body = trimesh.boolean.union(pieces, engine='manifold')

    if has_pad:
        body = _plant_pad(body)

    cutters = [_drip_groove(0.0, TILE_W)]
    if i < N_TILES - 1:
        cutters.append(_groove())
    for y in MAG_Y:
        if i > 0:
            cutters.append(_magnet_cutter(0.0, 'left', y))
        if i < N_TILES - 1:
            cutters.append(_magnet_cutter(TILE_W, 'right', y))
    body = trimesh.boolean.difference([body] + cutters, engine='manifold')
    body.merge_vertices()
    body.fix_normals()
    return body


def make_tiles():
    """The five tiles, each still in its own tile-local x -- positioning them
    into the 850 mm run is the caller's job (build.py does it for the
    renders; each tile prints and ships as its own part)."""
    return [make_tile(i) for i in range(N_TILES)]


def make_assembly(tiles=None):
    """The five tiles translated into the full 850 mm run, for the assembled
    renders and schematic."""
    tiles = make_tiles() if tiles is None else tiles
    out = []
    for i, t in enumerate(tiles):
        m = t.copy()
        m.apply_translation([i * TILE_W, 0, 0])
        out.append(m)
    return out


if __name__ == '__main__':
    print('%s: %d tiles, %.0f x %.0f mm run, %.0f mm sill depth + %.0f mm nose'
          % (NAME, N_TILES, TOTAL_W, SILL_D, NOSE))
    for i, t in enumerate(make_tiles()):
        print('tile %d  %.1f cm3  closed=%s bodies=%d  bounds %s'
              % (i, t.volume / 1000, t.is_watertight, t.body_count,
                 np.round(t.bounds, 1).tolist()))
