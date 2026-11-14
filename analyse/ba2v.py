#!/usr/bin/env python3
"""Ajustement de faisceaux sténopé multi-vues sur les pointés précis du musée.
Forme paramétrique commune (unités b = 1) + une caméra par vue (f, rotation, translation).
Point principal = centre de l'image. Python pur.

Usage : python3 analyse/ba2v.py [--arcs 0|1] [--fixe nom=val,...] [--vues A,B] [--fA px]
  --arcs 1 : pointes à arcs égaux sur le bord (défaut) ; 0 : cercle étiré.
"""
import json, math, os, sys

ICI = os.path.dirname(os.path.abspath(__file__))
VUES = {
    "A": dict(f="donnees/musee_a_precis.json", cle="museeA", w=600, h=900, f0=4000, wy=0.0),
    "B": dict(f="donnees/musee_b_precis.json", cle="museeB", w=1200, h=1600, f0=1300, wy=0.6),
}
FORME = ["ratio", "HC", "RR", "RV", "RM", "RP", "RQ", "ZV", "ZM", "ZP", "ZQ", "aD", "aI1", "aI2"]
S0 = dict(ratio=0.68, HC=0.35, RR=0.78, RV=0.58, RM=0.60, RP=0.30, RQ=0.30, ZV=0.53, ZM=0.38, ZP=0.81, ZQ=0.70,
          aD=40.0, aI1=19.5, aI2=63.5)   # angles paramétriques libres (--arcs 2), depuis l'horizontale
FAM = dict(T=(None, 0.0, None), R=("RR", 22.5, None), V=("RV", 22.5, "ZV"), M=("RM", 0.0, "ZM"),
           P=("RP", 0.0, "ZP"), Q=("RQ", 22.5, "ZQ"))

_cache = {}


def warp(deg, ratio, arcs):
    """Angle nominal (fraction du périmètre) -> angle paramétrique de l'ellipse."""
    if not arcs:
        return deg
    key = round(ratio, 6)
    if key not in _cache:
        N, cum = 360, [0.0]
        for i in range(N):
            tm = math.radians(90 + (i + 0.5) * 360 / N)
            cum.append(cum[-1] + math.hypot(ratio * math.sin(tm), math.cos(tm)))
        _cache.clear(); _cache[key] = cum
    cum = _cache[key]; N = len(cum) - 1
    s = ((deg - 90) / 360) % 1.0
    cible = s * cum[-1]
    lo, hi = 0, N
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if cum[mid] <= cible else (lo, mid)
    return 90 + (lo + (cible - cum[lo]) / (cum[hi] - cum[lo])) * 360 / N


def monde(nom, s, arcs):
    if nom == "C":
        return (0.0, 0.0, s["HC"])
    rk, off, zk = FAM[nom[0]]
    r = s[rk] if rk else 1.0
    z = s[zk] * s["HC"] if zk else 0.0
    nominal = 90 + 45 * int(nom[1:]) + off
    if arcs == 2:   # angles libres, symétrie des deux axes conservée
        n = nominal % 360; ph = n % 180; ph = 180 - ph if ph > 90 else ph
        a = {0.0: 0.0, 22.5: s["aI1"], 45.0: s["aD"], 67.5: s["aI2"], 90.0: 90.0}[round(ph, 1)]
        t = math.radians(a)
        sx = 1 if math.cos(math.radians(n)) > 1e-9 else -1
        sy = 1 if math.sin(math.radians(n)) > 1e-9 else -1
        return (sx * s["ratio"] * r * math.cos(t), sy * r * math.sin(t), z)
    t = math.radians(warp(nominal, s["ratio"], arcs))
    return (s["ratio"] * r * math.cos(t), r * math.sin(t), z)


def rodrigues(w):
    th = math.sqrt(sum(c * c for c in w))
    if th < 1e-12:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    k = [c / th for c in w]; c, s = math.cos(th), math.sin(th); v = 1 - c
    return [[c + k[0] * k[0] * v, k[0] * k[1] * v - k[2] * s, k[0] * k[2] * v + k[1] * s],
            [k[1] * k[0] * v + k[2] * s, c + k[1] * k[1] * v, k[1] * k[2] * v - k[0] * s],
            [k[2] * k[0] * v - k[1] * s, k[2] * k[1] * v + k[0] * s, c + k[2] * k[2] * v]]


def projette(cam, X, cx, cy):
    lf, wx, wy, wz, tx, ty, tz = cam
    R = rodrigues((wx, wy, wz))
    # R0 = diag(1,-1,-1) : caméra face au masque, y image vers le bas
    Xw = (X[0], -X[1], -X[2])
    xc = [R[i][0] * Xw[0] + R[i][1] * Xw[1] + R[i][2] * Xw[2] for i in range(3)]
    xc[0] += tx; xc[1] += ty; xc[2] += tz
    f = math.exp(lf)
    return (cx + f * xc[0] / xc[2], cy + f * xc[1] / xc[2])


