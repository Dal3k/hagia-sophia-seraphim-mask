"""Bague-chevalière « masque des séraphins » : générateur STL (Blender 4.2+).

    blender -b -P bague/bague.py -- [--taille 54] [--motif losanges] [--b 9] ...

Conception
- Chaton : l'étoile du masque (géométrie de masque_seraphin.py, polyèdre pur) réduite à
  b = 9 mm (18 × 12.7 mm, relief 2.8 mm), grand axe LE LONG DU DOIGT (axe Y). Elle est
  légèrement cintrée autour du doigt (rayon --courbure) en déplaçant les sommets : les
  facettes restent planes, les arêtes droites. Dessous : paroi verticale qui suit
  l'ellipse et descend jusqu'au doigt (creusé au rayon intérieur).
- Anneau : jonc à facettes planes, dans le langage des plis du masque. 32 sections ;
  profil « gouttière » = deux crêtes et un sillon central (la branche T-M-P du masque,
  qui prolonge les pointes latérales T2/T6) ; motif « losanges » = profils en W et en Λ
  alternés, ce qui donne une file de losanges creux comme l'étoile centrale.
  Plus large et plus épais aux épaules qu'en dessous.
- Intérieur lisse (cylindre), pour le confort.

Taille : tour de doigt en mm (taille française), diamètre intérieur = taille / π.
Sortie : bague/sortie/bague_t<taille>_<motif>.stl (un seul solide étanche, en mm).
"""
import bpy, bmesh, sys, os, math, argparse
from mathutils import Vector

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import masque_seraphin as ms  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--taille", type=float, default=54, help="tour de doigt en mm (taille FR)")
ap.add_argument("--b", type=float, default=9.0, help="demi-longueur de l'étoile (mm)")
ap.add_argument("--courbure", type=float, default=16.0, help="rayon de cintrage de l'étoile (mm), 0 = plate")
ap.add_argument("--sous", type=float, default=1.4, help="épaisseur de métal sous l'étoile, au centre (mm)")
ap.add_argument("--motif", default="losanges", choices=["gouttiere", "losanges"])
ap.add_argument("--largeur", type=float, nargs=2, default=(6.0, 3.2), help="largeur du jonc épaules / dessous")
ap.add_argument("--epaisseur", type=float, nargs=2, default=(1.9, 1.6), help="épaisseur du jonc épaules / dessous")
ap.add_argument("--sections", type=int, default=32)
ap.add_argument("--out", default="bague/sortie")
ap.add_argument("--blend", default="")
a = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
r_in = a.taille / math.pi / 2
z0 = r_in + a.sous                   # niveau du rebord de l'étoile, au centre
Rb = a.courbure


# ------------------------------------------------------------------ chaton
def cintre(x, y, z):
    """Enroule le plan de l'étoile autour d'un cylindre d'axe Y (rayon Rb, sommet en z0)."""
    if Rb <= 0:
        return Vector((x, y, z0 + z))
    th = x / Rb
    r = Rb + z
    return Vector((r * math.sin(th), y, z0 - Rb + r * math.cos(th)))


p = dict(ms.P)
p.update(b=a.b, hc=ms.P["hc"] * a.b / 100, fleche=0.0, arc=8)
pts, faces, rim, ids = ms.build(p)

bm = bmesh.new()
top = [bm.verts.new(cintre(*q)) for q in pts]
for f in faces:
    try:
        bm.faces.new([top[i] for i in f])
    except ValueError:
        pass
# paroi verticale sous le contour de l'ellipse, jusqu'à z = 0.6·r_in (largement dans le doigt)
zb = 0.6 * r_in
bot = [bm.verts.new((top[i].co.x, top[i].co.y, zb)) for i in rim]
m = len(rim)
for k in range(m):
    t0, t1 = top[rim[k]], top[rim[(k + 1) % m]]
    b0, b1 = bot[k], bot[(k + 1) % m]
    bm.faces.new([t0, b0, b1, t1])
bm.faces.new(bot)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
me = bpy.data.meshes.new("chaton")
bm.to_mesh(me)
bm.free()


