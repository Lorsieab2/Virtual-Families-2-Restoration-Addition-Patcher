import os
from pathlib import Path
from PIL import Image


SOURCE = Path(r"C:/Users/Owner/Downloads/Virtual Families 2 - Copy Official/originalimages/Furniture")
TARGET = Path(os.environ.get(
    "VF2_BUILD_FURNITURE",
    "outputs/VF2-Mobile-Furniture-With-Island-Events-B19-Invisible-Kids-Table-Mini-Game-Tables/Images/Furniture",
))
NAMES = (
    "SlotMachineBlkStd.png",
    "TreadmillStd.png",
    "PachinkoStd.png",
    "PoolTableStd.png",
    "FoosballTableStd.png",
    "PinballStd.png",
)


for name in NAMES:
    source = Image.open(SOURCE / name).convert("RGBA")
    scaled = source.resize(
        (round(source.width * 0.8), round(source.height * 0.8)),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    canvas.alpha_composite(
        scaled,
        ((source.width - scaled.width) // 2, (source.height - scaled.height) // 2),
    )
    canvas.save(TARGET / name)
    print(f"{name}: canvas={source.size}, graphic={scaled.size}")
