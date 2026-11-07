#!/usr/bin/env python3
"""
make_minecraft_scene.py — Build a high-quality, cinematic Minecraft diorama
and render it locally with Blender Cycles (CPU).

Run:
    xvfb-run -a blender -b --python make_minecraft_scene.py

Output:
    motion/scenes/minecraft_demo.blend        (scene file)
    motion/output/frames/minecraft_####.png   (rendered frames)
    motion/output/video/minecraft.mp4         (after encode_frames.sh)

Design targets (realistic Minecraft):
  * Blocky voxel aesthetic with PBR materials (Principled BSDF)
  * PBR channels per material: base color, roughness, metallic, emission
  * Cinematic camera orbit around a small biome diorama
  * Sun key light + soft fill, subtle world mist for atmosphere
  * CPU-friendly: 720p, moderate sample count, low poly count
"""
import bpy
import math
import os
from mathutils import Vector

# Paths resolve relative to this script so the file works both locally
# and on GitHub Actions runners (no hardcoded /home/ubuntu paths).
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
SCENES_DIR = os.path.join(REPO_ROOT, "scenes")
FRAME_DIR = os.path.join(REPO_ROOT, "output", "frames")
VIDEO_OUT = os.path.join(REPO_ROOT, "output", "video", "minecraft.mp4")
BLEND_OUT = os.path.join(SCENES_DIR, "minecraft_demo.blend")
os.makedirs(SCENES_DIR, exist_ok=True)
os.makedirs(FRAME_DIR, exist_ok=True)
os.makedirs(os.path.dirname(VIDEO_OUT), exist_ok=True)
os.makedirs(FRAME_DIR, exist_ok=True)
os.makedirs(os.path.dirname(VIDEO_OUT), exist_ok=True)

# ---------------------------------------------------------------------------
# Render settings (quality tuned for CPU / no GPU on this box)
# ---------------------------------------------------------------------------
RES_X, RES_Y = 1280, 720
FPS = 30
FRAME_START = 1
FRAME_END = 72          # 2.4 s orbit loop
SAMPLES = 96            # Cycles samples — quality vs CPU time balance

# ---------------------------------------------------------------------------
# 1. Clear default scene
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
for block in bpy.data.meshes:
    bpy.data.meshes.remove(block)
for mat in bpy.data.materials:
    bpy.data.materials.remove(mat)

scene = bpy.context.scene
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END
scene.render.fps = FPS
scene.render.resolution_x = RES_X
scene.render.resolution_y = RES_Y
scene.render.resolution_percentage = 100
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = os.path.join(FRAME_DIR, "minecraft_")
# this CPU build has no OpenImageDenoiser — disable denoising
for vl in scene.view_layers:
    vl.cycles.use_denoising = False

