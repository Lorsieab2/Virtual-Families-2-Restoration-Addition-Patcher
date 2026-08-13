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
    # Player-supplied complete pile art; unlike the cropped eight-frame strip,
    # this source contains the full visible pile without a clipped edge.
    return load("sockPileStrip_06.png")


def single_washer() -> Image.Image:
    sheet = load("WasherStd.png")
    # WasherStd is a two-cell horizontal sheet.  The No Sock Pile icon is one
    # washer, not the complete two-washer furniture strip.
    frame_width = sheet.width // 2
    return sheet.crop((0, 0, frame_width, sheet.height))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        "cheat_fill_house_messes.png": load("GarbageBags.png"),
        "cheat_clean_house.png": load("MaidServices_icon.png"),
        "cheat_fill_yard_weeds.png": weed_icon(),
        "cheat_clean_garden.png": load("GardeningServices_icon.png"),
        "cheat_max_sock_pile.png": largest_sock_pile(),
        "cheat_no_sock_pile.png": single_washer(),
        "cheat_marriage_email.png": load("loveemail.png"),
        "cheat_next_babies_male.png": load("Icon_Baby2.png"),
        "cheat_next_babies_female.png": load("Icon_Baby1.png"),
        "cheat_force_pregnancy.png": load("icon_BabyCrib.png"),
        "cheat_fix_malfunctions.png": load("Icon_Resort_Improvement.png"),
        "cheat_trophy_gold2x.png": load("trophy_gold2x.png"),
        "cheat_next_pregnancy_singleton.png": load("Prop_Baby_Temp.png"),
        "cheat_next_pregnancy_twins.png": load("twins.png"),
        "cheat_next_pregnancy_triplets.png": load("triplets.png"),
    }
    for filename, image in sources.items():
        contain(image).save(OUT / filename, optimize=True)


if __name__ == "__main__":
    main()
