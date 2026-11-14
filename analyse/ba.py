#!/usr/bin/env python3
"""Bundle adjustment: shared parametric mask shape + per-frame pinhole camera.
World units: b = 1 (half height). X = ratio*r*cos, Y = r*sin, Z = Zc*z."""
import math, sys, json, random

OBS = {
 "30.5": {"C": (945, 426), "T2": (693, 426), "T1": (753, 219), "T7": (1044, 263), "T6": (1077, 442),
          "V1": (812, 362), "V0": (858, 303), "V7": (991, 316), "V6": (1037, 382), "V2": (825, 484),
          "T3": (792, 627), "V5": (1024, 488), "T4": (925, 739)},
 "14.0": {"T0": (1052, 106), "T1": (743, 199), "T2": (597, 610), "T7": (1258, 354), "V0": (1019, 296),
          "V1": (888, 475), "V7": (1213, 349), "M1": (944, 374), "P0": (1143, 457), "P1": (1056, 480),
          "P7": (1218, 537), "C": (1150, 632), "V2": (862, 749), "P2": (1004, 606), "P3": (1037, 749)},
 "12.8": {"T1": (756, 77), "T2": (619, 494), "V1": (901, 367), "C": (1165, 520), "V0": (1030, 176),
          "T7": (1232, 236), "P0": (1158, 338), "T6": (1325, 450), "V2": (904, 643)},
}
if len(sys.argv) > 1:
    OBS = json.load(open(sys.argv[1]))

SHAPE_NAMES = ["ratio", "Zc", "RV", "RM", "RP", "ZV", "ZM", "ZP", "RR", "RQ", "ZQ"]
S0 = dict(ratio=0.65, Zc=0.35, RV=0.57, RM=0.60, RP=0.29, ZV=0.53, ZM=0.38, ZP=0.81, RR=0.76, RQ=0.32, ZQ=0.70)
CX, CY = 960.0, 540.0


def world(name, s):
    k = int(name[1:]) if len(name) > 1 else 0
    f = 90 + 45 * k
    kind = name[0]
    if kind == "C":
        r, a, z = 0, 0, 1.0
    elif kind == "T":
        r, a, z = 1, f, 0
    elif kind == "V":
        r, a, z = s["RV"], f + 22.5, s["ZV"]
    elif kind == "M":
        r, a, z = s["RM"], f, s["ZM"]
    elif kind == "P":
        r, a, z = s["RP"], f, s["ZP"]
    elif kind == "R":
        r, a, z = s["RR"], f + 22.5, 0
    elif kind == "Q":
        r, a, z = s["RQ"], f + 22.5, s["ZQ"]
    a = math.radians(a)
    return (s["ratio"] * r * math.cos(a), r * math.sin(a), s["Zc"] * z)


