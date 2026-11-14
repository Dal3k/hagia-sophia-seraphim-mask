# Rendus haute définition (Blender / Cycles)

Le script `rendu/rendu_blender.py` construit la scène complète : il importe le STL, crée la
matière, le fond, trois lampes et la caméra, puis calcule les images. Il tourne tel quel sur
Mac (GPU Metal), sur Windows ou sous Linux. Avec une carte NVIDIA RTX, il prend OptiX tout seul.

## 1. Installation sur un PC Windows (une seule fois)

Ouvrir **PowerShell** et lancer :

```powershell
winget install --id Git.Git -e
winget install --id BlenderFoundation.Blender -e
winget install --id Gyan.FFmpeg -e
```

FFmpeg ne sert qu'à assembler les animations en vidéo. Il faut aussi un pilote NVIDIA récent
(GeForce Experience ou nvidia.com) pour qu'OptiX soit disponible. Fermer puis rouvrir
PowerShell après l'installation.

## 2. Récupérer le dépôt

```powershell
cd $HOME\Documents
git clone https://github.com/Dal3k/hagia-sophia-seraphim-mask.git
cd hagia-sophia-seraphim-mask
```

Pour récupérer plus tard les mises à jour : `git pull` dans ce dossier.

## 3. Trouver Blender

Blender n'est pas dans le PATH sous Windows. Cette ligne retrouve l'exécutable, à relancer
dans chaque nouvelle fenêtre PowerShell :

```powershell
$blender = (Get-ChildItem "C:\Program Files\Blender Foundation\*\blender.exe" | Select-Object -Last 1).FullName
```

## 4. Lancer un rendu

Toutes les commandes se lancent depuis le dossier du dépôt. La première ligne affichée
indique le GPU utilisé (`Périphérique de rendu : OPTIX : NVIDIA GeForce RTX 4080`).

```powershell
# 4 vues en 4K carré (3840 × 3840), qualité finale
& $blender -b -P rendu/rendu_blender.py -- --res 3840 --samples 512

# une seule vue, 8K, format portrait 4:5
& $blender -b -P rendu/rendu_blender.py -- --vues trois_quarts --res 7680 --format portrait --samples 1024

# 16:9 pour fond d'écran ou vidéo
& $blender -b -P rendu/rendu_blender.py -- --vues rasante --res 3840 --format paysage --samples 512
```

Les images sont écrites dans `rendu/images/`. Elles portent le suffixe `_<matière>_<fond>`
quand la matière ou le fond ne sont pas ceux par défaut. Sur Mac, remplacer `& $blender`
par `blender`.

Durée indicative : 4 vues à 1600 px et 128 échantillons prennent ~2 min sur un M1 Pro.
Une RTX 4080 sous OptiX va environ 5 à 10 fois plus vite, soit 1 à 3 min par vue en 4K à
512 échantillons.

### Options

| option | valeurs | effet |
|---|---|---|
| `--vues` | `face,trois_quarts,rasante,profil`, `toutes`, `aucune` | vues fixes à calculer |
| `--res` | 1600, 3840 (4K), 7680 (8K)… | côté de référence en pixels |
| `--format` | `carre`, `portrait` (4:5), `paysage` (16:9) | le cadrage vertical reste le même |
| `--samples` | 128 essai, 512-1024 final | échantillons Cycles (bruit) |
| `--materiau` | `dore`, `or`, `bronze`, `vertdegris`, `zinc` | voir ci-dessous |
| `--fond` | `velours`, `blanc`, `transparent` | `transparent` = PNG détouré avec l'ombre portée |
| `--anim` | `aucune`, `balancier`, `lumiere` | animations, voir §5 |
| `--images` | 120 | nombre d'images de l'animation (24 par seconde) |
| `--stl` | `sortie_cintre/masque.stl` | `sortie/masque.stl` pour le polyèdre pur |
| `--gpu` | `auto`, `OPTIX`, `CUDA`, `METAL`, `CPU` | `auto` choisit le meilleur |
| `--blend` | `rendu/masque.blend` | enregistre la scène pour l'ouvrir dans Blender |

Matières :
- `dore` : dorure patinée, la matière par défaut, proche de l'exemplaire du musée.
- `or` : dorure neuve, très réfléchissante. Elle reflète le fond sombre, donc l'image est
  très contrastée.
- `bronze` : bronze brun avec patine sombre au fond des plis et métal frotté sur les crêtes.
  C'est l'aperçu de la future fonte.
- `vertdegris` : bronze ancien, avec du vert-de-gris logé dans les creux.
- `zinc` : zinc nu, la matière d'origine des Fossati sous la dorure.

## 5. Animations

```powershell
# la lumière rasante fait le tour du masque, caméra fixe (le plus spectaculaire sur les facettes)
& $blender -b -P rendu/rendu_blender.py -- --vues aucune --anim lumiere --res 2160 --samples 256 --images 240

# la caméra oscille de ±35°, lumières fixes
& $blender -b -P rendu/rendu_blender.py -- --vues aucune --anim balancier --res 2160 --samples 256
```

Les images partent dans `rendu/images/anim_<type>_<matière>/0000.png…`. L'animation boucle
parfaitement. Une image déjà calculée n'est pas refaite : on peut interrompre avec Ctrl+C
et relancer la même commande, le calcul reprend où il s'était arrêté.

Assemblage en vidéo MP4 :

```powershell
ffmpeg -framerate 24 -i rendu/images/anim_lumiere_dore/%04d.png -c:v libx264 -crf 16 -pix_fmt yuv420p masque_lumiere.mp4
```

## 6. Retoucher la scène à la main

```powershell
& $blender -b -P rendu/rendu_blender.py -- --vues aucune --blend rendu/masque.blend
& $blender rendu/masque.blend
```

Dans Blender, passer la vue 3D en mode **Rendu** (touche Z, puis « Rendered ») : sur une
4080, l'aperçu Cycles est quasi temps réel. On peut alors déplacer les lampes (`cle`,
`contre`, `debouche`) et la caméra, ou changer la matière. F12 lance le rendu final.

## 7. Autres idées de rendu (non faites)

- **In situ** : le masque posé sur un pendentif en mosaïque dorée, éclairé par le haut comme à
  Sainte-Sophie. Il faudrait modéliser le pendentif (triangle sphérique) et une texture de
  tesselles.
- **Porté** : le masque sur une tête, quand la version portable existera (tête neutre
  libre de droits ou scan 3D).
- **Planche technique** : vue de face orthographique sur fond blanc, avec les plis
  montagne/vallée en couleur, à côté du rendu.
- **Profondeur de champ macro** : objectif 100 mm à f/2.8 très près d'une crête, pour une
  image « matière ».
