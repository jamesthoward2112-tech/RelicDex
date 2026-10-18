#!/usr/bin/env python3
"""Apply source-verified 18 October 2026 PRU updates to bundled RelicDex Beta 3.

Never overwrite the approved artwork archive. Runs after the pinned donor sprites
have been bundled and before the GitHub Pages upload.
"""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path

SOURCE = "2f7122d692f676ac14665e43f7d0f5477d7ad59e"
SOURCE_URL = "https://github.com/jamesthoward2112-tech/Pokemon-Johto-Relics/pull/20"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1btIGLXVmJmUNLjeU-01-AEj8gYMnrjDxtAnSGQ23P0U/edit"

CHANGES = [
    ("444 species", "All 444 canonical entries have registered PRU species definitions. This does not yet mean 444 independently tracked Pokédex catches or 444 verified encounter paths.", "Build verified; gameplay QA outstanding"),
    ("Valkiri #319", "Previously Valkyvoir. Green is the normal palette and blue is the shiny palette, reusing approved PRL sprites without recolouring. Gardevoir evolves with an Ancient Stone at level 45.", "Build verified; in-game palette/evolution QA outstanding"),
    ("Sound moves", "Gardevoir gains Round at level 36 and Hyper Voice at 38. Valkiri can relearn both and gains Boomburst on evolution and at level 55.", "Build verified; in-game learn prompts QA outstanding"),
    ("Throat Spray", "Sold at Goldenrod Department Store 2F for ₽10,000; held-item effect integrated.", "Build verified; shop/effect QA outstanding"),
    ("Noxichu #032", "Pikachu's Moon Stone alternative evolution learns Bite immediately. Approved newer PRL battle artwork and party icon replace the older PJR sprites.", "Build verified; newest sprite QA outstanding"),
    ("Evolutions", "54 custom evolution targets checked, including 27 level-45 Ancient Stone routes and simplified Eeveelution methods. Exact outcomes still require saved-playthrough tests.", "Source/build verified; gameplay QA outstanding"),
    ("Johto rebalance", "202 trainer parties adjusted. Wild encounters cover 37 Johto areas and 63 day/night variants, including 145 slots using appropriate evolved species.", "Build verified; encounter QA outstanding"),
    ("Steevee & Neevee", "These are recurring human trainers, not species: Route 37 (replaces Ann & Anne, levels 30–32), Route 47 (38–40), Route 44 (44–47), and Kanto Route 3 (61–64). All four use the approved PRL custom Eevee Twins battle intro.", "Build verified; actual encounter/intro QA outstanding"),
    ("Johto Gym Leaders", "Eight upgraded first-encounter teams with signature Relics. £10,000, a TM and an item per leader; full team roster in the linked Google Sheet.", "Source/build verified; battle/reward QA outstanding"),
    ("Rocket and game systems", "Johto Jessie/James/Meowth positioning and custom intro; Chansey training; 92 named TMs and eight HMs.", "Build verified; save-file gameplay QA outstanding"),
    ("Future Kanto work", "Articuno, Zapdos and Moltres roaming in Kanto and properly evolved wild species on Kanto routes remain planned, not implemented.", "Planned only"),
]
GYMS = [
    ("Falkner","Hoothoot 11 · Natu 12 · Skarmet 12 · Pidgeotto 14","Roost","Sharp Beak"),
    ("Bugsy","Pineco 16 · Ledian 17 · Spinarak 16 · Scarabub 17 · Scyther 19","U-turn","Silver Powder"),
    ("Whitney","Clefairy 22 · Teddiursa 22 · Aipom 22 · Mootiny 23 · Miltank 24","Return","Eviolite"),
    ("Morty","Haunter 26 · Gemlin 25 · Omeon 27 · Misdreavus 26 · Gengar 28","Shadow Ball","Spell Tag"),
    ("Chuck","Hitmontop 33 · Primeape 33 · Heracross 34 · Champeon 34 · Poliwrath 36","Focus Punch","Black Belt"),
    ("Jasmine","Skarmory 37 · Guardeon 38 · Magneton 37 · Scizor 38 · Steelix 40","Iron Tail","Metal Coat"),
    ("Pryce","Dewgong 36 · Sneasel 36 · Jynx 37 · Jollibird 38 · Piloswine 40","Hail","Never-Melt Ice"),
    ("Clair","Dragonair 44 · Gyarados 45 · Altaria 45 · Mawyrm 46 · Dragonite 47 · Kingdra 48","Dragon Pulse","Dragon Fang"),
]

