import math, json, sys
import ba
from ba import *

def run(obs, fshared=None, fixf=None, verbose=True, drop=()):
    ba.OBS = {fr: {n: uv for n, uv in d.items() if (fr, n) not in drop} for fr, d in obs.items()}
    frames = list(ba.OBS)
    s = dict(S0); nshape = len(SHAPE_NAMES)
    x = [s[k] for k in SHAPE_NAMES]
    for fr in frames:
        cam, _ = affine_init(ba.OBS[fr], s); x += cam
    x.append(math.log(fixf or 1500.0))
    def fun(xx):
        y = xx[:-1]
        for fi in range(len(frames)):
            y[nshape + 7*fi + 6] = xx[-1]
        return residuals(y, frames, huber=8.0)
    # f: each cam's logf slot ignored (overridden); keep them out of free set
    free_cams = [i for i in range(nshape, len(x)-1) if (i - nshape) % 7 != 6]
    x, c, _ = lm(x, fun, 150, free_cams + ([] if fixf else [len(x)-1]))
    x, c, JtJ = lm(x, fun, 400, list(range(nshape)) + free_cams + ([] if fixf else [len(x)-1]))
    r = fun(x); n = len(r); rms = math.sqrt(sum(e*e for e in r)/n)
    shp = dict(zip(SHAPE_NAMES, x[:nshape]))
    per = []
    for fi, fr in enumerate(frames):
        cam = x[nshape+7*fi: nshape+7*fi+7]; cam[6] = x[-1]
        for nm, uv in ba.OBS[fr].items():
            e = math.hypot(*(a-b for a, b in zip(project(cam, world(nm, shp)), uv)))
            per.append((e, fr, nm))
    per.sort(reverse=True)
    return shp, rms, math.exp(x[-1]), per, x, frames

obs = ba.OBS
drop = set()
for rnd in range(6):
    shp, rms, f, per, x, frames = run(obs, drop=drop)
    print(f"round {rnd}: rms {rms:.1f}px f={f:.0f}  worst {[(fr,n,round(e)) for e,fr,n in per[:3]]}")
    if per[0][0] < 3*rms or per[0][0] < 12: break
    drop.add((per[0][1], per[0][2]))
print("dropped:", sorted(drop))
for k in SHAPE_NAMES: print(f"  {k:6s} {shp[k]:.3f}  (modèle {S0[k]})")
# sensitivity: fixed focal
for ff in (1000, 1500, 2500, 5000):
    s2, r2, _, _, _, _ = run(obs, fixf=ff, drop=drop)
    print(f"f fixe {ff}: rms {r2:.1f} ", " ".join(f"{k}={s2[k]:.3f}" for k in SHAPE_NAMES))
