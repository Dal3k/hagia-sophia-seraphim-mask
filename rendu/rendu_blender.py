"""Rendu photoréaliste du masque (Blender 4.2+ / Cycles).

À lancer depuis n'importe où (les chemins par défaut partent de la racine du dépôt) :

    blender -b -P rendu/rendu_blender.py -- [options]

Options principales (toutes facultatives) :
    --vues face,trois_quarts,rasante,profil   (ou « toutes », ou « aucune » pour l'animation seule)
    --res 1600          côté de référence en pixels (3840 = 4K, 7680 = 8K)
    --format carre      carre | portrait (4:5) | paysage (16:9)
    --samples 128       échantillons Cycles (512-1024 pour un rendu final 4K)
    --materiau dore     dore | or | bronze | vertdegris | zinc, ou un métal réel :
                        argent | acier | or_jaune | laiton | bronze_nu (avec --finition)
    --fond velours      velours | blanc | transparent (PNG détouré avec ombre portée)
    --anim aucune       aucune | balancier (la caméra oscille ±35°) | lumiere (la lumière tourne)
                        | vitrine (vidéo de présentation : caméra en huit + lumière qui tourne)
    --images 120        nombre d'images de balancier / lumiere (120 = 5 s à 24 i/s)
    --duree 20 --ips 30 vitrine : durée en secondes et images par seconde
    --amplitude 30      vitrine : balayage de la caméra (± degrés)
    --vue_video face    vitrine : vue de départ
    --gpu auto          auto | OPTIX | CUDA | HIP | METAL | ONEAPI | CPU
    --stl sortie_cintre/masque.stl     --out rendu/images     --blend rendu/masque.blend

Les animations sont enregistrées en images clés (la scène .blend se rejoue dans Blender), puis
calculées image par image (PNG) dans <out>/anim_<type>_<materiau>/ (vitrine :
<out>/video_masque_<hauteur>p<ips>/, puis assemblées en MP4 si ffmpeg est installé).
Une image déjà présente n'est pas recalculée (on peut interrompre et relancer).

Le STL est en mm, masque dans le plan XY (hauteur selon Y), relief vers +Z.
"""
import bpy, sys, math, os, argparse
from mathutils import Vector, Matrix

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def chemin(p):
    return p if os.path.isabs(p) else os.path.join(RACINE, p)


def regarde(obj, cible, haut=(0, 1, 0)):
    """Oriente obj (caméra/lampe, visée -Z) vers cible ; haut de l'image = `haut`
    (+Y = haut du masque), sauf si on vise dans cet axe."""
    f = (Vector(cible) - obj.location).normalized()
    up = Vector(haut)
    if abs(f.dot(up)) > 0.95:
        up = Vector((0, 1, 0)) if abs(f.y) < 0.95 else Vector((0, 0, 1))
    r = f.cross(up).normalized()
    u = r.cross(f)
    # angles compatibles avec les précédents : pas de saut de 360° entre deux images clés
    obj.rotation_euler = Matrix((r, u, -f)).transposed().to_euler('XYZ', obj.rotation_euler)


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--stl", default="sortie_cintre/masque.stl")
ap.add_argument("--patine", type=float, default=1.0,
                help="force de la patine (taches de teinte) : 1 forte, 0 uniforme")
ap.add_argument("--nom", default="", help="préfixe des images (remplace le nom automatique et le suffixe)")
ap.add_argument("--out", default="rendu/images")
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--res", type=int, default=1600)
ap.add_argument("--format", default="carre", choices=["carre", "portrait", "paysage"])
ap.add_argument("--vues", default="face,trois_quarts,rasante,profil")
ap.add_argument("--materiau", default="dore", choices=["dore", "or", "bronze", "vertdegris", "zinc",
                                                        "argent", "acier", "or_jaune", "laiton", "bronze_nu"])
ap.add_argument("--fond", default="velours", choices=["velours", "blanc", "transparent"])
ap.add_argument("--finition", default="poli", choices=["poli", "poli_ondule", "satine", "brosse", "mixte"],
                help="métaux réels : poli (faces planes parfaites), poli_ondule (faces légèrement ondulées, "
                     "arêtes arrondies), satine, brosse (stries), mixte (crêtes polies, faces satinées, creux sablés)")
ap.add_argument("--studio", default="non", choices=["oui", "non"],
                help="reflets de studio (diffuseurs en bandes autour du masque) au lieu d'un monde sombre uniforme")
