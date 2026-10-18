#!/usr/bin/env python3
"""Use exact Radical Red Sevii artwork and existing approved PRL legendary files.

Website-art synchronization only; no PRU ROM, source, sprite metadata or original
donor files are altered. Keep custom species/form count fixed at 444.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from shutil import copyfile
from PIL import Image

RADICAL_RED_REPO = "JwowSquared/Radical-Red-Pokedex"
RADICAL_RED_COMMIT = "488a0918194d567b5f7b02c396118d51fb9c81ce"
PRL_COMMIT = "6ee9b984521ac6f2beaf995f771a726379e55c88"
RADICAL_RED_ART_CREDITS = [
    "Radical Red sprite contributors: Scipio, Diezombie4114, "
    "Gladiator Kraken, pissuinhaaleatoria (RR 4.x credits)."
]
SEVII = {"Noibat (Sevii)":866, "Noivern (Sevii)":867}
LOCKED_LEGENDS = {
    "Raikou":"raikou", "Entei":"entei", "Suicune":"suicune",
    "Lugia":"lugia", "Ho-Oh":"ho_oh", "Celebi":"celebi"
}
SOURCE_URL_RR = f"https://github.com/{RADICAL_RED_REPO}/tree/{RADICAL_RED_COMMIT}/graphics/species"
SOURCE_URL_PRL = (
    "https://github.com/jamesthoward2112-tech/Pokemon-Relic-Legacy/"
    f"tree/{PRL_COMMIT}/graphics/pokemon"
)

def palette(path):
    ls=path.read_text(encoding="utf-8").strip().splitlines()
    assert ls[0]=="JASC-PAL" and int(ls[2])==16, f"Unexpected GBA palette: {path}"
    return [tuple(map(int,line.split())) for line in ls[3:19]]

def load_front(path):
    image=Image.open(path).convert("RGBA")
    if image.height>=2*image.width:
        image=image.crop((0,0,image.width,image.width))
    assert image.size==(64,64), f"Unexpected front frame size {path}: {image.size}"
    return image

def image_from_palette(image, base_palette, target_palette):
    # Use the approved indexed RGB palettes, not speculative recolouring.
    rgba=image.convert("RGBA")
    out=Image.new("RGBA",rgba.size,(0,0,0,0))
    pixels=[]
    unmatched=set()
    for col in rgba.getdata():
        if col[3]==0 or col[:3]==base_palette[0]:
            pixels.append((0,0,0,0))
        else:
            indices=[i for i,colour in enumerate(base_palette) if colour==col[:3]]
            if not indices:
                unmatched.add(col[:3])
                pixels.append(col)
            else:
                i=indices[0]
                pixels.append((*target_palette[i],col[3]))
    if unmatched:
        raise ValueError(f"Not a verified indexed normal/shiny palette pair: {len(unmatched)} colours {sorted(unmatched)[:5]}")
    out.putdata(pixels)
    return out

def copy_sprite(src,dst):
    assert src.is_file(), f"Missing authoritative sprite {src}"
    with Image.open(src) as im:
        assert im.width==64 and im.height==64, f"Unexpected RR sprite size {src}: {im.size}"
    dst.parent.mkdir(parents=True,exist_ok=True)
    copyfile(src,dst)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site",type=Path,required=True)
    ap.add_argument("--rr",type=Path,required=True)
    ap.add_argument("--prl",type=Path,required=True)
    args=ap.parse_args()
    site=args.site
    data=site/"data/pokemon.json"
    mons=json.loads(data.read_text(encoding="utf-8"))
    assert len(mons)==444
    names={m["name"]:m for m in mons}
    assert len(names)==444
    meta=[]
    # Exact Radical Red 4.x indexed Seviian front/back/shiny art.
    for name,sid in SEVII.items():
        m=names[name]
        assert m["number"] in (418,419) and m["types"]==["Rock","Ghost"]
        base=Path("assets/sprites/radical_red_sevii")/m["id"]
        for kind,folder in (("front","front"),("back","back"),
                            ("shiny","front shiny"),("shiny_back","back shiny")):
            src=args.rr/"graphics/species"/folder/f"{sid}.png"
            target=base/(kind+".png")
            copy_sprite(src,site/target)
            if kind=="shiny_back":
                m["spriteBackShiny"]=target.as_posix()
            else:
                m.setdefault("sprite",{})[kind]=target.as_posix()
        m["spriteProvenance"]=(
            f"Actual Radical Red Seviian Rock/Ghost art, form index {sid}; "
            f"{RADICAL_RED_REPO} at {RADICAL_RED_COMMIT}."
        )
        m["spriteNote"]=(
            "Seviian front/back and original shiny artwork verified for RelicDex; "
            "the independent PRU engine species/form implementation is still pending."
        )
        m["sourceStatus"]="SITE ART VERIFIED · PRU ENGINE QA PENDING"
        meta.append({"species":name,"number":m["number"],"status":"verified website-only",
                     "source":SOURCE_URL_RR,"assetId":sid,"artistCredit":RADICAL_RED_ART_CREDITS})
    # Prior approved PRL battle sprites for Relics legends: never use a speculative
    # Mega/Primal design or overwrite already approved P-series birds/Mewtwo.
    for name,folder in LOCKED_LEGENDS.items():
        m=names[name]
        srcdir=args.prl/"graphics/pokemon"/folder
        target=Path("assets/sprites/approved_prl_legendary")/folder
        normal=palette(srcdir/"normal.pal")
        shiny=palette(srcdir/"shiny.pal")
        front_src=srcdir/"anim_front.png"
        if not front_src.is_file():
            front_src=srcdir/"front.png"
        front=load_front(front_src)
        (site/target).mkdir(parents=True,exist_ok=True)
        front_path=target/"front.png"
        front.save(site/front_path)
        back_src=srcdir/"back.png"
        with Image.open(back_src) as im:
            back=im.convert("RGBA")
            assert back.size==(64,64), f"Invalid approved back sprite {back_src}"
        back_path=target/"back.png"
        back.save(site/back_path)
        shiny_path=target/"shiny.png"
        image_from_palette(front,normal,shiny).save(site/shiny_path)
        m.setdefault("sprite",{}).update({
            "front":front_path.as_posix(),
            "back":back_path.as_posix(),
            "shiny":shiny_path.as_posix()
        })
        icon=srcdir/"icon.png"
        if icon.is_file():
            icon_path=target/"icon.png"
            copyfile(icon,site/icon_path)
            m["sprite"]["icon"]=icon_path.as_posix()
        m["spriteProvenance"]=(
            f"Protected PRL/PJR source selection: {folder}; authentic "
            f"front/back/icon and corresponding normal/shiny JASC palettes "
            f"from PRL {PRL_COMMIT}."
        )
        m["spriteNote"]="Previously used vanilla PokéSprite card art; now uses pinned approved PRL artwork."
        meta.append({"species":name,"number":m["number"],"status":"approved PRL visual",
                     "source":SOURCE_URL_PRL+"/"+folder,
                     "preservedIdentity":True})
    # Explicit alternative *form*, not a new 445th species or main Ho-Oh replacement.
    hooh=names["Ho-Oh"]
    relicsrc=args.prl/"graphics/pokemon/ho_oh_relic"
    assert (relicsrc/"front.png").is_file()
    rv=Path("assets/sprites/approved_prl_legendary/ho_oh_relic")
    (site/rv).mkdir(parents=True,exist_ok=True)
    for file in ("front.png","back.png"):
        if (relicsrc/file).is_file():
            copyfile(relicsrc/file,site/rv/file)
    hooh.setdefault("approvedVisualVariants",[])
    if not any(v.get("label")=="Relic Ho-Oh" for v in hooh["approvedVisualVariants"]):
        hooh["approvedVisualVariants"].append({
            "label":"Relic Ho-Oh",
            "sprite":{"front":(rv/"front.png").as_posix(),
                      "back":(rv/"back.png").as_posix()},
            "description":"Existing approved PRL story-specific variant; same Pokédex species"
        })
    # Note the distinction: visual candidate ≠ automatically approved global swap.
    for name in ("Rayquaza","Groudon","Kyogre","Latias","Latios","Jirachi"):
        m=names[name]
        m["legendaryArtworkDecision"]="Distinct Mega/Primal/Bond artwork is a Notion candidate awaiting explicit sprite approval."
    (site/"data/artwork_import_audit.json").write_text(json.dumps({
        "rosterCount":len(mons),"radicalRedCommit":RADICAL_RED_COMMIT,
        "approvedPrlCommit":PRL_COMMIT,"applied":meta,
        "protectedExisting":["Articuno","Zapdos","Moltres","Mewtwo","Deoxys"],
        "candidatesNotReplaced":["Rayquaza","Groudon","Kyogre","Latias","Latios","Jirachi"],
        "credits":RADICAL_RED_ART_CREDITS,
        "scope":"RelicDex website art only; PRU game mechanics unchanged"
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    data.write_text(json.dumps(mons,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    assert len(mons)==444 and all(m["sprite"].get("front") for m in (names["Noibat (Sevii)"],names["Noivern (Sevii)"]))
    print(f"PASS: {len(meta)} verified artwork replacements, native RR forms 866/867, 444 species unchanged")
    print("PASS: protected legendary birds and prior Mewtwo/Deoxys art preserved")
    print("QA: PRU Seviian mechanics and six additional legendary candidate choices remain open.")

if __name__=="__main__":
    main()
