#!/usr/bin/env python3
"""Contrôle d'un pointé quasi frontal : homographie des 8 pointes T -> cercle unité,
puis rayon/angle de chaque famille de points, alignements T-M-P-C.
Usage : python3 analyse/verif_pointage.py analyse/donnees/musee_a_precis.json"""
import json, math, sys

d = json.load(open(sys.argv[1])); obs = next(iter(d.values()))
phi = lambda k, off=0.0: math.radians(90 + 45 * k + off)

def solve(A, b):
    n = len(A); M = [r[:] + [v] for r, v in zip(A, b)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]; M[r] = [x - f * y for x, y in zip(M[r], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)]

def homog(src, dst):  # moindres carrés DLT (h33 = 1)
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    At = list(zip(*A))
    N = [[sum(a * c for a, c in zip(r, col)) for col in At] for r in At]
    return solve(N, [sum(a * c for a, c in zip(r, b)) for r in At])

def ap(h, p):
    w = h[6] * p[0] + h[7] * p[1] + 1
    return ((h[0] * p[0] + h[1] * p[1] + h[2]) / w, (h[3] * p[0] + h[4] * p[1] + h[5]) / w)

# image y vers le bas -> on retourne y
img = {n: (p[0], -p[1]) for n, p in obs.items()}
T = [img[f"T{k}"] for k in range(8)]
H = homog(T, [(math.cos(phi(k)), math.sin(phi(k))) for k in range(8)])
Hi = homog([(math.cos(phi(k)), math.sin(phi(k))) for k in range(8)], T)
res = [math.dist(ap(Hi, (math.cos(phi(k)), math.sin(phi(k)))), T[k]) for k in range(8)]
print("résidus T (px) :", " ".join(f"{r:.1f}" for r in res), f"| rms {math.sqrt(sum(r*r for r in res)/8):.2f}")
hh = math.dist(T[0], T[4]); ww = math.dist(T[2], T[6])
print(f"rapport apparent T2T6/T0T4 = {ww/hh:.3f} ; hauteur {hh:.1f} px")
c = ap(H, img["C"]); print(f"C normalisé : ({c[0]:+.3f}, {c[1]:+.3f})")
modele = dict(M=(0.60, 0), P=(0.29, 0), V=(0.57, 22.5), R=(0.76, 22.5), Q=(0.32, 22.5))
for f, (rm, off) in modele.items():
    rs, das = [], []
    for k in range(8):
        if f"{f}{k}" not in img: continue
        u, v = ap(H, img[f"{f}{k}"]); u -= c[0]; v -= c[1]
        r = math.hypot(u, v); da = (math.degrees(math.atan2(v, u)) - (90 + 45 * k + off) + 180) % 360 - 180
        rs.append(r); das.append(da)
    m = sum(rs) / len(rs); sd = math.sqrt(sum((r - m) ** 2 for r in rs) / len(rs))
    print(f"{f}: r moy {m:.3f} ± {sd:.3f} (modèle {rm})  r_k = " + " ".join(f"{r:.2f}" for r in rs))
    print(f"   écart angulaire ° : " + " ".join(f"{a:+.1f}" for a in das))
print("alignement : écart (px) de M_k et P_k à la droite T_k–C")
for k in range(8):
    a, b = img[f"T{k}"], img["C"]; L = math.dist(a, b)
    e = lambda p: ((b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])) / L
    print(f"  k={k}: M {e(img[f'M{k}']):+.1f}  P {e(img[f'P{k}']):+.1f}")
