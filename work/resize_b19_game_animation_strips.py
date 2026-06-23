import os
from pathlib import Path
from PIL import Image

ROOT = Path(r"C:/Users/Owner/Documents/Codex/2026-06-13/files-mentioned-by-the-user-virtual")
SOURCE = Path(r"C:/Users/Owner/Downloads/Virtual Families 2 - Copy Official/originalimages")
TARGET = Path(os.environ.get(
    "VF2_BUILD_IMAGES",
    ROOT / "outputs" / "VF2-Mobile-Furniture-With-Island-Events-B19-Invisible-Kids-Table-Mini-Game-Tables" / "Images",
))

STRIPS = {
    "PachinkoAnimStripSE.png": 12,
    "PachinkoAnimStripSW.png": 12,
    "SlotMachineAnimStripSE.png": 10,
    "SlotMachineAnimStripSW.png": 10,
    "PinballAnimStripSE.png": 12,
    "PinballAnimStripSW.png": 12,
}

for filename, frames in STRIPS.items():
    source_path = SOURCE / filename
    with Image.open(source_path) as original:
        image = original.convert("RGBA")
    cell_width = image.width // frames
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    separated = TARGET / "SeparatedAnimationSprites" / source_path.stem
    separated.mkdir(parents=True, exist_ok=True)

    for index in range(frames):
        frame = image.crop((index * cell_width, 0, (index + 1) * cell_width, image.height))
        reduced = frame.resize((round(cell_width * 0.8), round(image.height * 0.8)), Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (cell_width, image.height), (0, 0, 0, 0))
        # Furniture effects stand on the original cell baseline. Centering a
        # reduced frame moves it upward and makes the animation float above
        # its cabinet; preserve the bottom edge instead.
        cell.alpha_composite(reduced, ((cell_width - reduced.width) // 2, image.height - reduced.height))
        result.alpha_composite(cell, (index * cell_width, 0))
        cell.save(separated / f"frame_{index + 1:02d}.png")

    result.save(TARGET / filename)
    print(f"{filename}: {frames} frames, {image.size[0]}x{image.size[1]} canvas retained")
