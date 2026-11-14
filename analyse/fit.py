import math
# frame coords measured on museum frontal frame (t=30.5s)
tips = {90:(914,144), 135:(750,219), 180:(694,424), 45:(1044,265)}
# affine fit p = c + A (u,v)
import itertools
rows=[];rhs=[]
for ang,(x,y) in tips.items():
    u,v=math.cos(math.radians(ang)),math.sin(math.radians(ang))
    rows.append([1,0,u,v,0,0]); rhs.append(x)
    rows.append([0,1,0,0,u,v]); rhs.append(y)
# least squares via normal equations
n=6
AtA=[[sum(r[i]*r[j] for r in rows) for j in range(n)] for i in range(n)]
Atb=[sum(r[i]*b for r,b in zip(rows,rhs)) for i in range(n)]
def solve(M,b):
    M=[row[:]+[bb] for row,bb in zip(M,b)]; N=len(M)
    for i in range(N):
        p=max(range(i,N),key=lambda r:abs(M[r][i])); M[i],M[p]=M[p],M[i]
        for r in range(N):
            if r!=i:
                f=M[r][i]/M[i][i]; M[r]=[a-f*bq for a,bq in zip(M[r],M[i])]
    return [M[i][N]/M[i][i] for i in range(N)]
cx,cy,a11,a12,a21,a22=solve(AtA,Atb)
print("affine c=(%.1f,%.1f) A=[[%.1f,%.1f],[%.1f,%.1f]]"%(cx,cy,a11,a12,a21,a22))
for ang,(x,y) in tips.items():
    u,v=math.cos(math.radians(ang)),math.sin(math.radians(ang))
    print(" tip",ang,"resid",round(cx+a11*u+a12*v-x,1),round(cy+a21*u+a22*v-y,1))
C=(939,430); kx,ky=C[0]-cx,C[1]-cy
print("parallax k per unit z (zC=1):",round(kx,1),round(ky,1))
det=a11*a22-a12*a21
def uv(x,y,z):
    X,Y=x-cx-kx*z, y-cy-ky*z
    return ((a22*X-a12*Y)/det, (-a21*X+a11*Y)/det)
pts={'P_N':((941,340),90),'I=F_N':((917,262),90),'P_NW':((892,365),135),'F_NW':((833,303),135),
     'X=F_W':((867,425),180),'A=V':((882,263),112.5),'B=V':((816,362),157.5),'R':((753,346),157.5)}
for name,((x,y),ang) in pts.items():
    best=None
    for zi in range(-30,131):
        z=zi/100; u,v=uv(x,y,z); d=abs(math.degrees(math.atan2(v,u))-ang)
        d=min(d,360-d)
        if best is None or d<best[0]: best=(d,z,u,v)
    d,z,u,v=best
    print(f"{name:6s} z={z:+.2f} r={math.hypot(u,v):.3f} angErr={d:.1f}")
