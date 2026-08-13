from pathlib import Path
import os
from PIL import Image


FOLDER = Path(
    os.environ.get(
        "VF2_RESIZE_FOLDER",
        "outputs/VF2-Mobile-Furniture-With-Island-Events-B15-Fire-Button-Mini-Tables-MP3/Images/Furniture",
    )
)
NAMES = (
    "FoosballTableStd.png",
    "PoolTableStd.png",
    "PinballStd.png",
    "SlotMachineBlkStd.png",
    "PachinkoStd.png",
    "Trampoline.png",
)


for name in NAMES:
    path = FOLDER / name
    source = Image.open(path).convert("RGBA")
    scaled = source.resize(
        (round(source.width * 0.8), round(source.height * 0.8)),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    canvas.alpha_composite(
        scaled,
        ((source.width - scaled.width) // 2, (source.height - scaled.height) // 2),
    )
    canvas.save(path)
    print(f"{name}: canvas={source.size}, graphic={scaled.size}")
