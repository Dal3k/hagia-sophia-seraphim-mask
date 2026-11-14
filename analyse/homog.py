import json, math, sys
from ba import solve
def H_fit(src, dst):
    # DLT with h33=1, least squares (16 eq, 8 unk)
    rows=[];b=[]
    for (x,y),(u,v) in zip(src,dst):
        rows.append([x,y,1,0,0,0,-u*x,-u*y]); b.append(u)
        rows.append([0,0,0,x,y,1,-v*x,-v*y]); b.append(v)
    A=[[sum(r[i]*r[j] for r in rows) for j in range(8)] for i in range(8)]
    y=[sum(r[i]*bb for r,bb in zip(rows,b)) for i in range(8)]
    h=solve(A,y)+[1]
    return [h[0:3],h[3:6],h[6:9]]
def ap(H,x,y):
    w=H[2][0]*x+H[2][1]*y+H[2][2]
    return ((H[0][0]*x+H[0][1]*y+H[0][2])/w,(H[1][0]*x+H[1][1]*y+H[1][2])/w)
for name in sys.argv[1:]:
    d=json.load(open(name)); key=list(d)[0]; obs=d[key]
    src=[];dst=[]
    for k in range(8):
        a=math.radians(90+45*k); src.append((math.cos(a),math.sin(a))); dst.append(obs["T%d"%k])
    H=H_fit(src,dst)
    res=[tuple(round(p-q,1) for p,q in zip(ap(H,*s),t)) for s,t in zip(src,dst)]
    rms=math.sqrt(sum(a*a+b*b for a,b in res)/8)
    c0=ap(H,0,0); C=obs["C"]
    # local scale: image px per unit b along vertical axis around centre
    up=ap(H,0,0.05); sv=math.hypot(up[0]-c0[0],up[1]-c0[1])/0.05
    print(key,"rms",round(rms,2),"resid",res)
    print("   centre projete",[round(c,1) for c in c0],"C",C,"parallaxe px",(round(C[0]-c0[0],1),round(C[1]-c0[1],1)),"=",round(math.hypot(C[0]-c0[0],C[1]-c0[1])/sv,3),"b ; px/b vert",round(sv))
    json.dump(H,open(key+"_H.json","w"))
