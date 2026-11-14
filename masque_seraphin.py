#!/usr/bin/env python3
"""
Masque des séraphins de Sainte-Sophie (plaques Fossati, 1847-49) — modèle paramétrique v2.

Géométrie relevée sur le masque exposé au musée d'histoire de Sainte-Sophie
(vidéo YouTube IfUzFmLskxk, vues frontale + oblique) et vérifiée sur la photo du
plafond (Wikimedia Commons). Hauteurs mesurées par parallaxe (modèle de caméra affine).

Repère : cercle unité étiré en ellipse  x = a·u,  y = b·v   (a/b = 0.65 mesuré).
Hauteur : z = HC · z_rel   (HC = hauteur du centre, mesurée ≈ 0.35·b).
8 branches, angles φ_k = 90° + 45°·k, symétrie d'ordre 8 avec miroirs.

Points            rayon r      angle         z_rel   rôle
  T_k  pointe      1            φ_k           0       touche le bord
  R_k  encoche     RR = 0.76    φ_k + 22.5°   0       fond plat entre deux pointes
  V_k  creux       RV = 0.57    φ_k + 22.5°   0.53    épaule entre deux branches
  M_k  arête       RM = 0.60    φ_k           0.38    pli en gouttière de la branche
  P_k  pointe int. RP = 0.29    φ_k           0.81    étoile centrale
  Q_k  creux int.  RQ = 0.32    φ_k + 22.5°   0.70    fond du losange central
  C    centre      0                          1       sommet

Facettes (triangles, toutes planes) :
  branche k     (T_k,V_k-1,M_k) (T_k,M_k,V_k) (V_k-1,M_k,P_k) (M_k,V_k,P_k)
                -> gouttière T_k-M_k-P_k (vallée), chevron V-M-V (montagne)
  entre-branche (T_k,V_k,R_k) (R_k,V_k,T_k+1)
  étoile        losange creux (C,P_k,V_k,P_k+1) : 4 facettes autour de Q_k
                (C,P_k,Q_k) (C,Q_k,P_k+1) (P_k,V_k,Q_k) (Q_k,V_k,P_k+1)
                -> diagonale C-Q-V en vallée, comme la gouttière des branches
  rebord        plat z=0 entre l'arc d'ellipse et T_k-R_k-T_k+1

Sorties : STL (relief plein + plaque de fond), SVG 2D des plis (montagne bleu,
vallée vert pointillé, contour rouge), SVG ombré, JSON des sommets.

Usage : python3 masque_seraphin.py [--b 100 --ratio 0.65 --hc 35 ...]
"""
import argparse
import json
import math
import os
import struct

# ---------------------------------------------------------------- paramètres
P = dict(
    b=100.0,      # demi-hauteur de l'ellipse (mm) -> masque de 200 mm de haut
    ratio=0.65,   # a/b mesuré (0.63-0.68 selon les vues)
    hc=35.0,      # hauteur du centre (mm), mesuré ≈ 0.35·b
    base=2.0,     # épaisseur de la plaque de fond (mm)
    RR=0.76, RV=0.57, RM=0.60, RP=0.29, RQ=0.32,
    ZR=0.0, ZM=0.38, ZP=0.81, ZC=1.0, ZQ=0.70,
    ZV=0.53,      # <0 : calculé pour que le losange central soit plan (≈0.60)
                  # RQ=0 : losange plié en 2 sur C-V, sans point Q
    arc=8,        # subdivisions de l'arc de bord par 22.5°
)


def zv_plan(p):
    """Hauteur de V rendant le losange (C,P_k,V_k,P_k+1) plan."""
    return p["ZC"] - (p["ZC"] - p["ZP"]) * p["RV"] / (p["RP"] * math.cos(math.radians(22.5)))


