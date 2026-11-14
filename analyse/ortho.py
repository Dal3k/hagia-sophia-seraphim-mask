"""Scaled-orthographic multi-image fit of the star shape.
camera per image: [w0,w1,w2 (rotation), log s, tx, ty]; image = s * (R X)[:2] + t
shape shared: ratio, Zc (=hc/b), RV, RM, RP, RQ, ZV, ZM, ZP, ZQ (ZC=1)."""
import math, json, sys
from ba import rodrigues, solve, lm

SN = ["ratio", "Zc", "RV", "RM", "RP", "RQ", "ZV", "ZM", "ZP", "ZQ"]
S0 = dict(ratio=0.65, Zc=0.35, RV=0.57, RM=0.60, RP=0.29, RQ=0.32, ZV=0.53, ZM=0.38, ZP=0.81, ZQ=0.70)

def world(n, s):
    if n == "C": return (0.0, 0.0, s["Zc"])
    k = int(n[1:]); f = 90 + 45 * k; t = n[0]
    r, a, z = {"T": (1, f, 0), "V": (s["RV"], f + 22.5, s["ZV"]), "M": (s["RM"], f, s["ZM"]),
               "P": (s["RP"], f, s["ZP"]), "Q": (s["RQ"], f + 22.5, s["ZQ"]), "R": (0.76, f + 22.5, 0)}[t]
    a = math.radians(a)
    return (s["ratio"] * r * math.cos(a), r * math.sin(a), s["Zc"] * z)

def proj(cam, X):
    R = rodrigues(cam[:3]); s = math.exp(cam[3])
    return (s * sum(R[0][j] * X[j] for j in range(3)) + cam[4], s * sum(R[1][j] * X[j] for j in range(3)) + cam[5])

def init_cam(obs, s):
    # affine LSQ then orthonormalise (choose sign so that +Z faces camera: R[2][2] < 0 means z toward viewer? keep both, pick best)
    names = list(obs); rows = [list(world(n, s)) + [1] for n in names]
    sol = []
    for idx in range(2):
        b = [obs[n][idx] for n in names]
        A = [[sum(r[i] * r[j] for r in rows) for j in range(4)] for i in range(4)]
        y = [sum(r[i] * bb for r, bb in zip(rows, b)) for i in range(4)]
        sol.append(solve(A, y))
    a1, a2 = sol[0][:3], sol[1][:3]
    sc = (math.sqrt(sum(c*c for c in a1)) + math.sqrt(sum(c*c for c in a2))) / 2
    r1 = [c / sc for c in a1]; r2 = [c / sc for c in a2]
    # Gram-Schmidt
    n1 = math.sqrt(sum(c*c for c in r1)); r1 = [c / n1 for c in r1]
    d = sum(p*q for p, q in zip(r1, r2)); r2 = [q - d*p for p, q in zip(r1, r2)]
    n2 = math.sqrt(sum(c*c for c in r2)); r2 = [c / n2 for c in r2]
    r3 = [r1[1]*r2[2]-r1[2]*r2[1], r1[2]*r2[0]-r1[0]*r2[2], r1[0]*r2[1]-r1[1]*r2[0]]
    R = [r1, r2, r3]
    tr = R[0][0] + R[1][1] + R[2][2]
    th = math.acos(max(-1, min(1, (tr - 1) / 2)))
    if abs(math.sin(th)) < 1e-6:
        w = [0, 0, 0] if th < 1 else [math.pi, 0, 0]
    else:
        w = [th*(R[2][1]-R[1][2])/(2*math.sin(th)), th*(R[0][2]-R[2][0])/(2*math.sin(th)), th*(R[1][0]-R[0][1])/(2*math.sin(th))]
    return w + [math.log(sc), sol[0][3], sol[1][3]]

def fit(OBS, free, fixed=None, huber=4.0, starts=None):
    imgs = list(OBS); S = dict(S0); S.update(fixed or {})
    best = None
    for st in (starts or [{}]):
        S1 = dict(S); S1.update(st)
        x = [S1[k] for k in SN]
        for im in imgs: x += init_cam(OBS[im], S1)
        def fun(xx):
            s = dict(zip(SN, xx[:len(SN)])); r = []
            for i, im in enumerate(imgs):
                cam = xx[len(SN)+6*i: len(SN)+6*i+6]
                for n, uv in OBS[im].items():
                    p = proj(cam, world(n, s))
                    for e in (p[0]-uv[0], p[1]-uv[1]):
                        a = abs(e); r.append(e if a <= huber else math.copysign(math.sqrt(2*huber*a-huber*huber), e))
            return r
        idx = [SN.index(k) for k in free] + list(range(len(SN), len(x)))
        x, c, JtJ = lm(x, fun, 300, idx)
        if best is None or c < best[1]: best = (x, c, JtJ, fun, idx)
    x, c, JtJ, fun, idx = best
    r = fun(x); n = len(r); dof = max(1, n - len(idx)); s2 = c / dof
    std = {}
    for kk, k in enumerate(free):
        e = [1.0 if q == kk else 0.0 for q in range(len(idx))]
        std[k] = math.sqrt(abs(solve([row[:] for row in JtJ], e)[kk]) * s2)
    shp = dict(zip(SN, x[:len(SN)]))
    cams = {}
    worst = []
    for i, im in enumerate(imgs):
        cam = x[len(SN)+6*i: len(SN)+6*i+6]
        R = rodrigues(cam[:3]); tilt = math.degrees(math.acos(min(1, abs(R[2][2]))))
        cams[im] = dict(scale_px_per_b=math.exp(cam[3]), tilt=tilt)
        for nm, uv in OBS[im].items():
            p = proj(cam, world(nm, shp)); worst.append((round(math.hypot(p[0]-uv[0], p[1]-uv[1]), 1), im, nm))
    worst.sort(reverse=True)
    return dict(shape=shp, std=std, rms=math.sqrt(sum(e*e for e in r)/n), cams=cams, worst=worst[:6], n=n//2)

def report(res, free):
    print(f"  rms {res['rms']:.2f}px  n={res['n']}  " + "  ".join(f"{im}: {c['scale_px_per_b']:.0f}px/b tilt {c['tilt']:.1f}°" for im, c in res['cams'].items()))
    print("  " + "  ".join(f"{k}={res['shape'][k]:.3f}±{res['std'][k]:.3f}" for k in free))
    print("  pires:", res["worst"][:5])

if __name__ == "__main__":
    OBS = json.load(open(sys.argv[1]))
    free = sys.argv[2].split(",")
    fixed = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    starts = [{"Zc": z} for z in (0.2, 0.35, 0.6)]
    report(fit(OBS, free, fixed, starts=starts), free)
