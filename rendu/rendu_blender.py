"""Rendu photoréaliste du masque (Blender / Cycles).

Usage :
    blender -b -P rendu/rendu_blender.py -- [--stl sortie_cintre/masque.stl]
            [--out rendu/images] [--samples 128] [--res 1600] [--vues face,trois_quarts,rasante,profil]

Le STL est en mm, masque dans le plan XY (hauteur selon Y), relief vers +Z.
Matière : laiton doré patiné (le musée le présente comme « bronze », la presse dit zinc doré).
Fond : velours sombre, comme la vitrine du musée.
"""
import bpy, sys, math, os, argparse
from mathutils import Vector, Matrix


def regarde(obj, cible):
    """Oriente obj (caméra/lampe, visée -Z) vers cible, haut = +Y monde (haut du masque)."""
    f = (Vector(cible) - obj.location).normalized()
    up = Vector((0, 1, 0)) if abs(f.y) < 0.95 else Vector((0, 0, 1))
    r = f.cross(up).normalized()
    u = r.cross(f)
    obj.rotation_euler = Matrix((r, u, -f)).transposed().to_euler()


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--stl", default="sortie_cintre/masque.stl")
ap.add_argument("--out", default="rendu/images")
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--res", type=int, default=1600)
ap.add_argument("--vues", default="face,trois_quarts,rasante,profil")
ap.add_argument("--blend", default="", help="enregistrer la scène .blend (pour l'ouvrir dans Blender)")
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)

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
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    cy.device = 'GPU'
except Exception as e:
    print("GPU indisponible, CPU :", e)
sc.render.resolution_x = sc.render.resolution_y = a.res
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'

# --- masque ----------------------------------------------------------------
bpy.ops.wm.stl_import(filepath=os.path.abspath(a.stl))
m = bpy.context.selected_objects[0]
m.name = "masque"
# facettes planes : ombrage plat (pas de lissage qui baverait sur les plis)
for p in m.data.polygons:
    p.use_smooth = False
zmax = max(v.co.z for v in m.data.vertices)

mat = bpy.data.materials.new("laiton_dore")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.inputs["Metallic"].default_value = 1.0
# variation de teinte et de rugosité (patine, dorure usée)
tc = nt.nodes.new("ShaderNodeTexCoord")
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 0.035
noise.inputs["Detail"].default_value = 8
nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[0].color = (0.62, 0.42, 0.18, 1)   # bronze
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (0.95, 0.74, 0.38, 1)   # or
nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
rr = nt.nodes.new("ShaderNodeMapRange")
rr.inputs["To Min"].default_value = 0.22
rr.inputs["To Max"].default_value = 0.42
nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
# arêtes adoucies au rendu (reflets fins sur les plis, géométrie inchangée)
bev = nt.nodes.new("ShaderNodeBevel")
bev.inputs["Radius"].default_value = 0.35
bev.samples = 8
nt.links.new(bev.outputs["Normal"], bsdf.inputs["Normal"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
m.data.materials.append(mat)

# --- fond velours ------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=2000, location=(0, 0, -1))
fond = bpy.context.object
fm = bpy.data.materials.new("velours")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.035, 0.03, 0.045, 1)
fb.inputs["Roughness"].default_value = 0.9
try:
    fb.inputs["Sheen Weight"].default_value = 0.6
    fb.inputs["Sheen Tint"].default_value = (0.5, 0.45, 0.6, 1)
except KeyError:
    pass
fond.data.materials.append(fm)

# --- monde : lumière ambiante faible ----------------------------------------
w = bpy.data.worlds.new("monde")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.025, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3


def lampe(nom, pos, energie, taille, couleur=(1, 0.95, 0.88)):
    bpy.ops.object.light_add(type='AREA', location=pos)
    L = bpy.context.object
    L.name = nom
    L.data.energy = energie
    L.data.size = taille
    L.data.color = couleur
    regarde(L, (0, 0, zmax * 0.4))
    return L


cle = lampe("cle", (-260, 320, 420), 9e5, 220)
contre = lampe("contre", (380, -120, 160), 3.5e5, 120, (0.85, 0.9, 1))
deb = lampe("debouche", (150, -300, 600), 1.2e5, 500)

# --- caméra ------------------------------------------------------------------
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 150
cam_d.sensor_width = 36
cam_d.clip_end = 1e5
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 11
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam

VUES = {
    # nom : (position caméra, éclairages {lampe: énergie}, distance mise au point visée)
    "face":         ((0, 0, 1050), None),
    "trois_quarts": ((-560, -330, 820), None),
    "profil":       ((900, -60, 330), None),
    "rasante":      ((0, -120, 1040), {"cle": (0, 520, 110), "contre": (-420, -60, 80), "debouche": (0, -400, 700)}),
}
pos0 = {L.name: L.location.copy() for L in (cle, contre, deb)}
cible = Vector((0, 0, zmax * 0.35))
for nom in a.vues.split(","):
    pos, lum = VUES[nom]
    for L in (cle, contre, deb):
        L.location = pos0[L.name]
        L.hide_render = False
    if lum:
        for k, p in lum.items():
            L = bpy.data.objects[k]
            L.location = p
        bpy.data.objects["cle"].data.energy = 1.6e6
        deb.data.energy = 4e4
    else:
        cle.data.energy, deb.data.energy = 9e5, 1.2e5
    for L in (cle, contre, deb):
        regarde(L, (0, 0, zmax * 0.4))
    cam.location = pos
    regarde(cam, cible)
    cam_d.dof.focus_distance = (cible - cam.location).length
    sc.render.filepath = os.path.abspath(os.path.join(a.out, f"masque_{nom}.png"))
    bpy.ops.render.render(write_still=True)
    print("écrit", sc.render.filepath)

if a.blend:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
