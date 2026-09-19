# CLAUDE.md — working rules for this repo

Adopted from the EasyPick case repo
(https://github.com/harrywebster/3d-printer-tepe-easy-pick-toothpicks-case),
where most of these rules were learned from a failure. The failure is noted
where it applies. Rules specific to this board are added as they are earned.

## One session at a time

Only one Claude session works in this directory. On 19 Sep 2026 a second
session ran here concurrently, overwrote the model, build script, Makefile and
this file, and built STLs at the wrong width. Its work is kept in
`alt/silldrain/` and is **not** the design being built. If files change under
you that you did not change, stop and ask — do not merge or overwrite.

## Sign-off before CAD

Before any printable file exists, a concept is rendered and signed off:

1. `make concept-vN` renders the views PNG and the schematic PNG from
   `src/geomNN.py` into `build/vN/`, and prints the check numbers. Nothing
   printable is written.
2. Present both PNGs in the conversation with an ASCII sketch of the key
   dimensions, what changed, the open questions, and the check numbers.
3. Only after the user signs off: add the printable stage (STLs, 3MF,
   README, `ship.py`, `verify.py`) to the same `build.py`, and ship
   `make vN`. Changes asked for at sign-off go into a new geometry module,
   exactly like any other revision.

> **Why.** Signing off pictures is far cheaper than re-slicing and reprinting
> — especially here, where one board is five plates and most of a spool.

## Every revision, without being asked

1. Bump the version: copy `src/geomNN.py` to `geomNN+1.py`, change parameters
   there. Never edit a released revision in place.
2. Run the single command — it is the only path to shipped files. Once the
   printable stage exists that is `make vNN`: `src/build.py` into
   `build/vNN/`, then `src/ship.py` copying that into `revisions/vNN/` and the
   root aliases. `ship.py` only ever copies; it never regenerates anything.
3. The build regenerates **all** of: views PNG, schematic PNG, README.md,
   colour 3MF, every part STL. Never generate one without the others. (The
   concept stage is the one exception, and it ships nothing.)
4. Shipping refuses to overwrite an existing `revisions/vNN`. If you hit that
   guard, the answer is almost always to bump the version, not `FORCE=1`.
5. Present the newly built files in the conversation for verification before
   they are treated as done. Report the check numbers alongside them. A
   revision is not finished when the build exits zero; it is finished when the
   files have been looked at.

> **Why one script.** In the EasyPick repo the exporter's import line was
> edited by hand and silently kept pointing at the old geometry module. Two
> revisions shipped stale files that were printed before anyone noticed.
> Nothing may reintroduce a path where the pictures and the printable files
> come from different models.

## Verification is part of the build, not a manual step

`build.py` computes these on every build and exits non-zero if any fail:

| Check | Requirement |
|---|---|
| Every part mesh | closed, one body |
| Largest part + 5 mm brim | fits the A1 bed, 256 × 256 |
| Parts side by side | span equals `width`, zero overlap between neighbours |
| Magnet pocket cover | ≥ 1.6 mm above and below every pocket |
| Rubber feet (v5+) | every foot on the sill (none under the overhang), ≥ 5 mm from a seam |
| Channels (v2–v4 only) | ≥ 1.6 mm to a pocket and over the roof; ≥ 2 mm short of the drip groove |
| Tip thickness | ≥ 4 mm |
| Shipped 3MF and STLs reloaded vs model volume | must match |

Then, after every ship: **`make slice-check`**. It does two things:

1. **Declarations.** Every setting in the 3MF that differs from its stock
   system preset must be listed in `different_settings_to_system`. It fails
   on anything unlisted.
2. **Slicing.** It opens the shipped 3MF in Bambu Studio headless and slices
   every plate using only the settings inside the file. It must report one
   part per plate, no supports, and `Success`.

Only the two together prove that Bambu Studio, headless *and* in the app, reads
the file the way we meant.

> **Why slice-check.** v2 passed every volume check and still shipped a 3MF
> that Bambu Studio opened with all five parts on plate 1, off the bed. A
> plain 3MF's plate list is ignored; only a file that declares itself a Bambu
> Studio project keeps its plates.

Report the numbers, don't assert "verified". Compare meshes by volume and
bounds, never byte-for-byte — the boolean and hull libraries tessellate flat
regions a few triangles differently between versions. A real regression moves
a volume or a bound.

> **Why the declaration check.** v3's 4 walls and 5 mm brim sliced fine
> headless, but they weren't declared as changes, so the app reset them to
> stock the moment the project was opened. The headless slicer doesn't do
> that reset, so slicing alone could never catch it.

> **Why the cover check.** v1's front magnet pocket sat at y = 100 with only
> 0.85 mm of plastic between its roof and the drain surface. Nothing checked
> it; it was found by hand while moving to v2.

## The 3MF is a Bambu Studio project

`build.py` writes Bambu Studio's own project layout (the layout Bambu Studio
2.08 writes itself): meshes in `3D/Objects/`, one component per object, an
`Application: BambuStudio` header, and plates in `model_settings.config`.

- **Plate positions:** plate *i* sits at column `i % cols`, row `i // cols`, where
  `cols = ceil(sqrt(n))`, spaced `256 × 1.2` apart, with rows running towards −y.
