#!/usr/bin/env python3
"""Replace the remaining nine vanilla RelicDex legendary cards with exact PJR art.

The user explicitly chose the *current PJR species graphics* for legendary
Pokémon, not donor concept Mega/Primal trainer-only skins. Preserve all already
approved P-series birds, Mewtwo, Deoxys, Johto Relics, and Mew untouched.
Run after PRL and Radical Red imports, before uniform preview normalization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from PIL import Image

from port_seviian_and_approved_legends import (
    image_from_palette,
    load_front,
    palette,
)

PJR_REPO = "jamesthoward2112-tech/Pokemon-Johto-Relics"
PJR_SHA = "9e9ec181961efbbdba88055876dfa9b18fd0ae64"
PJR_BASE = (
    f"https://github.com/{PJR_REPO}/tree/{PJR_SHA}/graphics/pokemon"
)

# The nine legend entries still pointing to tiny vanilla menu icons in
# the verified 18 Oct live export. Do NOT replace any previously user-approved
# global P-bird, Johto Relic, Mewtwo X, BYOXYS/Deoxys, Mewsion, or other art.
PJR_LEGENDARY = {
    "Regirock": "regirock",
    "Regice": "regice",
    "Registeel": "registeel",
    "Latias": "latias",
    "Latios": "latios",
    "Kyogre": "kyogre",
    "Groudon": "groudon",
    "Rayquaza": "rayquaza",
    "Jirachi": "jirachi",
}
PROTECTED = (
    "Mew", "Articuno", "Zapdos", "Moltres", "Mewtwo", "Deoxys",
    "Raikou", "Entei", "Suicune", "Lugia", "Ho-Oh", "Celebi",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, type=Path)
    ap.add_argument("--pjr", required=True, type=Path)
    args = ap.parse_args()

    data_path = args.site / "data/pokemon.json"
    mons = json.loads(data_path.read_text(encoding="utf8"))
    assert len(mons) == 444
    names = {m["name"]: m for m in mons}
    assert len(names) == 444

    protected_before = {
        name: json.dumps(
            {
                "sprite": names[name].get("sprite"),
                "spriteProvenance": names[name].get("spriteProvenance"),
                "approvedVisualVariants": names[name].get("approvedVisualVariants"),
            },
            sort_keys=True,
        )
        for name in PROTECTED
    }

    audit = []
    for name, folder in PJR_LEGENDARY.items():
        mon = names[name]
        old_provenance = mon.get("spriteProvenance", "")
        if "PokéSprite" not in old_provenance and "Pokesprite" not in old_provenance:
            raise ValueError(f"Not overwriting a previously approved custom sprite for {name}: {old_provenance}")

        source = args.pjr / "graphics/pokemon" / folder
        target = args.site / "assets/sprites/pjr_legendary" / folder
        assert source.is_dir(), f"Missing PJR artwork folder: {source}"
        base_palette = palette(source / "normal.pal")
        shiny_palette = palette(source / "shiny.pal")
        front_file = source / "anim_front.png"
        if not front_file.is_file():
            front_file = source / "front.png"
        front = load_front(front_file)
        with Image.open(source / "back.png") as im:
            back = im.convert("RGBA")
        assert back.size == (64, 64), f"Unexpected back sprite dimensions {name}: {back.size}"

        # Keep the historical PJR pixel colours and approved indexed shiny
        # palette. If the file doesn't actually match its own JASC palette,
        # stop and audit instead of inventing or recolouring art.
        shiny = image_from_palette(front, base_palette, shiny_palette)
        target.mkdir(parents=True, exist_ok=True)
        front.save(target / "front.png")
        back.save(target / "back.png")
        shiny.save(target / "shiny.png")

        icon_source = source / "icon.png"
        icon_path = None
        if icon_source.is_file():
            with Image.open(icon_source) as im:
                assert im.width in (32, 64) and im.height in (32, 64), (
                    f"Unexpected party-icon dimensions for {name}: {im.size}"
                )
            shutil.copyfile(icon_source, target / "icon.png")
            icon_path = f"assets/sprites/pjr_legendary/{folder}/icon.png"

        paths = {
            "front": f"assets/sprites/pjr_legendary/{folder}/front.png",
            "back": f"assets/sprites/pjr_legendary/{folder}/back.png",
            "shiny": f"assets/sprites/pjr_legendary/{folder}/shiny.png",
        }
        if icon_path:
            paths["icon"] = icon_path
        mon.setdefault("sprite", {}).update(paths)
        mon["spriteProvenance"] = (
            f"Verified original PJR source Pokémon graphics, {folder}, "
            f"pinned commit {PJR_SHA}. No Mega/Primal skin substituted."
        )
        mon["spriteNote"] = (
            "PJR battle front/back, shiny palette and party icon; "
            "independent gameplay/form QA remains separate."
        )
        mon["legendaryArtworkDecision"] = (
            "Approved user request: PJR original species artwork, "
            "not unapproved Mega/Primal concept artwork."
        )
        audit.append({
            "species": name,
            "number": mon["number"],
            "source": f"{PJR_BASE}/{folder}",
            "sourceCommit": PJR_SHA,
            "front": paths["front"],
            "back": paths["back"],
            "shiny": paths["shiny"],
            "icon": paths.get("icon"),
            "status": "PJR source art verified and installed on RelicDex",
        })

    for name, before in protected_before.items():
        after = json.dumps(
            {
                "sprite": names[name].get("sprite"),
                "spriteProvenance": names[name].get("spriteProvenance"),
                "approvedVisualVariants": names[name].get("approvedVisualVariants"),
            },
            sort_keys=True,
        )
        assert before == after, f"Forbidden change to approved artwork: {name}"

    data_path.write_text(json.dumps(mons, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (args.site / "data/pjr_legendary_art_audit.json").write_text(
        json.dumps(
            {
                "rosterCount": len(mons),
                "pjrReference": PJR_SHA,
                "applied": audit,
                "preserved": PROTECTED,
                "policy": (
                    "Match PJR canonical species visual; never turn a trainer-only "
                    "Mega or Primal graphic into an ordinary global Pokémon form."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf8",
    )
    assert len(audit) == 9
    print(
        f"PASS: {len(audit)} source-pinned PJR legendary front/back/shiny/icon sets; "
        "Mew and approved Johto/Kanto/Deoxys assets unchanged"
    )


if __name__ == "__main__":
    main()
