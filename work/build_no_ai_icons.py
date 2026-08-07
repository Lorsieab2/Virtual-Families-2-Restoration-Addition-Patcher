"""Build the optional 90x90 non-AI Special Upgrade icon set."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "patcher_assets" / "optional_patches" / "no_ai_icons" / "source_art"
OUT = ROOT / "patcher_assets" / "optional_patches" / "no_ai_icons"


def contain(source: Image.Image, *, box: int = 84) -> Image.Image:
    source = source.convert("RGBA")
    source.thumbnail((box, box), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
    result.alpha_composite(source, ((90 - source.width) // 2, (90 - source.height) // 2))
    return result


def load(name: str) -> Image.Image:
    with Image.open(RAW / name) as source:
        return source.convert("RGBA")


def weed_icon() -> Image.Image:
    sheet = load("collectables_small.png")
    result = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    # Stock weed carrying values 0x7D-0x80 map to collectable frames 46-49.
    for index, frame in enumerate(range(46, 50)):
        x = (frame % 6) * 40
        y = (frame // 6) * 40
        sprite = sheet.crop((x, y, x + 40, y + 40))
        result.alpha_composite(sprite, ((index % 2) * 40, (index // 2) * 40))
    return result


def largest_sock_pile() -> Image.Image:
    strip = load("sockPileStrip.png")
    frame_width = strip.width // 8
    return strip.crop((strip.width - frame_width, 0, strip.width, strip.height))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        "cheat_fill_house_messes.png": load("GarbageBags.png"),
        "cheat_clean_house.png": load("MaidServices_icon.png"),
        "cheat_fill_yard_weeds.png": weed_icon(),
        "cheat_clean_garden.png": load("GardeningServices_icon.png"),
        "cheat_max_sock_pile.png": largest_sock_pile(),
        "cheat_no_sock_pile.png": load("WasherStd.png"),
        "cheat_marriage_email.png": load("loveemail.png"),
        "cheat_next_babies_male.png": load("Icon_Baby2.png"),
        "cheat_next_babies_female.png": load("Icon_Baby1.png"),
        "cheat_force_pregnancy.png": load("icon_BabyCrib.png"),
        "cheat_fix_malfunctions.png": load("Icon_Resort_Improvement.png"),
        "cheat_next_pregnancy_singleton.png": load("Prop_Baby_Temp.png"),
        "cheat_next_pregnancy_twins.png": load("twins.png"),
        "cheat_next_pregnancy_triplets.png": load("triplets.png"),
    }
    for filename, image in sources.items():
        contain(image).save(OUT / filename, optimize=True)


if __name__ == "__main__":
    main()