def rodrigues(w):
    th = math.sqrt(sum(c * c for c in w))
    if th < 1e-12:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    k = [c / th for c in w]
    K = [[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]
    c, s_ = math.cos(th), math.sin(th)
    R = [[(1 if i == j else 0) + s_ * K[i][j] + (1 - c) * sum(K[i][m] * K[m][j] for m in range(3))
          for j in range(3)] for i in range(3)]
    return R


def rot2rod(R):
    tr = R[0][0] + R[1][1] + R[2][2]
    th = math.acos(max(-1, min(1, (tr - 1) / 2)))
    if th < 1e-9:
        return [0, 0, 0]
    d = 2 * math.sin(th)
    return [th * (R[2][1] - R[1][2]) / d, th * (R[0][2] - R[2][0]) / d, th * (R[1][0] - R[0][1]) / d]


def project(cam, X):
    # cam: [w0,w1,w2,tx,ty,tz,logf]
    R = rodrigues(cam[:3])
    x = [sum(R[i][j] * X[j] for j in range(3)) + cam[3 + i] for i in range(3)]
    f = math.exp(cam[6])
    return (CX + f * x[0] / x[2], CY + f * x[1] / x[2])


def affine_init(obs, s):
    names = list(obs)
    rows = [list(world(n, s)) + [1] for n in names]
    sol = []
    for idx in range(2):
        b = [obs[n][idx] for n in names]
        A = [[sum(r[i] * r[j] for r in rows) for j in range(4)] for i in range(4)]
        y = [sum(r[i] * bb for r, bb in zip(rows, b)) for i in range(4)]
        sol.append(solve(A, y))
    a1, a2 = sol[0][:3], sol[1][:3]
    s1, s2 = math.sqrt(sum(c * c for c in a1)), math.sqrt(sum(c * c for c in a2))
    sc = (s1 + s2) / 2
    r1 = [c / s1 for c in a1]
    r2 = [c / s2 for c in a2]
    # orthogonalize
    d = sum(p * q for p, q in zip(r1, r2))
    r1 = [p - d / 2 * q for p, q in zip(r1, r2)]
    r2 = [q - d / 2 * p for p, q in zip(r1, r2)]
    n1 = math.sqrt(sum(c * c for c in r1)); n2 = math.sqrt(sum(c * c for c in r2))
    r1 = [c / n1 for c in r1]; r2 = [c / n2 for c in r2]
    r3 = [r1[1] * r2[2] - r1[2] * r2[1], r1[2] * r2[0] - r1[0] * r2[2], r1[0] * r2[1] - r1[1] * r2[0]]
    R = [r1, r2, r3]
    f = 2500.0
    tz = f / sc
    tx = (sol[0][3] - CX) / sc
    ty = (sol[1][3] - CY) / sc
    return rot2rod(R) + [tx, ty, tz, math.log(f)], r3


def solve(A, y):
    n = len(y)
    A = [row[:] + [y[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p] = A[p], A[i]
        if abs(A[i][i]) < 1e-15:
            A[i][i] = 1e-15
        for r in range(n):
            if r != i:
                f = A[r][i] / A[i][i]
                if f:
                    for c in range(i, n + 1):
                        A[r][c] -= f * A[i][c]
    return [A[i][n] / A[i][i] for i in range(n)]


def residuals(x, frames, fix_f=None, huber=6.0):
    s = dict(zip(SHAPE_NAMES, x[:len(SHAPE_NAMES)]))
    res = []
    o = len(SHAPE_NAMES)
    for fi, fr in enumerate(frames):
        cam = x[o + 7 * fi: o + 7 * fi + 7]
        for n, (u, v) in OBS[fr].items():
            pu, pv = project(cam, world(n, s))
            for e in (pu - u, pv - v):
                a = abs(e)
                res.append(e if a <= huber else math.copysign(math.sqrt(2 * huber * a - huber * huber), e))
    return res


def lm(x, fun, iters=200, free=None):
    free = free if free is not None else list(range(len(x)))
    lam = 1e-2
    r = fun(x); cost = sum(e * e for e in r)
    for it in range(iters):
        J = []
        for j in free:
            h = 1e-6 * max(1.0, abs(x[j]))
            xp = x[:]; xp[j] += h
            rp = fun(xp)
            J.append([(a - b) / h for a, b in zip(rp, r)])
        n = len(free)
        JtJ = [[sum(J[i][k] * J[j][k] for k in range(len(r))) for j in range(n)] for i in range(n)]
        Jtr = [sum(J[i][k] * r[k] for k in range(len(r))) for i in range(n)]
        while True:
            A = [[JtJ[i][j] + (lam * JtJ[i][i] if i == j else 0) for j in range(n)] for i in range(n)]
            d = solve(A, [-g for g in Jtr])
            xn = x[:]
            for k, j in enumerate(free):
                xn[j] += d[k]
            rn = fun(xn); cn = sum(e * e for e in rn)
            if cn < cost:
                x, r, cost = xn, rn, cn; lam = max(lam / 3, 1e-9); break
            lam *= 4
            if lam > 1e9:
                return x, cost, JtJ
        if max(abs(v) for v in d) < 1e-9:
            break
    return x, cost, JtJ


def main():
    frames = list(OBS)
    s = dict(S0)
    x = [s[k] for k in SHAPE_NAMES]
    for fr in frames:
        cam, r3 = affine_init(OBS[fr], s)
        x += cam
    nshape = len(SHAPE_NAMES)
    fun = lambda xx: residuals(xx, frames)
    # 1) cameras only
    cam_idx = list(range(nshape, len(x)))
    x, c, _ = lm(x, fun, 100, cam_idx)
    print("cams only: rms px", round(math.sqrt(c / len(fun(x))), 2))
    # 2) everything
    x, c, JtJ = lm(x, fun, 300)
    n_obs = len(fun(x))
    rms = math.sqrt(c / n_obs)
    print("joint: rms px", round(rms, 2), "obs", n_obs, "params", len(x))
    # covariance -> std of shape params
    dof = max(1, n_obs - len(x))
    sigma2 = c / dof
    try:
        n = len(x)
        inv = []
        for i in range(nshape):
            e = [1.0 if k == i else 0.0 for k in range(n)]
            inv.append(solve([row[:] for row in JtJ], e)[i])
        std = [math.sqrt(abs(v) * sigma2) for v in inv]
    except Exception:
        std = [float("nan")] * nshape
    out = {}
    for k, v, sd in zip(SHAPE_NAMES, x[:nshape], std):
        out[k] = (round(v, 3), round(sd, 3))
        print(f"  {k:6s} {v:7.3f} ± {sd:.3f}   (modèle {S0[k]})")
    for fi, fr in enumerate(frames):
        cam = x[nshape + 7 * fi: nshape + 7 * fi + 7]
        R = rodrigues(cam[:3])
        ang = math.degrees(math.acos(max(-1, min(1, -R[2][2]))))
        print(f"  frame {fr}: f={math.exp(cam[6]):.0f}px dist={cam[5]:.2f}b inclinaison={ang:.1f}°")
        s_ = dict(zip(SHAPE_NAMES, x[:nshape]))
        worst = sorted(((math.hypot(*(a - b for a, b in zip(project(cam, world(nm, s_)), uv))), nm)
                        for nm, uv in OBS[fr].items()), reverse=True)[:3]
        print("     pires résidus:", [(n, round(e, 1)) for e, n in worst])
    json.dump(out, open("ba_out.json", "w"))


if __name__ == "__main__":
    main()
