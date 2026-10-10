# -*- coding: utf-8 -*-
"""Собрать assets/outfits.json по тому, что реально лежит в кадрах.

Вьюер умеет крутить НЕПОЛНЫЙ круг (смешивает ближайшие снятые углы), поэтому
манифест просто перечисляет то, что есть: каждый новый ракурс делает оборот
плавнее, и переписывать ничего не надо.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIGNED = os.path.join(ROOT, "frames_aligned")

OUTFITS = [
    {"id": "tee-jeans", "name": "Футболка и джинсы",
     "desc": "белая футболка, тёмные джинсы, белые кеды", "dir": ""},
]

out = {"note": "Кадры сняты по вашему фото и выровнены по росту и линии пола.",
       "outfits": []}
for o in OUTFITS:
    d = os.path.join(ALIGNED, o["dir"]) if o["dir"] else ALIGNED
    frames = {}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            m = re.fullmatch(r"a(\d{3})\.png", f)
            if m:
                rel = f"frames_aligned/{o['dir']+'/' if o['dir'] else ''}{f}"
                frames[int(m.group(1))] = rel
    out["outfits"].append({**{k: o[k] for k in ("id", "name", "desc")},
                           "frames": frames, "ready": len(frames) >= 2})
    print(f"  {o['id']}: {len(frames)} ракурс(ов) -> {sorted(frames)}")

os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
with open(os.path.join(ROOT, "assets", "outfits.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("манифест записан")