ap.add_argument("--anim", default="aucune", choices=["aucune", "balancier", "lumiere", "vitrine"])
ap.add_argument("--images", type=int, default=120)
ap.add_argument("--duree", type=float, default=20, help="vitrine : durée (s)")
ap.add_argument("--ips", type=int, default=30, help="vitrine : images par seconde")
ap.add_argument("--amplitude", type=float, default=30, help="vitrine : balayage de la caméra (± degrés)")
ap.add_argument("--vue_video", default="face", help="vitrine : vue de départ")
ap.add_argument("--mp4", default="oui", choices=["oui", "non"], help="vitrine : assembler la vidéo avec ffmpeg")
ap.add_argument("--gpu", default="auto")
ap.add_argument("--blend", default="", help="enregistrer la scène .blend (pour l'ouvrir dans Blender)")
a = ap.parse_args(argv)
if a.anim != "aucune" and a.vues == ap.get_default("vues"):
    a.vues = "aucune"   # une animation seule ne recalcule pas les vues fixes
# échelle de la scène (caméra, lampes, détails de matière) : 1 pour le masque de 200 mm
E = 1.0
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
# aperçu interactif dans Blender (fichier .blend) : débruité, 128 échantillons
cy.preview_samples = 128
cy.use_preview_denoising = True


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
# débruitage OpenImageDenoise sur la carte graphique aussi : par défaut Blender le fait tourner
# sur le processeur (tous les cœurs, plusieurs secondes par image en 4K)
if cy.device == 'GPU':
    for att in ("denoising_use_gpu", "preview_denoising_use_gpu"):
        if hasattr(cy, att):
            setattr(cy, att, True)
print("Débruitage :", cy.denoiser, "sur", "GPU" if getattr(cy, "denoising_use_gpu", False) else "CPU")

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
zc = zmax * 0.35
zl = zmax * 0.4

# Matières : (couleur sombre, couleur claire, rugosité min, max, couleur des creux ou None)
MATIERES = {
    "dore":       ((0.62, 0.42, 0.18), (0.95, 0.74, 0.38), 0.22, 0.42, None),  # dorure patinée
    "or":         ((0.90, 0.66, 0.30), (1.00, 0.80, 0.45), 0.08, 0.18, None),  # dorure neuve
    "bronze":     ((0.30, 0.17, 0.08), (0.72, 0.48, 0.28), 0.25, 0.45, (0.05, 0.03, 0.02)),
    "vertdegris": ((0.40, 0.24, 0.12), (0.75, 0.52, 0.30), 0.30, 0.50, (0.20, 0.42, 0.34)),
    "zinc":       ((0.55, 0.57, 0.58), (0.75, 0.77, 0.78), 0.35, 0.55, (0.25, 0.26, 0.27)),
}

# Métaux réels (voir metal_physique) : (réflectance de face F0 et teinte des reflets rasants F82,
# en couleurs linéaires mesurées ; rugosité des faces polies ; rugosité et couleur au fond des
# creux, là où le polissage ne passe pas et où le métal ternit, ou None)
METAUX = {
    "argent":    ((0.962, 0.949, 0.922), (1.00, 1.00, 1.00), 0.10, 0.30, (0.10, 0.095, 0.09)),   # argent 925
    "acier":     ((0.672, 0.637, 0.585), (0.95, 0.96, 1.00), 0.09, 0.22, None),                 # acier 316L
    "or_jaune":  ((0.944, 0.776, 0.373), (1.00, 0.96, 0.88), 0.08, 0.22, None),                 # or jaune 18 ct
    "laiton":    ((0.910, 0.778, 0.423), (1.00, 0.97, 0.90), 0.11, 0.30, (0.30, 0.22, 0.10)),
    "bronze_nu": ((0.800, 0.590, 0.400), (1.00, 0.95, 0.90), 0.12, 0.35, (0.09, 0.05, 0.03)),   # bronze de fonte
}