def build(p):
    b = p["b"]
    a = p["ratio"] * b
    zv = p["ZV"] if p["ZV"] >= 0 else zv_plan(p)
    pts, faces = [], []

    def add(r, deg, z):
        t = math.radians(deg)
        pts.append((a * r * math.cos(t), b * r * math.sin(t), z * p["hc"]))
        return len(pts) - 1

    n = 8
    phi = [90 + 45 * k for k in range(n)]
    T = [add(1, f, 0) for f in phi]
    R = [add(p["RR"], f + 22.5, p["ZR"]) for f in phi]
    V = [add(p["RV"], f + 22.5, zv) for f in phi]
    M = [add(p["RM"], f, p["ZM"]) for f in phi]
    Pk = [add(p["RP"], f, p["ZP"]) for f in phi]
    C = add(0, 0, p["ZC"])
    Q = [add(p["RQ"], f + 22.5, p["ZQ"]) for f in phi] if p["RQ"] > 0 else None

    rim = []
    for k in range(n):
        km, kp = (k - 1) % n, (k + 1) % n
        faces += [(T[k], V[km], M[k]), (T[k], M[k], V[k]),
                  (V[km], M[k], Pk[k]), (M[k], V[k], Pk[k]),
                  (T[k], V[k], R[k]), (R[k], V[k], T[kp])]
        if Q:   # losange central creux, 4 facettes
            faces += [(C, Pk[k], Q[k]), (C, Q[k], Pk[kp]),
                      (Pk[k], V[k], Q[k]), (Q[k], V[k], Pk[kp])]
        else:
            faces += [(C, Pk[k], V[k]), (C, V[k], Pk[kp])]
        # rebord plat : éventail depuis R_k sur l'arc T_k -> T_k+1
        arc = [T[k]] + [add(1, phi[k] + 45 * i / (2 * p["arc"]), 0)
                        for i in range(1, 2 * p["arc"])] + [T[kp]]
        for i in range(len(arc) - 1):
            faces.append((R[k], arc[i], arc[i + 1]))
        rim += arc[:-1]

    def area2(f):
        (x0, y0, _), (x1, y1, _), (x2, y2, _) = (pts[i] for i in f)
        return (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)

    faces = [f if area2(f) > 0 else (f[0], f[2], f[1]) for f in faces]
    return pts, faces, rim, dict(T=T, R=R, V=V, M=M, P=Pk, Q=Q or [], C=C, zv=zv, a=a)


# ---------------------------------------------------------------- utilitaires
def sub(u, v):
    return (u[0] - v[0], u[1] - v[1], u[2] - v[2])


def cross(u, v):
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def unit(v):
    l = math.sqrt(sum(c * c for c in v)) or 1
    return tuple(c / l for c in v)


def normal(pts, f):
    return unit(cross(sub(pts[f[1]], pts[f[0]]), sub(pts[f[2]], pts[f[0]])))


# ---------------------------------------------------------------- STL
def write_stl(path, pts, faces, rim, base):
    tris = [tuple(pts[i] for i in f) for f in faces]
    bot = [(x, y, -base) for (x, y, _) in (pts[i] for i in rim)]
    c = (0.0, 0.0, -base)
    m = len(rim)
    for i in range(m):  # fond, normale -z
        tris.append((c, bot[(i + 1) % m], bot[i]))
    for i in range(m):  # paroi
        t0, t1 = pts[rim[i]], pts[rim[(i + 1) % m]]
        b0, b1 = bot[i], bot[(i + 1) % m]
        tris += [(t0, b0, b1), (t0, b1, t1)]
    with open(path, "wb") as fh:
        fh.write(b"masque seraphin Hagia Sophia".ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        for t in tris:
            nrm = unit(cross(sub(t[1], t[0]), sub(t[2], t[0])))
            fh.write(struct.pack("<12fH", *nrm, *t[0], *t[1], *t[2], 0))
    return len(tris)


# ---------------------------------------------------------------- SVG
def _svg_head(a, b, pad=6):
    w, h = 2 * (a + pad), 2 * (b + pad)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
            f'viewBox="{-a - pad} {-b - pad} {w} {h}">\n'
            f'<g transform="scale(1,-1)">\n')


