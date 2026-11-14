import math
def solve(M,b):
    M=[row[:]+[bb] for row,bb in zip(M,b)]; N=len(M)
    for i in range(N):
        p=max(range(i,N),key=lambda r:abs(M[r][i])); M[i],M[p]=M[p],M[i]
        for r in range(N):
            if r!=i:
                f=M[r][i]/M[i][i]; M[r]=[a-f*bq for a,bq in zip(M[r],M[i])]
    return [M[i][N]/M[i][i] for i in range(N)]
def analyse(name,tips,C,inner):
    rows=[];rhs=[]
    for ang,(x,y) in tips.items():
        u,v=math.cos(math.radians(ang)),math.sin(math.radians(ang))
        rows.append([1,0,u,v,0,0]); rhs.append(x); rows.append([0,1,0,0,u,v]); rhs.append(y)
    n=6; AtA=[[sum(r[i]*r[j] for r in rows) for j in range(n)] for i in range(n)]
    Atb=[sum(r[i]*b for r,b in zip(rows,rhs)) for i in range(n)]
    cx,cy,a11,a12,a21,a22=solve(AtA,Atb)
    kx,ky=C[0]-cx,C[1]-cy
    m1=(a11,a21); m2=(a12,a22); m3=(kx,ky)
    A,B,G=solve([[m1[0]**2,m2[0]**2,m3[0]**2],[m1[1]**2,m2[1]**2,m3[1]**2],[m1[0]*m1[1],m2[0]*m2[1],m3[0]*m3[1]]],[1,1,0])
    print(f"== {name}: c=({cx:.0f},{cy:.0f}) cols u=({a11:.0f},{a21:.0f}) v=({a12:.0f},{a22:.0f}) z=({kx:.0f},{ky:.0f})")
    print(f"   alpha^2={A:.3e} beta^2={B:.3e} gamma^2={G:.3e}")
    if A>0 and B>0 and G>0:
        al,be,ga=map(math.sqrt,(A,B,G))
        print(f"   true a/b = {be/al:.3f}   Zc/b = {be/ga:.3f}")
        # view direction = r1 x r2
        r1=(m1[0]*al,m2[0]*be,m3[0]*ga); r2=(m1[1]*al,m2[1]*be,m3[1]*ga)
        d=(r1[1]*r2[2]-r1[2]*r2[1], r1[2]*r2[0]-r1[0]*r2[2], r1[0]*r2[1]-r1[1]*r2[0])
        print(f"   view tilt from normal = {math.degrees(math.acos(abs(d[2])/math.sqrt(sum(t*t for t in d)))):.1f} deg")
    det=a11*a22-a12*a21
    for nm,((x,y),ang) in inner.items():
        best=None
        for zi in range(-30,131):
            z=zi/100; X,Y=x-cx-kx*z,y-cy-ky*z; u,v=(a22*X-a12*Y)/det,(-a21*X+a11*Y)/det
            dd=abs(math.degrees(math.atan2(v,u))-ang); dd=min(dd,360-dd)
            if best is None or dd<best[0]: best=(dd,z,math.hypot(u,v))
        print(f"   {nm:5s} z={best[1]:+.2f} r={best[2]:.3f} err={best[0]:.1f}")
analyse("frontal 30.5s",{90:(914,144),135:(750,219),180:(694,424),45:(1044,265)},(939,430),
   {'P_N':((941,340),90),'P_NW':((892,365),135),'P_W':((867,425),180),'V112':((882,263),112.5),'V157':((816,362),157.5),'F_NW':((833,303),135),'F_N':((917,262),90),'R157':((753,346),157.5)})
analyse("oblique 15s",{90:(956,102),135:(639,174),180:(467,586)},(1035,630),
   {'P_W':((891,614),180),'V157':((782,460),157.5),'V202':((765,738),202.5),'V112':((920,282),112.5),'P_NW':((1031,445),135)})