def metal_physique(nom):
    """Métal réel : couleur mesurée (F0 + teinte rasante F82 du Principled), fond des creux plus mat
    et terni, finition --finition :
      poli         faces planes parfaites, grain de polissage très fin (référence) ;
      poli_ondule  le polissage creuse et arrondit à peine chaque face (ondulation lente : le reflet
                   d'un diffuseur se tord et se dégrade au lieu d'un aplat net), arêtes plus rondes ;
      satine       idem, faces satinées (reflets larges et doux) ;
      brosse       idem, stries parallèles (reflets étirés en travers des stries) ;
      mixte        idem, crêtes et arêtes polies, faces satinées, creux sablés et ternis."""
    f0, f82, r_poli, r_creux, terni = METAUX[nom]
    fi = a.finition
    ondule = fi != "poli"
    r_face = {"satine": 0.28, "brosse": 0.24, "mixte": 0.28}.get(fi, r_poli)
    if fi == "mixte":
        r_creux = 0.5
    mat = bpy.data.materials.new(nom)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    out = N("ShaderNodeOutputMaterial")
    bsdf = N("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Specular Tint"].default_value = (*f82, 1)
    tc = N("ShaderNodeTexCoord")
    # léger manque d'uniformité du métal (grandes taches très discrètes)
    gros = N("ShaderNodeTexNoise")
    gros.inputs["Scale"].default_value = 0.035 / E
    gros.inputs["Detail"].default_value = 6
    L(tc.outputs["Object"], gros.inputs["Vector"])
    teinte = N("ShaderNodeMix")
    teinte.data_type = 'RGBA'
    teinte.inputs["A"].default_value = (*(c * 0.9 for c in f0), 1)
    teinte.inputs["B"].default_value = (*f0, 1)
    L(gros.outputs["Fac"], teinte.inputs["Factor"])
    # grain fin : polissage, satinage ou stries du brossage (bruit étiré le long de X)
    vec = tc.outputs["Object"]
    if fi == "brosse":
        mp = N("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (0.03, 1.0, 1.0)
        L(vec, mp.inputs["Vector"])
        vec = mp.outputs["Vector"]
    fin = N("ShaderNodeTexNoise")
    fin.inputs["Scale"].default_value = (4.0 if fi == "brosse" else 0.6) / E
    fin.inputs["Detail"].default_value = 10
    fin.inputs["Roughness"].default_value = 0.6
    L(vec, fin.inputs["Vector"])
    # creux (occlusion ambiante) : 0 au fond des plis, 1 sur les faces dégagées
    ao = N("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 12.0 * E
    ao.samples = 16
    expo = N("ShaderNodeMapRange")
    expo.inputs["From Min"].default_value = 0.55
    expo.inputs["From Max"].default_value = 0.95
    L(ao.outputs["AO"], expo.inputs["Value"])
    rug = N("ShaderNodeMapRange")
    rug.inputs["To Min"].default_value = r_creux
    rug.inputs["To Max"].default_value = r_face
    L(expo.outputs["Result"], rug.inputs["Value"])
    r_out = rug.outputs["Result"]
    # arêtes adoucies au rendu (biseau), plus rondes quand la pièce est polie à la main
    bev = N("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = (0.8 if ondule else 0.35) * E
    bev.samples = 8
    if fi == "mixte":
        # crêtes : près d'une arête (la normale biseautée large s'écarte de la vraie normale) et
        # dégagées (pas au fond d'un pli) ; le polissoir ne touche que là
        bl = N("ShaderNodeBevel")
        bl.inputs["Radius"].default_value = 2.5 * E
        bl.samples = 8
        geo = N("ShaderNodeNewGeometry")
        dp = N("ShaderNodeVectorMath")
        dp.operation = 'DOT_PRODUCT'
        L(bl.outputs["Normal"], dp.inputs[0])
        L(geo.outputs["Normal"], dp.inputs[1])
        arete = N("ShaderNodeMapRange")
        arete.inputs["From Min"].default_value = 0.995
        arete.inputs["From Max"].default_value = 0.9995
        arete.inputs["To Min"].default_value = 1.0
        arete.inputs["To Max"].default_value = 0.0
        L(dp.outputs["Value"], arete.inputs["Value"])
        crete = N("ShaderNodeMath")
        crete.operation = 'MULTIPLY'
        L(arete.outputs["Result"], crete.inputs[0])
        L(expo.outputs["Result"], crete.inputs[1])
        mr = N("ShaderNodeMix")
        mr.data_type = 'FLOAT'
        mr.inputs["B"].default_value = 0.05
        L(crete.outputs["Value"], mr.inputs["Factor"])
        L(r_out, mr.inputs["A"])
        r_out = mr.outputs["Result"]
    grain = N("ShaderNodeMapRange")                      # ±0.04 de rugosité selon le grain fin
    grain.inputs["To Min"].default_value = -0.04
    grain.inputs["To Max"].default_value = 0.04
    L(fin.outputs["Fac"], grain.inputs["Value"])
    somme = N("ShaderNodeMath")
    somme.operation = 'ADD'
    somme.use_clamp = True
    L(r_out, somme.inputs[0])
    L(grain.outputs["Result"], somme.inputs[1])
    L(somme.outputs["Value"], bsdf.inputs["Roughness"])
    if fi == "brosse":
        # reflets étirés en travers des stries (stries le long de X)
        bsdf.inputs["Anisotropic"].default_value = 0.85
        tg = N("ShaderNodeCombineXYZ")
        tg.inputs["X"].default_value = 1.0
        L(tg.outputs["Vector"], bsdf.inputs["Tangent"])
    couleur = teinte.outputs["Result"]
    if terni:
        mix = N("ShaderNodeMix")
        mix.data_type = 'RGBA'
        mix.inputs["A"].default_value = (*terni, 1)
        L(expo.outputs["Result"], mix.inputs["Factor"])
        L(couleur, mix.inputs["B"])
        couleur = mix.outputs["Result"]
    L(couleur, bsdf.inputs["Base Color"])
    # relief : grain fin, plus l'ondulation lente des faces (quelques ondes par facette, pente ~1°)
    bump = N("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    bump.inputs["Distance"].default_value = 0.02 * E
    L(fin.outputs["Fac"], bump.inputs["Height"])
    normale = bev.outputs["Normal"]
    if ondule:
        onde = N("ShaderNodeTexNoise")
        onde.inputs["Scale"].default_value = 0.12 / E
        onde.inputs["Detail"].default_value = 1.5
        L(tc.outputs["Object"], onde.inputs["Vector"])
        b2 = N("ShaderNodeBump")
        b2.inputs["Strength"].default_value = 1.0
        b2.inputs["Distance"].default_value = 0.15 * E
        L(onde.outputs["Fac"], b2.inputs["Height"])
        L(normale, b2.inputs["Normal"])
        normale = b2.outputs["Normal"]
    L(normale, bump.inputs["Normal"])
    L(bump.outputs["Normal"], bsdf.inputs["Normal"])
    L(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def matiere(nom):
    """Matière métallique `nom` (voir MATIERES et METAUX). La patine (variation de teinte
    et de rugosité) est réduite par --patine (1 = forte, 0 = uniforme)."""
    if nom in METAUX:
        return metal_physique(nom)
    c1, c2, rmin, rmax, creux = MATIERES[nom]
    mi = [(x + y) / 2 for x, y in zip(c1, c2)]
    c1 = tuple(m_ + (x - m_) * PATINE for x, m_ in zip(c1, mi))
    c2 = tuple(m_ + (y - m_) * PATINE for y, m_ in zip(c2, mi))
    rmin, rmax = (rmin + rmax) / 2 - (rmax - rmin) / 2 * PATINE, (rmin + rmax) / 2 + (rmax - rmin) / 2 * PATINE
    mat = bpy.data.materials.new(nom)
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
    return mat


PATINE = a.patine
m.data.materials.append(matiere(a.materiau))

# --- fond --------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, -1))
fond = bpy.context.object
fond.name = "sol"
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
if a.studio == "oui":
    # Studio de photo : un métal poli montre surtout ce qu'il reflète. Autour du masque
    # (+Z = côté caméra et lampes), une tente claire en dégradé, deux grands diffuseurs en bandes
    # à gauche et à droite de l'objectif et une bande en haut ; autour de l'objectif, du noir
    # (les faces tournées vers la caméra restent sombres, comme en vrai). Invisible à la caméra.
    wt = w.node_tree
    W = wt.nodes.new
    d = W("ShaderNodeTexCoord").outputs["Generated"]   # direction du rayon (monde)
    sep = W("ShaderNodeSeparateXYZ")
    wt.links.new(d, sep.inputs["Vector"])

    def lisse_entre(val, de, a_, vers=(0.0, 1.0)):
        n_ = W("ShaderNodeMapRange")
        n_.interpolation_type = 'SMOOTHERSTEP'
        n_.inputs["From Min"].default_value, n_.inputs["From Max"].default_value = de, a_
        n_.inputs["To Min"].default_value, n_.inputs["To Max"].default_value = vers
        wt.links.new(val, n_.inputs["Value"])
        return n_.outputs["Result"]

    def op(o_, x, y):
        n_ = W("ShaderNodeMath")
        n_.operation = o_
        for k_, v_ in enumerate((x, y)):
            if isinstance(v_, (int, float)):
                n_.inputs[k_].default_value = v_
            else:
                wt.links.new(v_, n_.inputs[k_])
        return n_.outputs["Value"]

    def bande(axe, centre, demi, flou, force):
        """Diffuseur en bande : directions dont la composante `axe` vaut `centre` ± `demi`,
        bords adoucis sur `flou`, plus lumineux vers le haut (dégradé du diffuseur)."""
        ecart = op('ABSOLUTE', op('SUBTRACT', sep.outputs[axe], centre), 0)
        b_ = lisse_entre(ecart, demi, demi + flou, (1.0, 0.0))
        return op('MULTIPLY', op('MULTIPLY', b_, lisse_entre(sep.outputs["Z"], 0.0, 0.9, (0.35, 1.0))), force)

    tente = lisse_entre(sep.outputs["Z"], -0.1, 0.8, (0.0, 0.2))
    total = op('ADD', tente, bande("X", -0.55, 0.12, 0.08, 2.4))      # diffuseur gauche
    total = op('ADD', total, bande("X", 0.62, 0.08, 0.06, 1.5))       # diffuseur droit, plus étroit
    total = op('ADD', total, bande("Y", 0.60, 0.06, 0.05, 1.8))       # bande haute
    # noir autour de l'objectif (cône de ~35° autour de +Z)
    total = op('MULTIPLY', total, lisse_entre(sep.outputs["Z"], 0.78, 0.86, (1.0, 0.03)))
    total = op('MULTIPLY', total, lisse_entre(sep.outputs["Z"], -0.2, 0.05))   # rien sous le sol
    em = W("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.97, 0.93, 1)
    wt.links.new(total, em.inputs["Strength"])
    # le studio ne se voit que dans les reflets (rayons brillants) : le fond de velours et
    # l'éclairage d'ensemble restent ceux des lampes, la caméra voit l'ancien fond uniforme
    lp = W("ShaderNodeLightPath")
    mx = W("ShaderNodeMixShader")
    wt.links.new(lp.outputs["Is Glossy Ray"], mx.inputs["Fac"])
    wt.links.new(bg.outputs["Background"], mx.inputs[1])
    wt.links.new(em.outputs["Emission"], mx.inputs[2])
    wt.links.new(mx.outputs["Shader"], wt.nodes["World Output"].inputs["Surface"])


def lampe(nom, pos, energie, taille, couleur=(1, 0.95, 0.88)):
    bpy.ops.object.light_add(type='AREA', location=pos)
    L = bpy.context.object
    L.name = nom
    L.location = Vector(pos) * E
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
cam_d.dof.aperture_fstop = 11
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
NRJ_RASANTE = {"cle": 1.6e6, "debouche": 4e4}
HAUT = Vector((0, 1, 0))   # haut de l'image = haut du masque


def place(pos_cam, lum=None, nrj=None):
    """Caméra et lampes sur une vue ; renvoie (point visé par la caméra, par les lampes)."""
    cl = Vector((0, 0, zl))
    for L in LAMPES:
        q = (lum or {}).get(L.name)
        L.location = Vector(q) * E if q else pos0[L.name]
        L.data.energy = (nrj or {}).get(L.name, nrj0[L.name]) * E * E
        regarde(L, cl)
    cam.location = Vector(pos_cam) * E
    regarde(cam, cible, HAUT)
    cam_d.dof.focus_distance = (cible - cam.location).length
    return cible, cl


def rend(fichier):
    sc.render.filepath = fichier
    bpy.ops.render.render(write_still=True)
    print("écrit", fichier, flush=True)


suffixe = "" if (a.materiau, a.fond) == ("dore", "velours") or a.nom else f"_{a.materiau}_{a.fond}"
prefixe = a.nom or "masque"
vues = list(VUES) if a.vues == "toutes" else [] if a.vues == "aucune" else a.vues.split(",")
for nom in vues:
    pos, lum = VUES[nom]
    place(pos, lum, NRJ_RASANTE if lum else None)
    rend(os.path.join(OUT, f"{prefixe}_{nom}{suffixe}.png"))

# --- animations --------------------------------------------------------------
# Chaque image est enregistrée comme image clé (caméra, lampes) : la scène .blend se rejoue dans
# Blender, et le calcul passe par le rendu d'animation de Blender, qui garde la scène en mémoire
# d'une image à l'autre (« Persistent Data ») au lieu de tout recharger.


def image_cle(i):
    for o in (cam, *LAMPES):
        o.keyframe_insert("location", frame=i)
        o.keyframe_insert("rotation_euler", frame=i)
    for L in LAMPES:
        L.data.keyframe_insert("energy", frame=i)
    cam_d.dof.keyframe_insert("focus_distance", frame=i)


def ffmpeg():
    """Chemin de ffmpeg (PATH, ou installation winget hors PATH), ou None."""
    import shutil, glob
    p = shutil.which("ffmpeg")
    if p:
        return p
    g = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe"))
    return sorted(g)[-1] if g else None


if a.anim != "aucune":
    if a.anim == "vitrine":
        N = max(2, round(a.duree * a.ips))
        if a.vue_video not in VUES:
            sys.exit(f"--vue_video {a.vue_video} : vues possibles : {', '.join(VUES)}")
        dossier = os.path.join(OUT, f"video_{prefixe}{suffixe}_{H_}p{a.ips}")
        pos, lum = VUES[a.vue_video]
        c, cl = place(pos, lum, NRJ_RASANTE if lum else None)
        P0 = cam.location - c                            # caméra par rapport au point visé
        f_ = -P0.normalized()
        haut = (HAUT - HAUT.dot(f_) * f_).normalized()   # axe vertical de l'image
        droite = f_.cross(haut)
        K0 = cle.location - c                            # lampe principale par rapport au point visé
        A = math.radians(a.amplitude)
    else:
        N = a.images
        dossier = os.path.join(OUT, f"anim_{a.anim}_{a.materiau}")
    os.makedirs(dossier, exist_ok=True)
    for i in range(N):
        t = 2 * math.pi * i / N  # boucle parfaite
        if a.anim == "vitrine":
            # caméra : balayage de ±amplitude autour de l'axe vertical de l'image, et légère
            # montée-descente deux fois plus rapide (trajectoire en huit, on voit le relief) ;
            # lampe principale : un tour complet autour du masque, à sa hauteur (les reflets
            # glissent sur les facettes) ; contre-jour et débouchage fixes
            R = Matrix.Rotation(0.22 * A * math.sin(2 * t), 3, droite) @ Matrix.Rotation(A * math.sin(t), 3, haut)
            cam.location = c + R @ P0
            regarde(cam, c, HAUT)
            cle.location = c + Matrix.Rotation(-t, 3, 'Z') @ K0
            regarde(cle, cl)
        elif a.anim == "balancier":
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
        image_cle(i)
    sc.frame_start, sc.frame_end = 0, N - 1
    sc.render.fps = a.ips if a.anim == "vitrine" else 24
    sc.render.use_persistent_data = True
    sc.render.use_overwrite = False     # reprise : les images déjà écrites sont sautées
    sc.render.use_placeholder = False   # (une image interrompue n'est jamais écrite)
    sc.render.filepath = os.path.join(dossier, "####")
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(animation=True)
    faites = sum(os.path.exists(os.path.join(dossier, f"{i:04d}.png")) for i in range(N))
    print(f"{faites}/{N} images dans {dossier}", flush=True)
    if a.anim == "vitrine" and a.mp4 == "oui" and faites == N:
        exe = ffmpeg()
        if exe:
            import subprocess
            mp4 = dossier + ".mp4"
            subprocess.run([exe, "-y", "-loglevel", "error", "-framerate", str(a.ips),
                            "-i", os.path.join(dossier, "%04d.png"), "-c:v", "libx264", "-preset", "slow",
                            "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], check=True)
            print("vidéo", mp4, flush=True)
        else:
            print("ffmpeg introuvable : assembler les PNG à la main (voir RENDU.md)", flush=True)

if a.blend:
    # caméra et lampes sur la première vue (sinon la caméra resterait à l'origine)
    pos, lum = VUES[vues[0] if vues else next(iter(VUES))]
    place(pos, lum, NRJ_RASANTE if lum else None)
    sc.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=chemin(a.blend))
