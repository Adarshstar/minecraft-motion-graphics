#!/usr/bin/env python3
"""
render_remaining.py — Continue rendering frames 34-72 of the Minecraft scene
by loading the saved blend. Avoids re-rendering the 33 frames already done.
"""
import bpy
import os

WORKSPACE = "/home/ubuntu/.openclaw/workspace/motion"
BLEND_OUT = os.path.join(WORKSPACE, "scenes", "minecraft_demo.blend")
FRAME_DIR = os.path.join(WORKSPACE, "output", "frames")

# Load the scene we already built (has camera animation keyed 1-72)
bpy.ops.wm.open_mainfile(filepath=BLEND_OUT)
scene = bpy.context.scene

# Ensure output path points at our frame dir
scene.render.filepath = os.path.join(FRAME_DIR, "minecraft_")
scene.render.image_settings.file_format = "PNG"

# Render only the remaining frames 34 -> 72
scene.frame_start = 34
scene.frame_end = 72
# this CPU build has no OpenImageDenoiser — disable denoising
for vl in scene.view_layers:
    vl.cycles.use_denoising = False

print(f"RENDER_REMAINING: frames {scene.frame_start}-{scene.frame_end}")
bpy.ops.render.render(animation=True)
print("RENDER_REMAINING_COMPLETE")