- **Settings block:** it must be complete. With only a key or two, Bambu
  Studio crashes on load; it crashed four times during testing on 19 Sep 2026.
  `src/bambu/project_settings.config` holds the A1 0.4 / 0.20mm Standard / PLA
  Basic system presets as Bambu Studio writes them, plus the grey filament
  colour.
- **Changing a setting:** every deliberate change must also be listed in
  `different_settings_to_system`, a list of `;`-separated keys: [process,
  one per filament, machine]. Anything unlisted is silently reset to stock
  when the app opens the project. Change print settings in that file, never
  by hand in the build. The README reads its print-settings table from it.
- **Stock values:** `src/bambu/presets.py` flattens the installed system
  presets to compare against. Where both define a key, the filament preset
  overrides the process preset (e.g. `pre_start_fan_time`).
- **Project files:** Bambu Studio saves the project back over the file it
  opened, with whatever presets and filaments the app has loaded (including
  the AMS's four filaments). That happened to the root `windowsill.3mf` at
  12:08 on 19 Sep 2026, and it was committed that way at v3. Before
  committing, check that the root 3MF still matches `revisions/vNN/`.
- **Headless CLI:** the system profiles use `inherits`, and the CLI does not
  follow it. Passed straight to `--load-settings`, they fall back to a
  200 × 200 bed. `make slice-check` doesn't pass them at all; it slices on the
  settings inside the 3MF.

## Dependencies

`requirements.txt` is pinned. `scipy`, `lxml`, `rtree` and `networkx` are
listed even though nothing imports them directly — trimesh loads them for
convex hulls, 3MF reading, proximity queries and `body_count`. Without them
the build dies part-way through, *after* writing some of the deliverables.
Don't prune them. The venv here is uv-managed (no pip inside it);
`make deps` uses `uv pip` when uv is present.

## Writing rules

- The README opens with **why the board was built**, then what it is.
- Never use "watertight" in user-facing text. It is the mesh-topology term and
  reads as a waterproofing claim — doubly misleading on a draining board. Say
  "closed mesh, one body".
- Every number in the README and on the drawings is interpolated from the
  geometry module at build time. No hand-typed dimensions — they go stale.
- State the care routine: warm water and a wipe, never hot (PLA softens at
  55–60 °C). The window gets no direct sun, so PLA is fine here.

## The sill (from the owner's photos, v2)

- 845 × 220, tiled in ridged split-face tile. The ridges run **along** the
  sill, parallel to the window.
- Front edge: square aluminium tile trim, dark tiled wall flush beneath it.
- Back: uPVC frame with a silicone bead where the tile meets it.

## Design invariants — don't break these silently

- **Flat base, full contact, no bottom-edge chamfer.** The whole footprint
  meets the plate *(EasyPick v4 lifted off the plate mid-print because of a
  1 mm bottom chamfer)*. Nothing is printed underneath except the drip groove.
  The air gap over the ridged tile, which stops water sitting in the tile
  grooves, comes from the owner's 20 stick-on Ø10 rubber feet: 4 per part,
  positions in `feet_xy()`, all on the sill. *(v2–v4 printed runners with
  45° air channels instead. v4 part 1 lifted at the edges in its first 10
  layers: thin separate strips, ~37% contact, through the first 3 mm.
  Removing them also cut each plate from 6.3 h to 4.8 h.)* Never print
  underside features in the first layers to replace the feet.
- **Overhangs ≥ 45°.** Magnet pockets are teardrops with a 45° roof; the drip
  groove is a V with 45° flanks. Nothing on this board needs support.
- **Feature sizes on line-width multiples** (0.4 mm). Rib widths, rim widths.
- **No seam under the plant pad.** An odd number of parts, the centre one
  carrying the whole pad.
- **Seams fall midway between ribs.** `rib_pitch` divides the part width so no
  rib is ever cut by a seam.
- **The top falls towards the bath everywhere except the pad.** Nothing may
  create a dam across the flow; the pad's prow exists so the pad itself isn't
  one.
- **Magnet polarity is part of the assembly, not the model.** Every left-hand
  seam face takes N outward and every right-hand one S outward, so any part
  mates with its neighbour. Say so wherever assembly is described.

## Printing

Bambu Lab A1, 0.4 nozzle, stock 0.20mm Standard (2 walls, no supports) with
two declared changes: 10% infill instead of 15%, and a 5 mm outer brim instead
of auto (edges lifted on the A1). PLA Basic Grey. One part per plate, flat base
down, as it sits on the sill. The project assigns every part to
filament 1; the owner's AMS has white in slot 1, so the part must be mapped to
the grey slot when sending.

Per `make slice-check` at v5: about 866 g and 23.2 h over five plates, 4.0–4.8
h each (v4 with runners: 919 g, 30.5 h). Most of what's left is inherent to a
solid 19 mm wedge: a sloped top puts solid layers and slow internal bridges
under the whole top surface. Measured on plate 1 at v4: 15% → 10% infill saves
17 min and 18.5 g. Top shell 5 → 4 layers saves
nothing (the 1 mm shell thickness wins). Thicker layers would show as steps on
the slope. Hollowing the underside is not the way to save more: it puts features
back into the first layers, which is what lifted at v4.

The owner's first print also jammed filament, which is a feed or filament
problem rather than the model: check the spool, the feed tube, and that the
part is mapped to the grey slot (slot 3, listed as PLA Matte).

G-code is not generated or kept in this repo. It is specific to the printer,
filament and calibration state, so slice it locally from the 3MF each time.
