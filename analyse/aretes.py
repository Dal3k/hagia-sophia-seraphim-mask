#!/usr/bin/env python3
"""Test de rectitude des arêtes sur la photo oblique : un point pointé vers le milieu de
chaque arête, comparé à la corde entre ses deux sommets pointés.
Flèche = écart perpendiculaire ramené au milieu (hypothèse d'arc parabolique).
Sens : + = l'arête sort vers l'extérieur du relief (+z, « bombée »), d'après la caméra ajustée.
Usage : python3 analyse/ba2v.py --sauve analyse/donnees/ba2v_out.json
        python3 analyse/aretes.py"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ba2v

D = os.path.join(ba2v.ICI, "donnees")
fit = json.load(open(os.path.join(D, "ba2v_out.json")))
so = json.load(open(os.path.join(D, "musee_b_precis.json")))["museeB"]
ar = json.load(open(os.path.join(D, "musee_b_aretes.json")))["museeB_aretes"]
s, cam, arcs = fit["forme"], fit["cams"]["B"], fit["arcs"]
proj = lambda X: ba2v.projette(cam, X, 600, 800)
MM = 100.0  # b = 100 mm dans le modèle

fam = {}
for nom, p in ar.items():
    a, b = nom.split("-")
    if a not in so or b not in so:
        continue
    A, B = so[a], so[b]
    L = math.dist(A, B); ux, uy = (B[0] - A[0]) / L, (B[1] - A[1]) / L
    nx, ny = -uy, ux
    d = (p[0] - A[0]) * nx + (p[1] - A[1]) * ny
    t = ((p[0] - A[0]) * ux + (p[1] - A[1]) * uy) / L
    if not 0.15 < t < 0.85:
        continue
    f = d / (4 * t * (1 - t))                      # flèche au milieu, px
    Xa, Xb = ba2v.monde(a, s, arcs), ba2v.monde(b, s, arcs)
    Xm = tuple((1 - t) * u + t * v for u, v in zip(Xa, Xb))
    L3 = math.dist(Xa, Xb) * MM
    q0, q1 = proj(Xm), proj((Xm[0], Xm[1], Xm[2] + 0.01))
    sz = ((q1[0] - q0[0]) * nx + (q1[1] - q0[1]) * ny) / 1.0   # px perpendiculaires par mm de +z
    # écart dû au modèle lui-même (sommets pointés vs projetés) : non utilisé, on reste sur les pointés
    fam.setdefault(a[0] + "-" + b[0], []).append((nom, L, L3, t, f, sz))

print("famille   n   |flèche| moy   flèche signée moy ± err   (px)   en % de l'arête   équiv. +z (mm, si sensible)")
for k, v in fam.items():
    n = len(v)
    fs = [x[4] for x in v]
    # signe ramené au sens +z quand la sensibilité est suffisante
    sg = [(x[4] * (1 if x[5] > 0 else -1), x[4] / x[5]) for x in v if abs(x[5]) > 0.6]
    m_abs = sum(abs(f) for f in fs) / n
    if sg:
        m = sum(a for a, _ in sg) / len(sg)
        sd = math.sqrt(sum((a - m) ** 2 for a, _ in sg) / max(1, len(sg) - 1)) / math.sqrt(len(sg))
        mz = sum(z for _, z in sg) / len(sg)
        pc = sum(a / x[1] for (a, _), x in zip(sg, [x for x in v if abs(x[5]) > 0.6])) / len(sg) * 100
        print(f"{k:6s}  {n:3d}   {m_abs:5.1f}          {m:+5.1f} ± {sd:.1f} (n={len(sg)})            {pc:+5.1f} %            {mz:+5.1f} mm sur ~{sum(x[2] for x in v)/n:.0f} mm")
    else:
        print(f"{k:6s}  {n:3d}   {m_abs:5.1f}          (sens +z non déterminable sous cet angle)")
if "--detail" in sys.argv:
    for k, v in fam.items():
        for nom, L, L3, t, f, sz in v:
            print(f"  {nom:7s} L={L:5.0f}px t={t:.2f} flèche={f:+5.1f}px sens_z={sz:+.2f}px/mm")
