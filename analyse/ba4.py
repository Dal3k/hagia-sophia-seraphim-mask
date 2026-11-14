import math, json, itertools
import ba
from ba import *
OBS_ALL = dict(ba.OBS)  # original manual annotations (3 frames)

def fit(obs, free_shape, fixf=None, huber=8.0, init=None):
    ba.OBS = obs; frames = list(obs); nshape = len(SHAPE_NAMES)
    S = dict(S0); S.update(init or {})
    x = [S[k] for k in SHAPE_NAMES]
    for fr in frames:
        cam, _ = affine_init(obs[fr], S); x += cam
    x.append(math.log(fixf or 1500.0))
    def fun(xx):
        y = xx[:-1]
        for fi in range(len(frames)): y[nshape+7*fi+6] = xx[-1]
        return residuals(y, frames, huber=huber)
    cams = [i for i in range(nshape, len(x)-1) if (i-nshape) % 7 != 6]
    fidx = [] if fixf else [len(x)-1]
    sh = [SHAPE_NAMES.index(k) for k in free_shape]
    x, c, _ = lm(x, fun, 150, cams + fidx)
    x, c, J = lm(x, fun, 400, sh + cams + fidx)
    r = fun(x); rms = math.sqrt(sum(e*e for e in r)/len(r))
    shp = dict(zip(SHAPE_NAMES, x[:nshape]))
    per = []
    for fi, fr in enumerate(frames):
        cam = x[nshape+7*fi: nshape+7*fi+7]; cam[6] = x[-1]
        for nm, uv in obs[fr].items():
            p = project(cam, world(nm, shp)); per.append((round(math.hypot(p[0]-uv[0], p[1]-uv[1]),1), fr, nm, round(p[0]-uv[0]), round(p[1]-uv[1])))
    per.sort(reverse=True)
    return shp, rms, math.exp(x[-1]), per

H = ["Zc", "ZV", "ZM", "ZP"]
print("== contour fixé (ratio .65, rayons du modèle), hauteurs libres ==")
for ff in (None, 1200, 1800, 3000):
    shp, rms, f, per = fit(OBS_ALL, H, fixf=ff)
    print(f"f={'libre' if ff is None else ff} -> f={f:.0f} rms {rms:.1f}px  " + " ".join(f"{k}={shp[k]:.3f}" for k in H) + f"  hc/b={shp['Zc']:.3f}")
shp, rms, f, per = fit(OBS_ALL, H)
print("pires résidus (px, dx, dy):", per[:8])
# leave-one-frame-out
print("== en retirant une vue ==")
for fr in OBS_ALL:
    o = {k: v for k, v in OBS_ALL.items() if k != fr}
    shp, rms, f, per = fit(o, H, fixf=1800)
    print(f"sans {fr}: rms {rms:.1f} " + " ".join(f"{k}={shp[k]:.3f}" for k in H))
# robust: drop worst 4 points
o = {fr: dict(d) for fr, d in OBS_ALL.items()}
for e, fr, nm, *_ in per[:4]: o[fr].pop(nm, None)
shp, rms, f, per2 = fit(o, H)
print(f"sans les 4 pires: f={f:.0f} rms {rms:.1f} " + " ".join(f"{k}={shp[k]:.3f}" for k in H))