# ---------------------------------------------------------------------------
# 2. Material library (PBR-ish via Principled BSDF)
# ---------------------------------------------------------------------------
def new_mat(name, base_color, roughness=0.8, metallic=0.0, emission=0.0,
            emission_color=(1, 1, 1), transmission=0.0, ior=1.45,
            alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Emission Strength"].default_value = emission
    bsdf.inputs["Emission Color"].default_value = (*emission_color, 1.0)
    # Blender 4.0 renamed 'Transmission' -> 'Transmission Weight'
    trans_key = "Transmission Weight" if "Transmission Weight" in bsdf.inputs else "Transmission"
    if trans_key in bsdf.inputs:
        bsdf.inputs[trans_key].default_value = transmission
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Alpha"].default_value = alpha
    # blend mode for transparency
    if transmission > 0 or alpha < 1:
        mat.blend_method = "BLEND"
        mat.shadow_method = "CLIP"
    return mat


MATS = {
    "grass_top":   new_mat("grass_top",   (0.22, 0.45, 0.18), roughness=0.85),
    "grass_side":  new_mat("grass_side",  (0.30, 0.55, 0.22), roughness=0.85),
    "dirt":        new_mat("dirt",        (0.42, 0.30, 0.20), roughness=1.0),
    "stone":       new_mat("stone",       (0.55, 0.55, 0.60), roughness=0.75),
    "coal_ore":    new_mat("coal_ore",    (0.12, 0.12, 0.12), roughness=0.9, metallic=0.25),
    "iron_ore":    new_mat("iron_ore",    (0.70, 0.75, 0.80), roughness=0.45, metallic=0.85),
    "gold_ore":    new_mat("gold_ore",    (0.95, 0.80, 0.20), roughness=0.35, metallic=1.0),
    "diamond_ore": new_mat("diamond_ore", (0.30, 0.95, 1.0), roughness=0.25, metallic=0.8, emission=0.6, emission_color=(0.4, 0.9, 1.0)),
    "wood":        new_mat("wood",        (0.55, 0.35, 0.22), roughness=0.85),
    "leaves":      new_mat("leaves",      (0.18, 0.55, 0.20), roughness=0.9, alpha=0.85),
    "sand":        new_mat("sand",        (0.90, 0.82, 0.55), roughness=0.9),
    "water":       new_mat("water",       (0.15, 0.45, 0.70), roughness=0.15, transmission=1.0, ior=1.33, alpha=0.7),
    "glass":       new_mat("glass",       (0.92, 0.95, 1.0), roughness=0.02, transmission=1.0, ior=1.45, alpha=0.92),
    "lava":        new_mat("lava",        (1.0, 0.35, 0.05), roughness=0.4, emission=3.5, emission_color=(1.0, 0.5, 0.1)),
    "glowstone":   new_mat("glowstone",   (1.0, 0.9, 0.5), roughness=0.5, emission=2.0),
}

def mat(name):
    return MATS[name]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def add_cube(location, size=1.0, material=None, name="cube"):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if material is not None:
        obj.data.materials.append(mat(material))
    return obj

# Minecraft blocks sit with their center at integer grid + 0.5 so faces align.
B = 1.0  # block size

# ---------------------------------------------------------------------------
# 3. Build the diorama
# ---------------------------------------------------------------------------
# Base platform: stone bottom, dirt mid, grass top — a small floating island
platform_size = 14  # blocks across
for x in range(-7, 7):
    for z in range(-7, 7):
        # stone base
        add_cube((x + 0.5, 0, z + 0.5), size=B, material="stone", name=f"stone_{x}_{z}")
        # dirt layer
        add_cube((x + 0.5, 1, z + 0.5), size=B, material="dirt", name=f"dirt_{x}_{z}")
        # grass top (with some exposed stone patches for variety)
        if (x + z) % 5 == 0:
            add_cube((x + 0.5, 2, z + 0.5), size=B, material="stone", name=f"grass_stone_{x}_{z}")
        else:
            add_cube((x + 0.5, 2, z + 0.5), size=B, material="grass_top", name=f"grass_{x}_{z}")
            # grass sides visible where there's a drop? keep simple

# Some sand patch on one corner
for x in range(-4, -1):
    for z in range(-4, -1):
        add_cube((x + 0.5, 3, z + 0.5), size=B, material="sand", name=f"sand_{x}_{z}")

# A tree: wood trunk + leaves canopy
trunk_x, trunk_z = 4, 4
for y in range(2, 8):
    add_cube((trunk_x + 0.5, y, trunk_z + 0.5), size=B, material="wood", name=f"wood_{trunk_x}_{y}_{trunk_z}")
# leaves canopy (3x3x3 minus corners)
for lx in (-1, 0, 1):
    for ly in (7, 8, 9):
        for lz in (-1, 0, 1):
            if abs(lx) + abs(lz) <= 1:  # cross shape leaves
                add_cube((trunk_x + lx + 0.5, ly, trunk_z + lz + 0.5), size=B, material="leaves", name=f"leaves_{lx}_{ly}_{lz}")

# Ore cluster embedded in a stone hill at one side
ore_positions = {
    (2, 3, -3): "coal_ore",
    (3, 3, -3): "iron_ore",
    (2, 3, -2): "gold_ore",
    (3, 3, -2): "diamond_ore",
    (1, 4, -3): "coal_ore",
    (4, 4, -3): "iron_ore",
}
for (ox, oy, oz), omat in ore_positions.items():
    add_cube((ox + 0.5, oy, oz + 0.5), size=B, material=omat, name=f"ore_{ox}_{oy}_{oz}")

# Small water pool
for wx in range(-2, 1):
    for wz in range(2, 5):
        add_cube((wx + 0.5, 2.01, wz + 0.5), size=B, material="water", name=f"water_{wx}_{wz}")

# A glass pillar + glowstone for magical accent
add_cube((-5 + 0.5, 3, -5 + 0.5), size=B, material="glass", name="glass_pillar")
add_cube((-5 + 0.5, 4, -5 + 0.5), size=B, material="glowstone", name="glowstone_top")

# A little lava pool
for lx in range(-6, -4):
    for lz in range(4, 6):
        add_cube((lx + 0.5, 2.01, lz + 0.5), size=B, material="lava", name=f"lava_{lx}_{lz}")

# ---------------------------------------------------------------------------
# 4. Lights — cinematic key + fill + rim
# ---------------------------------------------------------------------------
# Sun / key light
sun_data = bpy.data.lights.new("Sun", type="SUN")
sun_data.energy = 4.0
sun_data.color = (1.0, 0.95, 0.85)  # warm daylight
sun = bpy.data.objects.new("Sun", sun_data)
scene.collection.objects.link(sun)
sun.location = (10, -10, 12)
sun.rotation_euler = (math.radians(45), math.radians(-30), 0)

# Fill light (soft, cool)
fill_data = bpy.data.lights.new("Fill", type="AREA")
fill_data.energy = 600
fill_data.color = (0.7, 0.85, 1.0)
fill_data.size = 8
fill = bpy.data.objects.new("Fill", fill_data)
scene.collection.objects.link(fill)
fill.location = (-8, 6, 5)
fill.rotation_euler = (math.radians(20), math.radians(45), 0)

# Rim / back light (warm accent)
rim_data = bpy.data.lights.new("Rim", type="AREA")
rim_data.energy = 400
rim_data.color = (1.0, 0.5, 0.2)
rim_data.size = 4
rim = bpy.data.objects.new("Rim", rim_data)
scene.collection.objects.link(rim)
rim.location = (0, 10, 6)
rim.rotation_euler = (math.radians(-40), 0, 0)

# ---------------------------------------------------------------------------
# 5. World — subtle gradient + mist
# ---------------------------------------------------------------------------
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
bg = wnodes.get("Background")
bg.inputs["Color"].default_value = (0.12, 0.18, 0.28, 1.0)  # deep twilight blue
bg.inputs["Strength"].default_value = 0.6

# Mist settings (cheap atmospheric depth, no heavy volumetrics)
# Blender 4.0: mist is viewport-only; skip for render compatibility

# ---------------------------------------------------------------------------
# 6. Camera + orbit animation
# ---------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 35
cam_data.dof.use_dof = True
cam_data.dof.focus_distance = 12.0
cam_data.dof.aperture_fstop = 2.8
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

center = Vector((0.0, 2.0, 2.0))
radius = 13.0
height = 9.0

for frame in range(FRAME_START, FRAME_END + 1):
    t = (frame - FRAME_START) / (FRAME_END - FRAME_START)
    angle = t * 2 * math.pi  # one full orbit
    cam.location = (
        center.x + radius * math.cos(angle),
        center.y + radius * math.sin(angle),
        center.z + height,
    )
    cam.rotation_euler = (
        math.radians(35),
        0,
        angle + math.pi,  # look toward center
    )
    cam.keyframe_insert(data_path="location", frame=frame)
    cam.keyframe_insert(data_path="rotation_euler", frame=frame)

# ---------------------------------------------------------------------------
# 7. Save blend + render animation
# ---------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print("SAVED_BLEND:", BLEND_OUT)

# render animation
bpy.ops.render.render(animation=True)
print("RENDER_COMPLETE: frames written to", FRAME_DIR)
