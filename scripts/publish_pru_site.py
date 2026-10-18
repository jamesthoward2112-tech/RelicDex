#!/usr/bin/env python3
"""Publish the PRU microsite alongside, not over, the canonical RelicDex."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from shutil import copy2, copytree
TITLE_SHA256 = "0cfdc68858e6818c771dd10e3d79b41a41658f642c0aaec7cd017b2cc60a2c64"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--site",type=Path,required=True)
    p.add_argument("--source",type=Path,default=Path("site/pru"))
    p.add_argument("--pru",type=Path,required=True)
    a=p.parse_args()
    root=a.site
    mons=json.loads((root/"data/pokemon.json").read_text(encoding="utf-8"))
    assert len(mons)==444,"Cannot publish PRU microsite without the full RelicDex"
    names={m.get("name") for m in mons}
    assert {"Noxichu","Valkiri","Skulberus","Charaxis"} <= names,"Spotlight species missing"
    approved=a.pru/"assets/pru_title/Noxichu_Title_GBA_240x160_256colour.png"
    assert approved.is_file(),"Approved title asset missing from pinned PRU source"
    actual=hashlib.sha256(approved.read_bytes()).hexdigest()
    assert actual==TITLE_SHA256,f"Unapproved PRU title artwork checksum: {actual}"
    out=root/"pru"
    copytree(a.source,out,dirs_exist_ok=True)
    (out/"media").mkdir(exist_ok=True)
    copy2(approved,out/"media/title-screen.png")
    for target in (out/"index.html",out/"about/index.html"):
        assert target.is_file(),str(target)
    assert (out/"media/title-screen.png").is_file()
    # One compact discovery link is added to the existing Pokédex without altering its app.
    index=root/"index.html"
    txt=index.read_text(encoding="utf-8")
    if 'PRU game website' not in txt:
        link='<a href="./pru/" aria-label="Explore the PRU game website" style="position:fixed;left:12px;bottom:12px;z-index:9998;background:#183048;color:#ffdea6;border:2px solid #b69a63;padding:9px 14px;border-radius:24px;font:600 13px system-ui,sans-serif;box-shadow:0 2px 18px #0008;text-decoration:none">◇ PRU game website</a>'
        txt=txt.replace("</body>",link+"</body>",1) if "</body>" in txt else txt+link
        index.write_text(txt,encoding="utf-8")
    print(f"PRU microsite verified: 444 Dex entries, approved title sha256={actual}, homepage/about + sprites")
if __name__=="__main__":main()
