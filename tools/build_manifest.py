# -*- coding: utf-8 -*-
"""Собрать assets/outfits.json по тому, что реально снято.

Матрица наполняется часами, поэтому манифест пересобирается на каждый прогон, а
вьюер показывает ровно то, что готово: сочетание без кадров помечается как
«снимается». Так интерфейс работает с первого готового комплекта, а не ждёт все
27, и ничего переписывать по дороге не надо.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wardrobe import TOPS, BOTTOMS, SHOES, combos, combo_id  # noqa: E402

ALIGNED = os.path.join(ROOT, "frames_aligned")

out = {
    "items": {
        "top": [{"id": i, "name": n} for i, n, _ in TOPS],
        "bottom": [{"id": i, "name": n} for i, n, _ in BOTTOMS],
        "shoes": [{"id": i, "name": n} for i, n, _ in SHOES],
    },
    "combos": {},
}

ready = 0
for t, b, s in combos():
    cid = combo_id(t, b, s)
    d = os.path.join(ALIGNED, cid)
    frames = {}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            m = re.fullmatch(r"a(\d{3})\.png", f)
            if m:
                frames[int(m.group(1))] = f"frames_aligned/{cid}/{f}"
    out["combos"][cid] = frames
    if frames:
        ready += 1

out["total"] = len(out["combos"])
out["ready"] = ready
out["note"] = f"Готово сочетаний: {ready} из {out['total']}."

# Фон сцены — из самого кадра, иначе по краям виден шов между подложкой
# страницы и подложкой снимка (два почти одинаковых, но разных серых).
try:
    import numpy as np
    from PIL import Image
    any_frame = next(p for c in out["combos"].values() for p in c.values())
    a = np.asarray(Image.open(os.path.join(ROOT, any_frame)).convert("RGB"))
    g = tuple(int(v) for v in np.median(a[:, :30, :].reshape(-1, 3), axis=0))
    out["bg"] = "rgb(%d,%d,%d)" % g
except StopIteration:
    out["bg"] = "rgb(121,120,122)"

with open(os.path.join(ROOT, "assets", "outfits.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print(f"сочетаний готово: {ready} из {out['total']}")
for cid, fr in out["combos"].items():
    if fr:
        print(f"  {cid}: {sorted(fr)}")
print("манифест записан")