def label(mon: dict) -> str:
    for key in ("name", "displayName", "display_name"):
        v = mon.get(key)
        if isinstance(v, str):
            return v.casefold()
        if isinstance(v, dict):
            for k in ("en", "english"):
                if isinstance(v.get(k), str):
                    return v[k].casefold()
    return ""

def find(mons: list, name: str, number: int) -> dict:
    hits = [m for m in mons if isinstance(m,dict) and label(m) == name.casefold()]
    if hits:
        assert len(hits) == 1, (name,len(hits))
        return hits[0]
    matches = [m for m in mons if isinstance(m,dict) and any(str(m.get(k)) == str(number) for k in ("number","dexNumber","dex_number","dex","num","pruNumber"))]
    assert len(matches) == 1, f"Cannot safely identify {name} #{number}: {len(matches)} matches"
    return matches[0]

def rename_label(mon:dict, name:str) -> None:
    for k in ("name", "displayName", "display_name"):
        if isinstance(mon.get(k),str):
            mon[k] = name
        elif isinstance(mon.get(k),dict):
            for language in ("en","english"):
                if language in mon[k]: mon[k][language] = name
    if "name" not in mon:
        mon["name"] = name

def fix_evo(mon:dict) -> None:
    for k in ("evolution", "evolutionMethod", "evolution_method", "evolvesTo", "evolves_to"):
        v = mon.get(k)
        if isinstance(v,str) and ("VALKYVOIR" in v.upper() or "shiny" in v.lower()):
            mon[k] = "Level 45 + Ancient Stone → VALKIRI"
    mon["pru_verified_evolution"] = "Level 45 + Ancient Stone → Valkiri"

def swap_existing_art(mon:dict) -> list[str]:
    """Only exchange paths to existing local donor files, never redraw/recolour."""
    applied=[]
    for field in ("sprite", "sprites"):
        sprite=mon.get(field)
        if not isinstance(sprite,dict): continue
        for normal,shiny in (("normal","shiny"),("regular","shiny"),("front","shiny"),("front","shiny_front"),("front_normal","front_shiny"),("back","shiny_back"),("back_normal","back_shiny")):
            if normal in sprite and shiny in sprite and isinstance(sprite[normal],str) and isinstance(sprite[shiny],str) and sprite[normal] != sprite[shiny]:
                sprite[normal],sprite[shiny] = sprite[shiny],sprite[normal]
                applied.append(f"{field}.{normal}<->{shiny}")
                if normal in ("normal","regular","front"): break
    return applied

def render_page():
    cards="".join('<article><h3>'+html.escape(title)+'</h3><p>'+html.escape(detail)+'</p><small>'+html.escape(status)+'</small></article>' for title,detail,status in CHANGES)
    gymrows="".join("<tr><th>"+html.escape(leader)+"</th><td>"+html.escape(team)+"</td><td>£10,000</td><td>"+html.escape(tm)+"</td><td>"+html.escape(item)+"</td></tr>" for leader,team,tm,item in GYMS)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>18 Oct 2026 verified PRU updates • RelicDex</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#0b1420;color:#eaf3f6;font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{background:linear-gradient(130deg,#143f41,#13213b);padding:2rem max(1rem,calc((100vw - 1080px)/2));border-bottom:1px solid #3b626a}}
