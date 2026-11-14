"""Rendu photoréaliste du masque (Blender 4.2+ / Cycles).

À lancer depuis n'importe où (les chemins par défaut partent de la racine du dépôt) :

    blender -b -P rendu/rendu_blender.py -- [options]

Options principales (toutes facultatives) :
    --vues face,trois_quarts,rasante,profil   (ou « toutes », ou « aucune » pour l'animation seule)
    --res 1600          côté de référence en pixels (3840 = 4K, 7680 = 8K)
    --format carre      carre | portrait (4:5) | paysage (16:9)
    --samples 128       échantillons Cycles (512-1024 pour un rendu final 4K)
    --materiau dore     dore | or | bronze | vertdegris | zinc
    --fond velours      velours | blanc | transparent (PNG détouré avec ombre portée)
    --anim aucune       aucune | balancier (la caméra oscille ±35°) | lumiere (la lumière tourne)
    --images 120        nombre d'images de l'animation (120 = 5 s à 24 i/s)
    --gpu auto          auto | OPTIX | CUDA | HIP | METAL | ONEAPI | CPU
    --stl sortie_cintre/masque.stl     --out rendu/images     --blend rendu/masque.blend

Les animations sont écrites image par image (PNG) dans <out>/anim_<type>_<materiau>/ ;
une image déjà présente n'est pas recalculée (on peut interrompre et relancer).
Assemblage en vidéo : voir RENDU.md (ffmpeg).

Le STL est en mm, masque dans le plan XY (hauteur selon Y), relief vers +Z.
"""
import bpy, sys, math, os, argparse
from mathutils import Vector, Matrix

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def chemin(p):
    return p if os.path.isabs(p) else os.path.join(RACINE, p)


def regarde(obj, cible, haut=(0, 1, 0)):
    """Oriente obj (caméra/lampe, visée -Z) vers cible ; haut de l'image = `haut`
    (+Y = haut du masque ; +Z pour la bague debout), sauf si on vise dans cet axe."""
    f = (Vector(cible) - obj.location).normalized()
    up = Vector(haut)
    if abs(f.dot(up)) > 0.95:
        up = Vector((0, 1, 0)) if abs(f.y) < 0.95 else Vector((0, 0, 1))
    r = f.cross(up).normalized()
    u = r.cross(f)
    obj.rotation_euler = Matrix((r, u, -f)).transposed().to_euler()


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--objet", default="masque", choices=["masque", "bague"])
ap.add_argument("--stl", default="")
ap.add_argument("--out", default="rendu/images")
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--res", type=int, default=1600)
ap.add_argument("--format", default="carre", choices=["carre", "portrait", "paysage"])
ap.add_argument("--vues", default="face,trois_quarts,rasante,profil")
ap.add_argument("--materiau", default="dore", choices=["dore", "or", "bronze", "vertdegris", "zinc"])
ap.add_argument("--fond", default="velours", choices=["velours", "blanc", "transparent"])
ap.add_argument("--anim", default="aucune", choices=["aucune", "balancier", "lumiere"])
ap.add_argument("--images", type=int, default=120)
ap.add_argument("--gpu", default="auto")
ap.add_argument("--blend", default="", help="enregistrer la scène .blend (pour l'ouvrir dans Blender)")
a = ap.parse_args(argv)
BAGUE = a.objet == "bague"
if not a.stl:
    a.stl = "bague/sortie/bague_t54_losanges.stl" if BAGUE else "sortie_cintre/masque.stl"
# échelle de la scène (caméra, lampes, détails de matière) : 1 pour le masque de 200 mm
E = 0.12 if BAGUE else 1.0
OUT = chemin(a.out)
os.makedirs(OUT, exist_ok=True)

# --- scène vide -----------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'
sc.unit_settings.scale_length = 0.001  # 1 unité = 1 mm

# --- moteur ----------------------------------------------------------------
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.samples = a.samples
cy.use_denoising = True


def active_gpu(choix):
    """Choisit le meilleur back-end GPU disponible (OptiX pour une RTX, Metal sur Mac)."""
    if choix.upper() == "CPU":
        return "CPU"
    prefs = bpy.context.preferences.addons['cycles'].preferences
    essais = [choix.upper()] if choix != "auto" else ["OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"]
    for t in essais:
        try:
            prefs.compute_device_type = t
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == t]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == t
            cy.device = 'GPU'
            return t + " : " + ", ".join(d.name for d in gpus)
    return "CPU (aucun GPU trouvé)"


print("Périphérique de rendu :", active_gpu(a.gpu))

L_, H_ = {"carre": (a.res, a.res),
          "portrait": (round(a.res * 0.8), a.res),
          "paysage": (a.res, round(a.res * 9 / 16))}[a.format]
