#!/usr/bin/env python3
"""
Masque des séraphins de Sainte-Sophie (plaques Fossati, 1847-49) — modèle paramétrique v2.

Géométrie relevée sur le masque exposé au musée d'histoire de Sainte-Sophie
(vidéo YouTube IfUzFmLskxk, vues frontale + oblique) et vérifiée sur la photo du
plafond (Wikimedia Commons). Hauteurs mesurées par parallaxe (modèle de caméra affine).

Repère : cercle unité étiré en ellipse  x = a·u,  y = b·v   (a/b = 0.705 mesuré).
Hauteur : z = HC · z_rel   (HC = hauteur du centre, mesurée ≈ 0.31·b).
8 branches, angles nominaux φ_k = 90° + 45°·k. Par défaut (arcs=1) ces angles sont des
fractions du périmètre : les 8 pointes partagent le bord en 8 arcs de longueur égale
(pointes diagonales à ~50° réels de l'horizontale, mesuré 50-51° sur la photo frontale du
musée ; le cercle étiré donnait 55°). Symétrie : 2 miroirs (axes), plus d'ordre 8 exact.

Points            rayon r      angle         z_rel   rôle
  T_k  pointe      1            φ_k           0       touche le bord
  R_k  encoche     RR = 0.79    φ_k + 22.5°   0       fond plat entre deux pointes
  V_k  creux       RV = 0.57    φ_k + 22.5°   0.70    épaule entre deux branches
  M_k  arête       RM = 0.57    φ_k           0.365   pli en gouttière de la branche
  P_k  pointe int. RP = 0.29    φ_k           0.925   étoile centrale
  Q_k  creux int.  RQ = 0.265   φ_k + 22.5°   0.715   fond du losange central
  C    centre      0                          1       sommet

Option --fleche f (défaut 0) : crêtes T-V cintrées en plan, arc de parabole de flèche f·longueur
(mesuré f ≈ 0.028 sur les deux photos du musée) ; les 4 facettes voisines deviennent des portions
de cône (lisses, développables). Les autres arêtes restent droites (mesuré).

Facettes (triangles, toutes planes si fleche = 0) :
  branche k     (T_k,V_k-1,M_k) (T_k,M_k,V_k) (V_k-1,M_k,P_k) (M_k,V_k,P_k)
                -> gouttière T_k-M_k-P_k (vallée ~51° sur T-M, ~37° sur M-P), chevron V-M-V (vallée ~20°).
                   Schéma des plis confirmé de visu au musée ; seules les hauteurs restent
                   incertaines (voir README.md).
  entre-branche (T_k,V_k,R_k) (R_k,V_k,T_k+1)
  étoile        losange creux (C,P_k,V_k,P_k+1) : 4 facettes autour de Q_k
                (C,P_k,Q_k) (C,Q_k,P_k+1) (P_k,V_k,Q_k) (Q_k,V_k,P_k+1)
                -> diagonale C-Q-V en vallée, comme la gouttière des branches
  rebord        plat z=0 entre l'arc d'ellipse et T_k-R_k-T_k+1

Sorties : STL (relief plein + plaque de fond), SVG 2D des plis (montagne bleu,
vallée vert pointillé, contour rouge), SVG ombré, JSON des sommets.
NB : le SVG 2D est une PROJECTION verticale, pas un développé : les longueurs y sont
raccourcies (ex. T-V 49.4 mm projeté pour 52.8 mm réel avec l'ancien jeu de paramètres) et les sommets R, V, C ne sont pas
développables (déficits angulaires +19°, -8°, +6°). Inutilisable tel quel comme patron
à plier ; correct pour du zinc repoussé ou de l'impression 3D.

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
    ratio=0.705,  # a/b : BA 2 vues musée (analyse/ba2v.py), ±0.005 formel
    hc=31.0,      # hauteur du centre (mm) : 0.31·b ±0.02 formel, 0.29-0.35 plausible
    base=2.0,     # épaisseur de la plaque de fond (mm)
    RR=0.79, RV=0.57, RM=0.57, RP=0.29, RQ=0.265,
    ZR=0.0, ZM=0.365, ZP=0.925, ZC=1.0, ZQ=0.715,
    ZV=0.70,      # <0 : calculé pour que le losange central soit plan (≈0.60)
                  # RQ=0 : losange plié en 2 sur C-V, sans point Q
    arc=8,        # subdivisions de l'arc de bord par 22.5°
    fleche=0.0,   # cintrage en plan des crêtes T-V, en fraction de leur longueur (mesuré 0.028) ;
                  # 0 : crêtes droites (polyèdre pur)
    seg=16,       # segments par crête cintrée
    arcs=1,       # 1 : pointes à arcs égaux sur le bord (mesuré) ; 0 : cercle étiré (ancien)
)


def zv_plan(p):
    """Hauteur de V rendant le losange (C,P_k,V_k,P_k+1) plan."""
    return p["ZC"] - (p["ZC"] - p["ZP"]) * p["RV"] / (p["RP"] * math.cos(math.radians(22.5)))


def build(p):
    b = p["b"]
    a = p["ratio"] * b
    zv = p["ZV"] if p["ZV"] >= 0 else zv_plan(p)
    pts, faces = [], []

    # Partage du bord : arcs=1 -> les angles nominaux (90+45k...) sont des fractions du
    # PÉRIMÈTRE de l'ellipse (8 arcs de longueur égale, relevé photo frontale musée) ;
    # arcs=0 -> ancien comportement, angle paramétrique du cercle étiré.
    N = 720
    cum = [0.0]
    for i in range(N):
        tm = math.radians(90 + (i + 0.5) * 360 / N)
        cum.append(cum[-1] + math.hypot(a * math.sin(tm), b * math.cos(tm)))

    def warp(deg):
        if not p["arcs"]:
            return deg
        s = (deg - 90) / 360
        tours, s = math.floor(s), s - math.floor(s)
        cible = s * cum[-1]
        lo, hi = 0, N
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if cum[mid] <= cible else (lo, mid)
        f = (cible - cum[lo]) / (cum[hi] - cum[lo])
        return 90 + 360 * tours + (lo + f) * 360 / N

    def add(r, deg, z):
        t = math.radians(warp(deg))
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

    # Crêtes T-V cintrées (fleche > 0) : arc de parabole plan (Bézier quadratique)
    #   X(t) = (1-t)·T + t·V + 4·f·L·t(1-t)·n ,  t ∈ [0,1]
    # L = longueur en plan de la corde, n = normale horizontale à la corde, du côté opposé à
    # l'axe de la branche (vers l'encoche R). Hauteur z linéaire : pas de cintrage en hauteur.
    # Les 4 facettes qui bordent la crête deviennent des portions de CÔNE (sommet M ou R,
    # directrice = l'arc) : surfaces lisses et développables, sans pli supplémentaire.
    _LISSES.clear(); _CRETES.clear()

    def crete(ti, vi, mi):
        if p["fleche"] <= 0:
            return [ti, vi]
        (x0, y0, z0), (x1, y1, z1), (xm, ym, _) = pts[ti], pts[vi], pts[mi]
        L = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        if (xm - x0) * nx + (ym - y0) * ny > 0:
            nx, ny = -nx, -ny
        ch = [ti]
        for i in range(1, p["seg"]):
            t = i / p["seg"]; w = 4 * p["fleche"] * L * t * (1 - t)
            pts.append((x0 + t * (x1 - x0) + w * nx, y0 + t * (y1 - y0) + w * ny, z0 + t * (z1 - z0)))
            ch.append(len(pts) - 1)
        ch.append(vi)
        for i in range(len(ch) - 1):
            _CRETES.add(tuple(sorted((ch[i], ch[i + 1]))))
        return ch

    def cone(apex, ch):
        for i in range(len(ch) - 1):
            faces.append((apex, ch[i], ch[i + 1]))
        for q in ch[1:-1]:
            _LISSES.add(tuple(sorted((apex, q))))

    gauche = [crete(T[k], V[(k - 1) % n], M[k]) for k in range(n)]   # crête T_k - V_k-1
    droite = [crete(T[k], V[k], M[k]) for k in range(n)]             # crête T_k - V_k
    rim = []
    for k in range(n):
        km, kp = (k - 1) % n, (k + 1) % n
        cone(M[k], gauche[k]); cone(M[k], droite[k])       # facettes de la branche
        cone(R[k], droite[k]); cone(R[k], gauche[kp])      # facettes de l'entre-branche
        faces += [(V[km], M[k], Pk[k]), (M[k], V[k], Pk[k])]
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


_LISSES, _CRETES = set(), set()   # génératrices de cône (pas des plis) ; segments de crête cintrée


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
def solide(pts, faces, rim, base):
    """Triangles du solide fermé : relief + paroi + plaque de fond à z = -base."""
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
    return tris


def write_stl(path, pts, faces, rim, base, tris=None):
    tris = tris or solide(pts, faces, rim, base)
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


def fold_edges(pts, faces, min_deg=1.0, lisses=None):
    """Plis = arêtes partagées par deux facettes non coplanaires.
    Renvoie [(i, j, 'M'|'V')] : M = montagne (convexe), V = vallée."""
    adj = {}
    for fi, f in enumerate(faces):
        for i in range(3):
            adj.setdefault(tuple(sorted((f[i], f[(i + 1) % 3]))), []).append(fi)
    cmin = math.cos(math.radians(min_deg))
    out = []
    for (i, j), fs in adj.items():
        if len(fs) != 2 or (i, j) in (_LISSES if lisses is None else lisses):
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
    if _CRETES:   # une crête cintrée = un seul pli, quel que soit le nombre de segments
        folds = [f for f in folds if tuple(sorted(f[:2])) not in _CRETES] + [(0, 0, "M")] * 16
    print(f"{len(faces)} {'triangles' if _CRETES else 'facettes'}, {len(folds)} plis "
          f"({sum(k == 'M' for *_, k in folds)} montagne / {sum(k == 'V' for *_, k in folds)} vallée), "
          f"ZV={ids['zv']:.3f}, ellipse {2*a:.0f}x{2*p['b']:.0f} mm, relief {p['hc']:.0f} mm, "
          f"STL {n} triangles -> {args.out}/")


if __name__ == "__main__":
    main()