def fold_edges(pts, faces, min_deg=1.0):
    """Plis = arêtes partagées par deux facettes non coplanaires.
    Renvoie [(i, j, 'M'|'V')] : M = montagne (convexe), V = vallée."""
    adj = {}
    for fi, f in enumerate(faces):
        for i in range(3):
            adj.setdefault(tuple(sorted((f[i], f[(i + 1) % 3]))), []).append(fi)
    cmin = math.cos(math.radians(min_deg))
    out = []
    for (i, j), fs in adj.items():
        if len(fs) != 2:
            continue
        f0, f1 = faces[fs[0]], faces[fs[1]]
        n0 = normal(pts, f0)
        if sum(a * b for a, b in zip(n0, normal(pts, f1))) >= cmin:
            continue
        w = next(k for k in f1 if k not in (i, j))
        d = sum(n0[t] * (pts[w][t] - pts[i][t]) for t in range(3))
        out.append((i, j, "M" if d < 0 else "V"))
    return out


def write_svg_lines(path, pts, faces, p, a):
    """Contour (rouge, découpe) + plis montagne (bleu) / vallée (vert pointillé)."""
    out = [_svg_head(a, p["b"])]
    for i, j, kind in fold_edges(pts, faces):
        (x0, y0, _), (x1, y1, _) = pts[i], pts[j]
        style = 'stroke="#1f4fd1"' if kind == "M" else 'stroke="#1a9a3a" stroke-dasharray="2,1.2"'
        out.append(f'<line x1="{x0:.3f}" y1="{y0:.3f}" x2="{x1:.3f}" y2="{y1:.3f}" '
                   f'{style} stroke-width="0.35"/>\n')
    out.append(f'<ellipse cx="0" cy="0" rx="{a:.3f}" ry="{p["b"]}" fill="none" '
               f'stroke="red" stroke-width="0.35"/>\n</g></svg>\n')
    open(path, "w").write("".join(out))


def shade(pts, faces, light=(0.08, 0.92, 0.38)):
    L = unit(light)
    gold_dark, gold_lit = (92, 62, 18), (250, 222, 140)
    res = []
    for f in faces:
        n = normal(pts, f)
        d = max(0.0, sum(n[i] * L[i] for i in range(3)))
        d = d ** 1.3
        col = tuple(int(gold_dark[i] + (gold_lit[i] - gold_dark[i]) * d) for i in range(3))
        res.append(col)
    return res


def write_svg_shaded(path, pts, faces, p, a, light=(0.08, 0.92, 0.38)):
    cols = shade(pts, faces, light)
    out = [_svg_head(a, p["b"])]
    for f, c in zip(faces, cols):
        d = " ".join(f"{pts[i][0]:.3f},{pts[i][1]:.3f}" for i in f)
        out.append(f'<polygon points="{d}" fill="rgb{c}" stroke="rgb{c}" stroke-width="0.25"/>\n')
    out.append("</g></svg>\n")
    open(path, "w").write("".join(out))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sortie")
    for k, v in P.items():
        ap.add_argument(f"--{k}", type=type(v), default=v)
    args = ap.parse_args()
    p = {k: getattr(args, k) for k in P}
    os.makedirs(args.out, exist_ok=True)
    pts, faces, rim, ids = build(p)
    a = ids["a"]
    n = write_stl(os.path.join(args.out, "masque.stl"), pts, faces, rim, p["base"])
    write_svg_lines(os.path.join(args.out, "masque_2d.svg"), pts, faces, p, a)
    write_svg_shaded(os.path.join(args.out, "masque_apercu.svg"), pts, faces, p, a)
    named = {f"{k}{i}": [round(c, 2) for c in pts[idx]]
             for k in ("T", "R", "V", "M", "P", "Q") for i, idx in enumerate(ids[k])}
    named["C"] = [round(c, 2) for c in pts[ids["C"]]]
    json.dump({"parametres": p, "ZV_calcule": round(ids["zv"], 3), "sommets_mm": named},
              open(os.path.join(args.out, "sommets.json"), "w"), indent=1, ensure_ascii=False)
    folds = fold_edges(pts, faces)
    print(f"{len(faces)} facettes, {len(folds)} plis "
          f"({sum(k == 'M' for *_, k in folds)} montagne / {sum(k == 'V' for *_, k in folds)} vallée), "
          f"ZV={ids['zv']:.3f}, ellipse {2*a:.0f}x{2*p['b']:.0f} mm, relief {p['hc']:.0f} mm, "
          f"STL {n} triangles -> {args.out}/")


if __name__ == "__main__":
    main()