sc.render.resolution_x, sc.render.resolution_y = L_, H_
sc.render.resolution_percentage = 100
sc.render.film_transparent = a.fond == "transparent"
sc.render.image_settings.color_mode = 'RGBA' if a.fond == "transparent" else 'RGB'
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'

# --- masque ----------------------------------------------------------------
bpy.ops.wm.stl_import(filepath=chemin(a.stl))
m = bpy.context.selected_objects[0]
m.name = "masque"
# facettes planes : ombrage plat (pas de lissage qui baverait sur les plis)
for p in m.data.polygons:
    p.use_smooth = False
zmax = max(v.co.z for v in m.data.vertices)
zmin = min(v.co.z for v in m.data.vertices)
# point visé et hauteur visée par les lampes
zc = (zmax + zmin) / 2 if BAGUE else zmax * 0.35
zl = zc if BAGUE else zmax * 0.4

# Matières : (couleur sombre, couleur claire, rugosité min, max, couleur des creux ou None)
MATIERES = {
    "dore":       ((0.62, 0.42, 0.18), (0.95, 0.74, 0.38), 0.22, 0.42, None),  # dorure patinée
    "or":         ((0.90, 0.66, 0.30), (1.00, 0.80, 0.45), 0.08, 0.18, None),  # dorure neuve
    "bronze":     ((0.30, 0.17, 0.08), (0.72, 0.48, 0.28), 0.25, 0.45, (0.05, 0.03, 0.02)),
    "vertdegris": ((0.40, 0.24, 0.12), (0.75, 0.52, 0.30), 0.30, 0.50, (0.20, 0.42, 0.34)),
    "zinc":       ((0.55, 0.57, 0.58), (0.75, 0.77, 0.78), 0.35, 0.55, (0.25, 0.26, 0.27)),
}
c1, c2, rmin, rmax, creux = MATIERES[a.materiau]

