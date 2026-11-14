"""BA with shared focal; input obs json; output shape + predicted coords of all vertices per frame."""
import math, json, sys
import ba
from ba import *
NAMES = ["C"] + [f"{k}{i}" for k in "TVMPQR" for i in range(8)]

def run(obs, fixf=None, fix_shape=(), huber=6.0):
    ba.OBS = obs
    frames = list(obs)
    nshape = len(SHAPE_NAMES)
    x = [S0[k] for k in SHAPE_NAMES]
    for fr in frames:
        cam, _ = affine_init(obs[fr], S0); x += cam
    x.append(math.log(fixf or 1500.0))
    def fun(xx):
        y = xx[:-1]
        for fi in range(len(frames)): y[nshape+7*fi+6] = xx[-1]
        return residuals(y, frames, huber=huber)
    cams = [i for i in range(nshape, len(x)-1) if (i-nshape) % 7 != 6]
    fidx = [] if fixf else [len(x)-1]
    observed = {n[0] for d in obs.values() for n in d}
    used = {"ratio","Zc"} | ({"RV","ZV"} if "V" in observed else set()) | ({"RM","ZM"} if "M" in observed else set()) \
         | ({"RP","ZP"} if "P" in observed else set()) | ({"RR"} if "R" in observed else set()) | ({"RQ","ZQ"} if "Q" in observed else set())
    sh = [i for i,k in enumerate(SHAPE_NAMES) if k in used and k not in fix_shape]
    x, c, _ = lm(x, fun, 150, cams + fidx)
    x, c, JtJ = lm(x, fun, 400, sh + cams + fidx)
    r = fun(x); n = len(r); rms = math.sqrt(sum(e*e for e in r)/n)
    # std
    free = sh + cams + fidx; dof = max(1, n - len(free)); s2 = sum(e*e for e in r)/dof
    std = {}
    for k_i, i in enumerate(sh):
        e = [1.0 if q == k_i else 0.0 for q in range(len(free))]
        std[SHAPE_NAMES[i]] = math.sqrt(abs(solve([row[:] for row in JtJ], e)[k_i]) * s2)
    shp = dict(zip(SHAPE_NAMES, x[:nshape]))
    pred, res = {}, []
    for fi, fr in enumerate(frames):
        cam = x[nshape+7*fi: nshape+7*fi+7]; cam[6] = x[-1]
        pred[fr] = {nm: [round(v, 1) for v in project(cam, world(nm, shp))] for nm in NAMES}
        for nm, uv in obs[fr].items():
            res.append((round(math.hypot(pred[fr][nm][0]-uv[0], pred[fr][nm][1]-uv[1]), 1), fr, nm))
    res.sort(reverse=True)
    return dict(shape=shp, std=std, rms=rms, f=math.exp(x[-1]), pred=pred, worst=res[:6])

if __name__ == "__main__":
    obs = json.load(open(sys.argv[1]))
    fixf = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    out = run(obs, fixf)
    print(f"rms {out['rms']:.2f}px  f={out['f']:.0f}  n={sum(len(d) for d in obs.values())}")
    for k, v in out["shape"].items():
        sd = out["std"].get(k)
        print(f"  {k:6s} {v:.3f}" + (f" ± {sd:.3f}" if sd is not None else "  (non observé)") + f"   modèle {S0[k]}")
    print("pires:", out["worst"])
    json.dump(out["pred"], open("pred.json", "w"))