def resoudre(A, y):
    n = len(A); M = [r[:] + [v] for r, v in zip(A, y)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        if abs(M[i][i]) < 1e-300:
            M[i][i] = 1e-300
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                if f:
                    M[r] = [a - f * b for a, b in zip(M[r], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)]


def lm(x, fun, libres, iters=150):
    r = fun(x); c = sum(v * v for v in r); lam = 1e-3
    for _ in range(iters):
        J = []
        for j in libres:
            h = 1e-6 * max(1.0, abs(x[j])); xp = x[:]; xp[j] += h; xm = x[:]; xm[j] -= h
            rp, rm = fun(xp), fun(xm)
            J.append([(a - b) / (2 * h) for a, b in zip(rp, rm)])
        n = len(libres)
        JTJ = [[sum(a * b for a, b in zip(J[i], J[k])) for k in range(n)] for i in range(n)]
        g = [sum(a * b for a, b in zip(J[i], r)) for i in range(n)]
        ok = False
        for _ in range(12):
            A = [row[:] for row in JTJ]
            for i in range(n):
                A[i][i] += lam * (JTJ[i][i] + 1e-12)
            d = resoudre(A, [-v for v in g])
            xn = x[:]
            for i, j in enumerate(libres):
                xn[j] += d[i]
            try:
                rn = fun(xn); cn = sum(v * v for v in rn)
            except (ValueError, ZeroDivisionError, OverflowError):
                cn = float("inf")
            if cn < c:
                gain = c - cn; x, r, c, lam, ok = xn, rn, cn, lam / 3, True
                break
            lam *= 4
        if not ok or gain < 1e-10 * c:
            break
    return x, r, c, JTJ


def main():
    args = dict(a.lstrip("-").split("=", 1) if "=" in a else (a.lstrip("-"), None) for a in [])
    av = sys.argv[1:]; opt = {}
    while av:
        k = av.pop(0).lstrip("-"); opt[k] = av.pop(0)
    arcs = int(opt.get("arcs", 1))
    noms_vues = opt.get("vues", "A,B").split(",")
    fixe = dict((kv.split("=")[0], float(kv.split("=")[1])) for kv in opt.get("fixe", "").split(",") if kv)
    fA = float(opt["fA"]) if "fA" in opt else None

    obs = []
    for v in noms_vues:
        d = VUES[v]; pts = json.load(open(os.path.join(ICI, d["f"])))[d["cle"]]
        obs.append((v, d, pts))
    s0 = dict(S0); s0.update(fixe)
    x = [s0[n] for n in FORME]
    libres = [i for i, n in enumerate(FORME) if n not in fixe and (arcs == 2 or not n.startswith("a"))]
    for v, d, pts in obs:
        base = len(x)
        f0 = fA if (v == "A" and fA) else d["f0"]
        haut = math.dist(pts["T0"], pts["T4"]) / 2
        cxm = sum(p[0] for p in pts.values()) / len(pts); cym = sum(p[1] for p in pts.values()) / len(pts)
        tz = f0 / haut
        x += [math.log(f0), 0.0, d["wy"], 0.0, (cxm - d["w"] / 2) / f0 * tz, (cym - d["h"] / 2) / f0 * tz, tz]
        libres += [base + i for i in range(7) if not (i == 0 and v == "A" and fA)]

    def fun(x):
        s = dict(zip(FORME, x)); r = []
        for i, (v, d, pts) in enumerate(obs):
            cam = x[len(FORME) + 7 * i: len(FORME) + 7 * i + 7]
            for n, p in pts.items():
                u = projette(cam, monde(n, s, arcs), d["w"] / 2, d["h"] / 2)
                r += [u[0] - p[0], u[1] - p[1]]
        return r

    x, r, c, JTJ = lm(x, fun, libres)
    m = len(r); dof = m - len(libres); sig2 = c / dof
    # covariance
    n = len(libres); sd = {}
    for i in range(n):
        e = [0.0] * n; e[i] = 1.0
        try:
            sd[libres[i]] = math.sqrt(abs(resoudre([row[:] for row in JTJ], e)[i]) * sig2)
        except Exception:
            sd[libres[i]] = float("nan")
    print(f"arcs={arcs} vues={','.join(noms_vues)} fixe={fixe or '-'} : rms {math.sqrt(c / (m / 2)):.2f} px/point, {m // 2} points, {len(libres)} paramètres")
    print("  " + "  ".join(f"{nm}={x[i]:.3f}" + (f"±{sd[i]:.3f}" if i in sd else "*") for i, nm in enumerate(FORME) if i in sd or nm in fixe))
    if arcs == 2:
        ra = x[0]; print("  prédiction arcs égaux pour ce ratio : aD=%.1f aI1=%.1f aI2=%.1f" % tuple(
            (lambda t: min(t % 180, 180 - t % 180))(warp(d, ra, 1)) for d in (135, 157.5, 112.5)))
    k = 0
    for i, (v, d, pts) in enumerate(obs):
        b = len(FORME) + 7 * i; cam = x[b:b + 7]
        rr = r[k:k + 2 * len(pts)]; k += 2 * len(pts)
        rms = math.sqrt(sum(a * a for a in rr) / len(pts))
        R = rodrigues(cam[1:4])
        # direction de visée dans le repère du masque (angle avec la normale)
        incl = math.degrees(math.acos(max(-1, min(1, R[2][2]))))
        par = {}
        for j, nm in enumerate(pts):
            par.setdefault(nm[0], []).append(math.hypot(rr[2 * j], rr[2 * j + 1]))
        print(f"  vue {v}: rms {rms:.2f} px  f={math.exp(cam[0]):.0f} px  distance={cam[6]:.2f}·b  inclinaison={incl:.1f}°  "
              + " ".join(f"{f}:{sum(l) / len(l):.1f}" for f, l in par.items()))
    if "sauve" in opt:
        json.dump(dict(arcs=arcs, forme=dict(zip(FORME, x)),
                       cams={v: x[len(FORME) + 7 * i: len(FORME) + 7 * i + 7] for i, (v, d, pts) in enumerate(obs)}),
                  open(opt["sauve"], "w"), indent=1)
    if "detail" in opt:
        k = 0
        for v, d, pts in obs:
            for nm in pts:
                print(f"    {v} {nm}: {r[k]:+.1f} {r[k + 1]:+.1f}"); k += 2


if __name__ == "__main__":
    main()
