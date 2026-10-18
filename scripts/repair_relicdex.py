#!/usr/bin/env python3
"""RelicDex source-of-truth repair: PRU evolutions, sprite provenance, uniform previews.
Reads the pinned playable PRU source; never edits original sprite donors.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import re
import shutil

from PIL import Image

PRU_SHA = "2f7122d692f676ac14665e43f7d0f5477d7ad59e"
NOTION_CANON = "https://app.notion.com/p/3fb4939d431681afa46fdeb97cf8c79b"
NOTION_SPRITES = "https://app.notion.com/p/3f14939d43168107a9accfa462bf0122"
TARGET_SIZE = 96
TARGET_OCCUPIED = 76

def parse_verified_stone_evolutions(pru):
    """Only use exact active SpeciesInfo records and explicit Lv45 conditions."""
    resolved = {}
    src = pru / "src/data/pokemon/species_info"
    record = re.compile(r"(?m)^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{")
    evo = re.compile(
        r"EVO_ITEM\s*,\s*ITEM_ANCIENT_STONE\s*,\s*(SPECIES_[A-Z0-9_]+)\s*,\s*"
        r"CONDITIONS\s*\(\s*\{\s*IF_MIN_LEVEL\s*,\s*45\s*\}\s*\)"
    )
    for file in sorted(src.glob("*.h")):
        body = file.read_text(encoding="utf-8")
        matches = list(record.finditer(body))
        for i, match in enumerate(matches):
            section = body[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(body)]
            for target in evo.findall(section):
                key = match.group(1)
                if key in resolved and resolved[key] != target:
                    raise ValueError(f"Conflicting Ancient Stone routes: {key}")
                resolved[key] = target
    if len(resolved) < 25:
        raise ValueError(f"Expected at least 25 source-verified Ancient Stone routes; found {len(resolved)}")
    return resolved

def remove_background(image):
    """Flood-remove a solid outer matte; never replace internal sprite colours."""
    image = image.convert("RGBA")
    w, h = image.size
    rgba = image.load()
    opaque_corners = [rgba[x,y] for x,y in ((0,0),(w-1,0),(0,h-1),(w-1,h-1)) if rgba[x,y][3] >= 240]
    if len(opaque_corners) < 3:
        return image
    colour = max(set(opaque_corners), key=opaque_corners.count)
    if opaque_corners.count(colour) < 3:
        return image
    work = image.copy()
    pix = work.load()
    seen=set()
    queue = deque([(x,y) for x in range(w) for y in (0,h-1)] + [(x,y) for y in range(h) for x in (0,w-1)])
    while queue:
        x,y=queue.popleft()
        if not (0<=x<w and 0<=y<h) or (x,y) in seen:
            continue
        seen.add((x,y))
        if pix[x,y] != colour:
            continue
        pix[x,y] = (colour[0],colour[1],colour[2],0)
        queue.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    return work

def preview(src, dst):
    image = Image.open(src)
    if src.name == "anim_front.png" and image.height >= 2 * image.width:
        image = image.crop((0,0,image.width,image.width))
    image = remove_background(image)
    bbox=image.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"Blank image: {src}")
    region=image.crop(bbox)
    factor=min(TARGET_OCCUPIED / region.width, TARGET_OCCUPIED / region.height)
    size=(max(1,round(region.width*factor)),max(1,round(region.height*factor)))
    region=region.resize(size,Image.Resampling.NEAREST)
    canvas=Image.new("RGBA",(TARGET_SIZE,TARGET_SIZE),(0,0,0,0))
    canvas.alpha_composite(region,((TARGET_SIZE-size[0])//2,(TARGET_SIZE-size[1])//2))
    dst.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(dst,format="PNG",optimize=True)

def update_evolutions(mons, stone):
    by_constant={m["speciesConstant"]:m for m in mons if m.get("speciesConstant")}
    changed=[]
    for source,target in sorted(stone.items()):
        mon=by_constant.get(source)
        mon_target=by_constant.get(target)
        if mon is None or mon_target is None:
            continue  # Some inherited species do not belong to the strict PRU 444 whitelist
        old=mon.get("evolutions",[])
        preserved=[e for e in old if e.get("targetConstant") != target]
        record={"method":"Ancient Stone","requirement":"Level 45+","targetConstant":target,
                "verification":"PRU compiled SpeciesInfo","sourceCommit":PRU_SHA}
        mon["evolutions"]=preserved+[record]
        changed.append((mon["name"],mon_target["name"]))
    if ("Mightyena","Skulberus") not in changed:
        raise ValueError("Mightyena → Skulberus active Lv45 Ancient Stone source route missing")
    for m in mons:
        m["evolvesFrom"]=[]
    for source in mons:
        for route in source.get("evolutions",[]):
            target=by_constant.get(route.get("targetConstant"))
            if target is None: continue
            target["evolvesFrom"].append({
                "source":source["name"],"sourceNumber":source["number"],
                "method":route.get("method",""),"requirement":str(route.get("requirement","")),
                "verification":route.get("verification","donor draft / ROM QA pending")
            })
    return changed

def add_incoming_evo_display(site):
    script=site/"js/app.js"
    text=script.read_text(encoding="utf-8")
    original="if(m.evolutions?.length){for(const x of m.evolutions)evo.append(E('p','muted',"
    if original not in text and "evolvesFrom?.length" not in text:
        raise ValueError("RelicDex JS evolution rendering changed; refusing a blind patch")
    if "evolvesFrom?.length" not in text:
        extra="""if(m.evolvesFrom?.length){for(const x of m.evolvesFrom)evo.append(E('p','muted',`Evolves from ${x.source} (#${String(x.sourceNumber).padStart(3,'0')}) — ${x.method}: ${x.requirement}`))} """
        text=text.replace(original,extra+original,1)
        script.write_text(text,encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site",type=Path,required=True)
    ap.add_argument("--pru",type=Path,required=True)
    args=ap.parse_args()
    site,pru=args.site,args.pru
    path=site/"data/pokemon.json"
    mons=json.loads(path.read_text(encoding="utf-8"))
    assert len(mons)==444
    byname={m["name"].lower():m for m in mons}
    assert len(byname)==444

    # The previously bundled Noxichu came from the older PRL donor. Use the
    # exact art shipped in the verified 18 Oct PRU compiled source.
    nox=byname["noxichu"]
    oldfront=site/nox["sprite"]["front"]
    sourcefront=pru/"graphics/pokemon/noxichu/front.png"
    assert sourcefront.is_file() and oldfront.is_file()
    shutil.copyfile(sourcefront,oldfront)
    nox["spriteProvenance"]=f"Exact front sprite from verified PRU source {PRU_SHA}"
    nox["pru_verified_sprite_source"]=nox["spriteProvenance"]
    for file in ("back.png",):
        src=pru/"graphics/pokemon/noxichu"/file
        if src.is_file() and nox["sprite"].get("back"):
            shutil.copyfile(src,site/nox["sprite"]["back"])

    changes=update_evolutions(mons,parse_verified_stone_evolutions(pru))
    add_incoming_evo_display(site)
    # Force the installable/offline site to replace the old Beta 3 shell cache.
    # A new service worker cache key ensures users do not keep seeing old art.
    sw=site/"sw.js"
    old_sw=sw.read_text(encoding="utf-8")
    new_sw=re.sub(r"const KEY='[^']+'", "const KEY='relicdex-pru-20261018-v6-sevii-legends'", old_sw, count=1)
    if old_sw == new_sw:
        raise ValueError("Unable to version the RelicDex service worker")
    sw.write_text(new_sw,encoding="utf-8")
    processed=0
    for mon in mons:
        sprite=mon.get("sprite",{})
        original=sprite.copy()
        mon["spriteOriginal"]=original
        for kind in ("front","shiny","back"):
            file=sprite.get(kind)
            if not file or file.startswith(("https://","http://")):
                continue
            src=site/file
            if not src.is_file():
                raise ValueError(f"Referenced original sprite not bundled: {mon['name']} {file}")
            dst=Path("assets/previews")/(mon["id"]+"_"+kind+".png")
            preview(src,site/dst)
            sprite[kind]=dst.as_posix()
            processed+=1
    assert processed >= 430, f"Only {processed} sprites normalized"
    path.write_text(json.dumps(mons,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (site/"data"/"sprite_evolution_audit.json").write_text(json.dumps({
        "date":"2026-10-18","sourceCommit":PRU_SHA,"sources":[NOTION_CANON,NOTION_SPRITES],
        "canonicalEntries":len(mons),"normalizedSprites":processed,
        "stoneEvolutions":[{"from":a,"to":b} for a,b in changes],
        "noxichuSprite":"verified PRU compiled source (not older PRL pin)",
        "previewNormalization":"96x96 alpha transparent, 76px content bounding box; original sprite paths retained in spriteOriginal",
        "remaining":"Individual encounter validation and gameplay testing are distinct tasks"
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"PASS: {len(mons)} entries, {processed} normalized images, {len(changes)} Lv45 Ancient Stone chains")
    print("PASS: Noxichu exact compiled PRU art and incoming Skulberus evolution")

if __name__=="__main__":
    main()