# ------------------------------------------------------------------ jonc
def profil(w, t, k):
    """Section du jonc (u le long du doigt, h radial depuis l'intérieur).
    Intérieur un peu sous r_in : il sera recoupé par le cylindre du doigt."""
    ext = [(w / 2, 0.55 * t), (w / 4, t), (0, 0.70 * t), (-w / 4, t), (-w / 2, 0.55 * t)]
    if a.motif == "losanges" and k % 2:
        ext = [(w / 2, 0.55 * t), (w / 4, 0.80 * t), (0, t), (-w / 4, 0.80 * t), (-w / 2, 0.55 * t)]
    return [(-w / 2, -0.3), (w / 2, -0.3)] + ext


# Le jonc est un arc ouvert : ses deux bouts sont noyés dans le chaton.
al0 = math.radians(30)
N = a.sections
bm = bmesh.new()
rings = []
for k in range(N + 1):
    al = al0 + (2 * math.pi - 2 * al0) * k / N
    s = ((1 + math.cos(al)) / 2) ** 1.5            # 1 aux épaules, 0 dessous
    w = a.largeur[1] + (a.largeur[0] - a.largeur[1]) * s
    t = a.epaisseur[1] + (a.epaisseur[0] - a.epaisseur[1]) * s
    e = Vector((math.sin(al), 0, math.cos(al)))
    rings.append([bm.verts.new(e * (r_in + h) + Vector((0, u, 0))) for u, h in profil(w, t, k)])
n = len(rings[0])
for k in range(N):
    A, B = rings[k], rings[k + 1]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([A[i], A[j], B[j], B[i]])
bm.faces.new(rings[0])
bm.faces.new(list(reversed(rings[-1])))
bmesh.ops.triangulate(bm, faces=bm.faces)       # facettes planes garanties
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mj = bpy.data.meshes.new("jonc")
bm.to_mesh(mj)
bm.free()

# ------------------------------------------------------------------ assemblage
chaton = bpy.data.objects.new("chaton", me)
jonc = bpy.data.objects.new("jonc", mj)
for o in (chaton, jonc):
    sc.collection.objects.link(o)

bpy.ops.mesh.primitive_cylinder_add(vertices=192, radius=r_in, depth=60, rotation=(math.pi / 2, 0, 0))
doigt = bpy.context.object
doigt.name = "doigt"


def booleen(obj, autre, op):
    md = obj.modifiers.new(op, 'BOOLEAN')
    md.operation = op
    md.solver = 'EXACT'
    md.object = autre
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=md.name)


booleen(chaton, jonc, 'UNION')
booleen(chaton, doigt, 'DIFFERENCE')
bpy.data.objects.remove(jonc)
bpy.data.objects.remove(doigt)
chaton.name = "bague"

# contrôle : solide fermé ?
bm = bmesh.new()
bm.from_mesh(chaton.data)
ouvert = sum(1 for e in bm.edges if not e.is_manifold)
vol = bm.calc_volume()
bm.free()
os.makedirs(os.path.join(RACINE, a.out), exist_ok=True)
nom = f"bague_t{a.taille:g}_{a.motif}"
stl = os.path.join(RACINE, a.out, nom + ".stl")
bpy.ops.object.select_all(action='DESELECT')
chaton.select_set(True)
bpy.ops.wm.stl_export(filepath=stl, export_selected_objects=True)
print(f"BAGUE taille {a.taille:g} (Ø int. {2 * r_in:.2f} mm), étoile {2 * p['b'] * p['ratio']:.1f} × "
      f"{2 * p['b']:.1f} mm, relief {p['hc']:.2f} mm, motif {a.motif} ; "
      f"{len(chaton.data.polygons)} faces, arêtes non étanches : {ouvert}, volume {vol:.0f} mm³ "
      f"(or 18 ct ≈ {vol * 0.0155:.1f} g, argent ≈ {vol * 0.0104:.1f} g, bronze ≈ {vol * 0.0088:.1f} g)")
print("écrit", stl)
if a.blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(RACINE, a.blend))
