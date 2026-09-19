import numpy as np

def _basis(azim, elev):
    a, e = np.radians(azim), np.radians(elev)
    d = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
    right = np.cross([0, 0, 1.0], d); right /= np.linalg.norm(right)
    up = np.cross(d, right)
    return right, up, d

def render(items, azim=-55, elev=26, W=1000, H=760, ss=2,
           bg=(1.0, 1.0, 1.0), light=None, margin=0.06,
           outline=True):
    """items: list of (mesh, rgb tuple). Orthographic, flat-shaded, z-buffered."""
    W, H = W*ss, H*ss
    right, up, d = _basis(azim, elev)
    if light is None:            # headlight, offset up and to the left
        L = 0.55*d - 0.40*right + np.array([0, 0, 0.80])
    else:
        L = np.array(light, float)
    L /= np.linalg.norm(L)

    tris, cols, norms = [], [], []
    for mesh, col in items:
        v = mesh.vertices[mesh.faces]
        tris.append(v)
        norms.append(mesh.face_normals)
        cols.append(np.tile(np.array(col, float), (len(v), 1)))
    tris = np.concatenate(tris); norms = np.concatenate(norms); cols = np.concatenate(cols)

    P = tris.reshape(-1, 3)
    u = P @ right; vv = P @ up; dep = P @ d
    u = u.reshape(-1, 3); vv = vv.reshape(-1, 3); dep = dep.reshape(-1, 3)

    su = (u.max() - u.min()) or 1; sv = (vv.max() - vv.min()) or 1
    scale = min(W*(1-2*margin)/su, H*(1-2*margin)/sv)
    px = (u - (u.min()+u.max())/2) * scale + W/2
    py = -(vv - (vv.min()+vv.max())/2) * scale + H/2

    zbuf = np.full((H, W), -1e9)
    img = np.zeros((H, W, 3)); img[:] = bg
    idbuf = np.full((H, W), -1, dtype=np.int32)

    shade = 0.54 + 0.50*np.clip(norms @ L, 0, 1)
    face_col = np.clip(cols * shade[:, None], 0, 1)

    order = np.argsort(dep.mean(axis=1))
    for i in order:
        x0, x1 = px[i], py[i]
        minx = max(int(np.floor(x0.min())), 0); maxx = min(int(np.ceil(x0.max()))+1, W)
        miny = max(int(np.floor(x1.min())), 0); maxy = min(int(np.ceil(x1.max()))+1, H)
        if minx >= maxx or miny >= maxy:
            continue
        ax, ay = x0[0], x1[0]; bx, by = x0[1], x1[1]; cx, cy = x0[2], x1[2]
        area = (bx-ax)*(cy-ay) - (by-ay)*(cx-ax)
        if abs(area) < 1e-9:
            continue
        ys, xs = np.mgrid[miny:maxy, minx:maxx]
        xs = xs + 0.5; ys = ys + 0.5
        w0 = ((bx-ax)*(ys-ay) - (by-ay)*(xs-ax)) / area
        w1 = ((xs-ax)*(cy-ay) - (ys-ay)*(cx-ax)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any():
            continue
        z = w2*dep[i, 0] + w1*dep[i, 1] + w0*dep[i, 2]
        sub = zbuf[miny:maxy, minx:maxx]
        hit = m & (z > sub)
        if not hit.any():
            continue
        sub[hit] = z[hit]
        img[miny:maxy, minx:maxx][hit] = face_col[i]
        idbuf[miny:maxy, minx:maxx][hit] = i

    if outline:
        z = zbuf.copy()
        gx = np.abs(np.diff(z, axis=1, prepend=z[:, :1]))
        gy = np.abs(np.diff(z, axis=0, prepend=z[:1, :]))
        step = max(np.percentile(np.abs(z[z > -1e8]), 99) * 0.004, 0.35)
        edge = ((gx > step) | (gy > step)) & (idbuf >= 0)
        img[edge] = img[edge] * 0.66

    img = img.reshape(H//ss, ss, W//ss, ss, 3).mean(axis=(1, 3))
    return np.clip(img, 0, 1)


def trim(img, bg=1.0, pad=6):
    m = np.any(np.abs(img - bg) > 0.01, axis=2)
    if not m.any():
        return img
    ys, xs = np.where(m)
    y0, y1 = max(ys.min()-pad, 0), min(ys.max()+pad+1, img.shape[0])
    x0, x1 = max(xs.min()-pad, 0), min(xs.max()+pad+1, img.shape[1])
    return img[y0:y1, x0:x1]