main{{max-width:1080px;padding:1rem;margin:auto}}h1{{line-height:1.1;font-size:clamp(2rem,6vw,3rem);margin:.4rem 0}}h2{{margin:1.8rem 0 .6rem}}p{{color:#bfd0d8}}a{{color:#8de0ca}}.lead{{max-width:760px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:12px}}
article{{background:#142532;border:1px solid #2a4551;border-radius:12px;padding:16px}}article h3{{margin:0 0 .4rem;color:#c9f5e8}}article p{{margin:.2rem 0 1rem}}small{{color:#d6c38e}}
.scroller{{overflow-x:auto;border:1px solid #2a4551;border-radius:12px}}table{{width:100%;border-collapse:collapse;min-width:690px;background:#142532}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #2a4551;vertical-align:top}}thead{{background:#21404c}}nav a{{display:inline-block;margin-right:1rem}}footer{{padding:2rem 1rem;text-align:center;color:#9eb0b8}}
</style></head><body>
<header><nav><a href="./">← RelicDex Pokédex</a><a href="{SHEET_URL}">Google Sheet ↗</a></nav>
<p style="letter-spacing:.13em;color:#8de0ca;margin-top:1.5rem">POKÉMON RELICS ULTIMATE</p>
<h1>18 October 2026 updates</h1><p class="lead">Changes taken from the compiled PRU development source, not assumptions from donor data. Build-verified is not the same as playthrough-tested.</p>
</header><main>
<h2>Verified changes and outstanding gameplay QA</h2><section class="cards">{cards}</section>
<h2>Johto gym first-battle teams</h2><p>Source/build verified; in-game battle and rewards testing is still outstanding.</p>
<div class="scroller"><table><thead><tr><th>Leader</th><th>First team & levels</th><th>Bonus</th><th>TM</th><th>Item</th></tr></thead><tbody>{gymrows}</tbody></table></div>
<h2>Source and further detail</h2><p><a href="{SOURCE_URL}">PRU Steevee/Neevee source and build checkpoint ↗</a> · <a href="{SHEET_URL}">RelicDex canonical Google Sheet ↗</a></p>
<p>Source commit: <code>{SOURCE}</code>. This page does not claim all species are catchable or that all event locations have been gameplay-tested.</p></main><footer>RelicDex • fan-made companion to Pokémon Relics Ultimate • approved artwork and third-party attribution retained</footer></body></html>'''

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--site",type=Path,required=True)
    args=parser.parse_args()
    site=args.site
    data=site/"data"/"pokemon.json"
    mons=json.loads(data.read_text(encoding="utf-8"))
    assert isinstance(mons,list) and len(mons)==444, "Unexpected canonical Pokédex"
    gardevoir=find(mons,"Gardevoir",318)
    valkiri=find(mons,"Valkyvoir",319) if not any(label(x)=="valkiri" for x in mons if isinstance(x,dict)) else find(mons,"Valkiri",319)
    noxichu=find(mons,"Noxichu",32)
    rename_label(valkiri,"Valkiri")
    fix_evo(gardevoir)
    gardevoir["pru_verified_moves"]=[{"level":36,"move":"Round"},{"level":38,"move":"Hyper Voice"}]
    valkiri["pru_verified_moves"]=[{"level":0,"move":"Boomburst (evolution)"},{"level":55,"move":"Boomburst"}]
    valkiri["pru_verified_sprite_palettes"]={"normal":"green","shiny":"blue","art":"approved PRL, unchanged"}
    valkiri["pru_verified_shop_item"]="Throat Spray · Goldenrod Dept Store 2F · ₽10,000"
    noxichu["pru_verified_moves"]=[{"level":0,"move":"Bite (evolution)"}]
    noxichu["pru_verified_sprite_source"]="Latest approved PRL artwork and party icon (not old PJR)"
    swapped=swap_existing_art(valkiri)
    data.write_text(json.dumps(mons,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (site/"updates.html").write_text(render_page(),encoding="utf-8")
    (site/"data"/"pru_updates.json").write_text(json.dumps({"date":"2026-10-18","romSourceSha":SOURCE,"romSourceUrl":SOURCE_URL,"googleSheet":SHEET_URL,"updates":[{"title":t,"detail":d,"status":s} for t,d,s in CHANGES]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    index=site/"index.html"
    html_text=index.read_text(encoding="utf-8")
    banner='''<a href="./updates.html" aria-label="See verified PRU updates from 18 October 2026" style="position:fixed;right:12px;bottom:12px;z-index:9999;background:#173d41;color:#e9fff8;border:2px solid #7bceae;padding:9px 14px;border-radius:24px;font:600 13px system-ui,sans-serif;box-shadow:0 2px 18px #0008;text-decoration:none">✦ 18 Oct PRU updates</a>'''
    if "18 Oct PRU updates" not in html_text:
        if "</body>" in html_text: html_text=html_text.replace("</body>",banner+"</body>",1)
        elif "</BODY>" in html_text: html_text=html_text.replace("</BODY>",banner+"</BODY>",1)
        else: html_text += banner
        index.write_text(html_text,encoding="utf-8")
    print("Verified PRU overlay applied to 444-entry RelicDex; Valkiri sprite keys swapped:",swapped)
    assert label(find(mons,"Valkiri",319)) == "valkiri"
    assert (site/"updates.html").stat().st_size > 2000

if __name__=="__main__":main()
