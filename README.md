# Minecraft Motion Graphics

High-quality Minecraft diorama rendered with **Blender Cycles (CPU)** and assembled with **ffmpeg**.

## What this repo does

- `scripts/make_minecraft_scene.py` — builds a cinematic Minecraft diorama (stone/dirt/grass island, tree, ore cluster, water pool, lava, glass pillar, glowstone) with PBR-ish Principled BSDF materials and a 2.4 s camera orbit.
- `.github/workflows/render.yml` — GitHub Actions workflow that installs Blender + ffmpeg on `ubuntu-latest`, renders 72 frames at 1280×720, encodes to H.264 MP4, and uploads frames + video as workflow artifacts.

## Materials (PBR-inspired)

Each Minecraft block uses a Principled BSDF with tuned channels:

| Block | Roughness | Metallic | Emission | Notes |
|-------|-----------|----------|----------|-------|
| Grass top / side | 0.85 | 0 | 0 | matte organic |
| Dirt | 1.00 | 0 | 0 | rough soil |
| Stone | 0.75 | 0 | 0 | slightly polished rock |
| Coal ore | 0.90 | 0.25 | 0 | speckled mineral |
| Iron ore | 0.45 | 0.85 | 0 | reflective metal |
| Gold ore | 0.35 | 1.00 | 0 | bright metal |
| Diamond ore | 0.25 | 0.80 | 0.6 | emissive gem |
| Wood | 0.85 | 0 | 0 | matte timber |
| Leaves | 0.90 | 0 | 0 | slight transparency |
| Sand | 0.90 | 0 | 0 | granular |
| Water | 0.15 | 0 | 0 | transmission, IOR 1.33 |
| Glass | 0.02 | 0 | 0 | transmission, IOR 1.45 |
| Lava | 0.40 | 0 | 3.5 | strong emission |
| Glowstone | 0.50 | 0 | 2.0 | emissive |

These maps mirror Minecraft Bedrock PBR channels (metalness, roughness, emission, normal, height, subsurface scattering).

## Local render

```bash
# needs Blender 4.x + ffmpeg + xvfb
xvfb-run -a blender -b --python scripts/make_minecraft_scene.py
```

Frames write to `output/frames/minecraft_####.png`. Encode:

```bash
ffmpeg -y -framerate 30 -i output/frames/minecraft_%04d.png \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  output/video/minecraft.mp4
```

## GitHub Actions

Push to `main` (or run manually via the Actions tab) to render on GitHub-hosted runners and download the artifacts from the workflow run summary.

## Notes

- No GPU is assumed anywhere — this runs on CPU (GitHub Actions standard runners and this local box are both CPU-only).
- Blender 4.0.x on this build lacks OpenImageDenoiser, so denoising is disabled in the scene.