mat = bpy.data.materials.new(a.materiau)
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Metallic"].default_value = 1.0
# variation de teinte et de rugosité (patine, usure)
tc = nt.nodes.new("ShaderNodeTexCoord")
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 0.035 / E
noise.inputs["Detail"].default_value = 8
nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[0].color = (*c1, 1)
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (*c2, 1)
nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
rr = nt.nodes.new("ShaderNodeMapRange")
rr.inputs["To Min"].default_value = rmin
rr.inputs["To Max"].default_value = rmax
nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
couleur = ramp.outputs["Color"]
if creux:
    # patine logée au fond des plis (occlusion ambiante) : métal frotté sur les crêtes
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 12.0 * E
    ao.samples = 16
    pr = nt.nodes.new("ShaderNodeMapRange")
    pr.inputs["From Min"].default_value = 0.55
    pr.inputs["From Max"].default_value = 0.95
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.inputs["A"].default_value = (*creux, 1)
    nt.links.new(ao.outputs["AO"], pr.inputs["Value"])
    nt.links.new(pr.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(couleur, mix.inputs["B"])
    couleur = mix.outputs["Result"]
    # la patine n'est pas métallique
    nt.links.new(pr.outputs["Result"], bsdf.inputs["Metallic"])
nt.links.new(couleur, bsdf.inputs["Base Color"])
# arêtes adoucies au rendu (reflets fins sur les plis, géométrie inchangée)
bev = nt.nodes.new("ShaderNodeBevel")
bev.inputs["Radius"].default_value = 0.35 * E
bev.samples = 8
nt.links.new(bev.outputs["Normal"], bsdf.inputs["Normal"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
m.data.materials.append(mat)

# --- fond --------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=4000 * E, location=(0, 0, zmin - 0.01 if BAGUE else -1))
fond = bpy.context.object
fm = bpy.data.materials.new("fond")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
if a.fond == "velours":
    fb.inputs["Base Color"].default_value = (0.035, 0.03, 0.045, 1)
    fb.inputs["Roughness"].default_value = 0.9
    try:
        fb.inputs["Sheen Weight"].default_value = 0.6
        fb.inputs["Sheen Tint"].default_value = (0.5, 0.45, 0.6, 1)
    except KeyError:
        pass
else:
    fb.inputs["Base Color"].default_value = (0.8, 0.79, 0.77, 1)
    fb.inputs["Roughness"].default_value = 0.8
fond.data.materials.append(fm)
if a.fond == "transparent":
    fond.is_shadow_catcher = True  # ne garde que l'ombre portée

# --- monde : lumière ambiante ------------------------------------------------
w = bpy.data.worlds.new("monde")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
clair = a.fond != "velours"
bg.inputs["Color"].default_value = (0.8, 0.8, 0.82, 1) if clair else (0.02, 0.02, 0.025, 1)
bg.inputs["Strength"].default_value = 0.25 if clair else 0.3


def lampe(nom, pos, energie, taille, couleur=(1, 0.95, 0.88)):
    bpy.ops.object.light_add(type='AREA', location=pos)
    L = bpy.context.object
    L.name = nom
    L.location = Vector(pos) * E + Vector((0, 0, zc if BAGUE else 0))
    L.data.energy = energie * E * E
    L.data.size = taille * E
    L.data.color = couleur
    regarde(L, (0, 0, zl))
    return L


cle = lampe("cle", (-260, 320, 420), 9e5, 220)
contre = lampe("contre", (380, -120, 160), 3.5e5, 120, (0.85, 0.9, 1))
deb = lampe("debouche", (150, -300, 600), 1.2e5, 500)
LAMPES = (cle, contre, deb)
pos0 = {L.name: L.location.copy() for L in LAMPES}
nrj0 = {L.name: L.data.energy / (E * E) for L in LAMPES}

# --- caméra ------------------------------------------------------------------
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 150
cam_d.sensor_fit = 'VERTICAL'   # même cadrage vertical quel que soit le format
cam_d.sensor_height = 36
cam_d.clip_start = 0.1
cam_d.clip_end = 1e5
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 16 if BAGUE else 11
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
cible = Vector((0, 0, zc))

VUES = {
    # nom : (position caméra, lampes déplacées {nom: position} ou None)
    "face":         ((0, 0, 1050), None),
    "trois_quarts": ((-560, -330, 820), None),
    "profil":       ((900, -60, 330), None),
    "rasante":      ((0, -120, 1040), {"cle": (0, 520, 110), "contre": (-420, -60, 80),
                                       "debouche": (0, -400, 700)}),
}
if BAGUE:
    VUES = {
        "dessus":       ((0, -60, 1050), None),
        "trois_quarts": ((-600, -420, 760), None),
        "profil":       ((1000, -150, 260), None),
        "bout":         ((150, -900, 520), None),
        "rasante":      ((0, -120, 1040), {"cle": (0, 520, 110), "contre": (-420, -60, 80),
                                           "debouche": (0, -400, 700)}),
    }
    if a.vues == "face,trois_quarts,rasante,profil":
        a.vues = "trois_quarts,dessus,profil,bout"
NRJ_RASANTE = {"cle": 1.6e6, "debouche": 4e4}


def place(pos_cam, lum=None, nrj=None):
    dz = Vector((0, 0, zc if BAGUE else 0))
    for L in LAMPES:
        q = (lum or {}).get(L.name)
        L.location = Vector(q) * E + dz if q else pos0[L.name]
        L.data.energy = (nrj or {}).get(L.name, nrj0[L.name]) * E * E
        regarde(L, (0, 0, zl))
    cam.location = Vector(pos_cam) * E + dz
    regarde(cam, cible, (0, 0, 1) if BAGUE else (0, 1, 0))
    cam_d.dof.focus_distance = (cible - cam.location).length


def rend(fichier):
    sc.render.filepath = fichier
    bpy.ops.render.render(write_still=True)
    print("écrit", fichier, flush=True)


suffixe = "" if (a.materiau, a.fond) == ("dore", "velours") else f"_{a.materiau}_{a.fond}"
prefixe = os.path.splitext(os.path.basename(a.stl))[0] if BAGUE else "masque"
vues = list(VUES) if a.vues == "toutes" else [] if a.vues == "aucune" else a.vues.split(",")
for nom in vues:
    pos, lum = VUES[nom]
    place(pos, lum, NRJ_RASANTE if lum else None)
    rend(os.path.join(OUT, f"{prefixe}_{nom}{suffixe}.png"))

# --- animations --------------------------------------------------------------
if a.anim != "aucune":
    dossier = os.path.join(OUT, f"anim_{a.anim}_{a.materiau}" + ("_" + prefixe if BAGUE else ""))
    os.makedirs(dossier, exist_ok=True)
    N = a.images
    for i in range(N):
        f = os.path.join(dossier, f"{i:04d}.png")
        if os.path.exists(f):
            continue  # reprise après interruption
        t = 2 * math.pi * i / N  # boucle parfaite
        if a.anim == "balancier":
            # caméra qui oscille de ±35° autour de l'axe vertical, lumières fixes :
            # les facettes s'allument et s'éteignent tour à tour
            ang = math.radians(35) * math.sin(t)
            d = 1050
            place((d * math.sin(ang), -80 * math.cos(t) ** 2, d * math.cos(ang)))
        else:
            # caméra de face, lumière rasante qui fait le tour du masque
            r, h = 560, 140
            place((0, 0, 1050),
                  {"cle": (r * math.sin(t), r * math.cos(t), h), "contre": (0, 0, -5000),
                   "debouche": (0, -400, 900)},
                  {"cle": 1.6e6, "contre": 0, "debouche": 2.5e4})
        rend(f)

if a.blend:
    bpy.ops.wm.save_as_mainfile(filepath=chemin(a.blend))
