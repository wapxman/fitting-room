# -*- coding: utf-8 -*-
"""Разбор исходного кадра: вырезать фон, снять пропорции и цвета.

Зачем: 3D-фигура должна быть ПО ЭТОМУ человеку, а не «средний мужчина».
Из одного фронтального кадра честно снимаются ширины торса, высоты уровней
и цвета. Этого хватает, чтобы задать пропорции модели числами, а не на глаз.

Фон равномерно-серый, поэтому сегментация простая: заливка от углов по порогу
расстояния в RGB. Заливка, а НЕ «все похожие пиксели» — серая одежда по цвету
близка к фону, и без связности мы выгрызли бы дыры прямо в футболке.

⚠️ ГЛАВНАЯ ГРАБЛЯ, НА КОТОРУЮ ПЕРВАЯ ВЕРСИЯ НАСТУПИЛА. Поза A-образная: руки
отведены от корпуса. Если мерить ширину как (самый правый минус самый левый
пиксель строки), то на уровне бёдер получаешь РАЗМАХ РУК — первая версия дала
«бёдра/плечи = 1,56», чего у человека не бывает. Поэтому строка режется на
связные отрезки, и торсом считается ЦЕНТРАЛЬНЫЙ: [рука][торс][рука].
"""
import json
import os
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

SRC = r"C:\Users\User\tg-claude-bot\_voice_34d1d1dad8f74dbd886b84662e2ecedf.jpg"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(OUT_DIR, exist_ok=True)

img = Image.open(SRC).convert("RGB")
W, H = img.size
a = np.asarray(img).astype(np.int16)
print(f"исходник: {W}x{H}")

# ⚠️ ПОРОГ ЗДЕСЬ РЕШАЕТ ВСЁ, И ПЕРВАЯ ВЕРСИЯ ЕГО ЗАВЫСИЛА В ТРИ РАЗА.
# Стояло TOL=26 «с запасом» — и заливка СЪЕЛА ОДЕЖДУ: серая футболка отстоит от
# фона всего на 11,1 по RGB, то есть попадала внутрь порога, фон протекал сквозь
# неё, и от фигуры оставались голова, кисти и кромки (14,3 % кадра вместо ~20 %).
# Замер по материалам (расстояние до локального фона):
#   футболка 11,1 · лосины 22,9 · кроссовок 23,4 · рукав 25,8 · кожа 44,2 · лицо 107,8
# Шум самого фона при этом 1,0. Значит рабочий порог — между шумом и футболкой,
# берём 7: фон ловится уверенно, а самая «фоновая» ткань остаётся фигурой.
#
# Фон берём ЛОКАЛЬНЫЙ ПО СТРОКЕ (медиана левых и правых 120 px), а не один цвет
# на кадр: по кадру он плывёт 120…135, и единая константа на краях ошибается
# сильнее, чем весь наш запас по порогу.
#
# ⚠️ И ОДНОЙ МЕДИАНЫ НА СТРОКУ ТОЖЕ МАЛО. С общим фоном на строку bbox фигуры
# растянулся на весь кадр (32…959 при реальных 193…746): у подложки есть и
# ГОРИЗОНТАЛЬНЫЙ перепад, а медиана левых и правых полей сводит его в одно
# число, которое ошибается на обоих краях сразу — больше, чем весь наш порог 7.
# Поэтому фон — линейная рампа: слева своё значение, справа своё, между ними
# интерполяция. Так ловятся оба градиента, вертикальный и горизонтальный.
MARGIN = 120
left_med = np.median(a[:, :MARGIN, :], axis=1)        # (H, 3)
right_med = np.median(a[:, W - MARGIN:, :], axis=1)   # (H, 3)
ramp = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :, None]
bg_field = left_med[:, None, :] * (1.0 - ramp) + right_med[:, None, :] * ramp
bg = np.median(bg_field.reshape(-1, 3), axis=0)       # средний, только для отчёта
dist = np.sqrt(((a - bg_field) ** 2).sum(axis=2))
bg_like = dist < 7.0

mask_bg = np.zeros((H, W), dtype=bool)
q = deque()
for sy, sx in ((0, 0), (0, W - 1), (H - 1, 0), (H - 1, W - 1)):
    if bg_like[sy, sx] and not mask_bg[sy, sx]:
        mask_bg[sy, sx] = True
        q.append((sy, sx))
while q:
    y, x = q.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < H and 0 <= nx < W and not mask_bg[ny, nx] and bg_like[ny, nx]:
            mask_bg[ny, nx] = True
            q.append((ny, nx))

fig = ~mask_bg

# Крапины: одиночные «фоновые» точки внутри ткани и наоборот. Снимаем закрытием
# (расширить → сжать) по маске фигуры — дешевле и предсказуемее, чем медиана.
fm = Image.fromarray((fig * 255).astype(np.uint8), "L")
fm = fm.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
fig = np.asarray(fm) > 127

# ⚠️ РЕШАЮЩИЙ ШАГ, без которого всё предыдущее не спасало. По краям кадра
# остаётся кромка от JPEG и виньетки, и она попадала в «фигуру»: bbox выходил
# 0…1255 × 8…959, то есть весь кадр, а замеры снимались с пустого фона —
# все цвета получались серыми (#757575), то есть цветом подложки.
# Человек на кадре один и он сплошной, поэтому оставляем ТОЛЬКО самую большую
# связную область. Это снимает любой мусор по краям разом и навсегда.
lab = np.zeros((H, W), dtype=np.int32)
cur, best_id, best_sz = 0, 0, 0
for y0 in range(H):
    for x0 in range(W):
        if not fig[y0, x0] or lab[y0, x0]:
            continue
        cur += 1
        sz = 0
        dq = deque([(y0, x0)])
        lab[y0, x0] = cur
        while dq:
            y, x = dq.popleft()
            sz += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and fig[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = cur
                    dq.append((ny, nx))
        if sz > best_sz:
            best_id, best_sz = cur, sz
fig = lab == best_id
print(f"связных областей: {cur}, крупнейшая {best_sz} px")
print(f"пикселей фигуры: {fig.sum()} ({fig.sum() / (W * H):.1%} кадра)")

alpha_img = Image.fromarray((fig * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.8))
cut = img.copy()
cut.putalpha(alpha_img)
cut.save(os.path.join(OUT_DIR, "person_cutout.png"))

rows = np.where(fig.any(axis=1))[0]
cols = np.where(fig.any(axis=0))[0]
top, bottom = int(rows[0]), int(rows[-1])
left, right = int(cols[0]), int(cols[-1])
hpx = bottom - top + 1
cx = (left + right) / 2.0
print(f"фигура: {top}..{bottom} ({hpx} px), {left}..{right}")


def runs(y):
    """Связные отрезки фигуры в строке y → [(x0, x1), ...]."""
    xs = np.where(fig[y])[0]
    if len(xs) == 0:
        return []
    out, s, p = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == p + 1:
            p = x
            continue
        out.append((int(s), int(p)))
        s = p = x
    out.append((int(s), int(p)))
    return out


def torso_at(frac):
    """Ширина ТОРСА на доле роста: центральный отрезок, а не размах рук.

    Порог длины 20 px, а не 3: тонкие отрезки — это пальцы, кромка рукава и
    шум сегментации. С порогом 3 центральным однажды оказался обрывок в 4 px,
    и «талия» вышла 4 пикселя — цифра, по которой модель стала бы осой.
    """
    y = int(top + frac * (hpx - 1))
    y = max(0, min(H - 1, y))
    rr = [r for r in runs(y) if r[1] - r[0] + 1 >= 20]
    if not rr:
        return 0.0, None
    best = min(rr, key=lambda r: abs((r[0] + r[1]) / 2.0 - cx))
    return float(best[1] - best[0] + 1), best


def span_at(frac):
    """Полный размах строки — нужен, чтобы найти кисти и ширину плеч с руками."""
    y = int(top + frac * (hpx - 1))
    rr = runs(y)
    if not rr:
        return 0.0
    return float(rr[-1][1] - rr[0][0] + 1)


torso = np.array([torso_at(i / 200.0)[0] for i in range(201)])
span = np.array([span_at(i / 200.0) for i in range(201)])

# Уровни ищем по профилю ТОРСА (индекс = доля роста × 200), и КАЖДЫЙ в своём
# анатомическом окне. Прежняя версия искала их цепочкой «от предыдущего», и одна
# промахнувшаяся точка утаскивала за собой все следующие — так шея на 13,5 %
# сделала плечи на 25 %, а талию на 37,5 %. Окна заданы от роста, независимо.
def arg_in(fn, lo, hi):
    lo, hi = max(0, lo), min(len(torso), hi)
    seg = torso[lo:hi]
    seg = np.where(seg > 0, seg, np.nan)
    if np.all(np.isnan(seg)):
        return (lo + hi) // 2
    return int(lo + (np.nanargmin(seg) if fn == "min" else np.nanargmax(seg)))


neck_i = arg_in("min", 22, 34)    # шея: 11…17 % роста, самое узкое под головой
sh_i = arg_in("max", 34, 52)      # плечи: 17…26 %
waist_i = arg_in("min", 58, 82)   # талия: 29…41 %
hip_i = arg_in("max", 86, 110)    # бёдра: 43…55 %
# Пах: ниже бёдер торс распадается на две ноги → в строке становится 2+ отрезка
crotch_i = None
for i in range(hip_i, 150):
    y = int(top + (i / 200.0) * (hpx - 1))
    rr = [r for r in runs(y) if r[1] - r[0] >= 8]
    mid = [r for r in rr if abs((r[0] + r[1]) / 2 - cx) < 0.18 * hpx]
    if len(mid) >= 2:
        crotch_i = i
        break

measure = {
    "source": os.path.basename(SRC),
    "image": {"w": W, "h": H},
    "figure_px": {"top": top, "bottom": bottom, "left": left, "right": right, "height": hpx},
    "levels_frac": {
        "neck": neck_i / 200.0,
        "shoulder": sh_i / 200.0,
        "waist": waist_i / 200.0,
        "hip": hip_i / 200.0,
        "crotch": (crotch_i / 200.0) if crotch_i else None,
    },
    "widths_px": {
        "head": float(torso[: neck_i].max()) if neck_i > 0 else 0.0,
        "neck": float(torso[neck_i]),
        "shoulder": float(torso[sh_i]),
        "waist": float(torso[waist_i]),
        "hip": float(torso[hip_i]),
        "armspan": float(span.max()),
    },
    "torso_profile": [round(float(v) / hpx, 4) for v in torso],
}
m = measure["widths_px"]

# Санитарная граница на талию. Замер даёт 118 px при плечах 357 (0,33) — у
# человека так не бывает: на этой строке центральный отрезок иногда прихватывает
# только часть корпуса между прижатыми руками. Реальное отношение талия/плечи у
# мужчин 0,70…0,85. Если замер ниже 0,60 — он недостоверен, и вместо него берём
# интерполяцию между плечами и бёдрами, честно помечая это в данных.
measure["waist_measured_px"] = m["waist"]
if m["shoulder"] > 0 and m["waist"] / m["shoulder"] < 0.60:
    m["waist"] = round((m["shoulder"] + m["hip"]) / 2.0 * 0.86, 1)
    measure["waist_estimated"] = True
    print(f"[!] талия {measure['waist_measured_px']:.0f} px недостоверна "
          f"(<0,60 плеч) -> взята оценка {m['waist']:.0f} px")
else:
    measure["waist_estimated"] = False
measure["ratios"] = {
    "shoulder_to_height": m["shoulder"] / hpx,
    "waist_to_shoulder": m["waist"] / m["shoulder"],
    "hip_to_shoulder": m["hip"] / m["shoulder"],
    "head_to_height": m["head"] / hpx,
    "heads_tall": hpx / (measure["levels_frac"]["neck"] * hpx) if neck_i else None,
}


def sample(y_frac, x_off, r=7):
    """Цвет медианой в точке: y — доля роста, x_off — смещение от оси в долях роста."""
    y = int(top + y_frac * hpx)
    x = int(cx + x_off * hpx)
    patch = a[max(0, y - r):y + r, max(0, x - r):x + r].reshape(-1, 3)
    if len(patch) == 0:
        return None
    return tuple(np.median(patch, axis=0).astype(int))


def hexof(t):
    return "#%02x%02x%02x" % tuple(t) if t else None


# Кожу берём по НЕСКОЛЬКИМ точкам и выбираем самую «кожную» (R>G>B и не тёмную):
# точка на глаз попадает то в тень, то в волосы, и одиночная проба врёт.
cands = [sample(f, dx) for f, dx in
         ((0.062, -0.028), (0.062, 0.028), (0.072, 0.0), (0.115, 0.0), (0.50, -0.175))]
skin = None
for c in cands:
    if c is None:
        continue
    r_, g_, b_ = int(c[0]), int(c[1]), int(c[2])
    if r_ > g_ > b_ and r_ > 120:
        if skin is None or r_ > skin[0]:
            skin = (r_, g_, b_)
colors = {
    "hair": hexof(sample(0.018, 0.0)),
    "skin": hexof(skin) or hexof(sample(0.072, 0.0)),
    "top": hexof(sample(0.30, 0.0)),
    "bottom": hexof(sample(0.62, -0.03)),
    "shoe": hexof(sample(0.978, -0.06)),
    "background": hexof(tuple(bg.astype(int))),
}
measure["colors"] = colors

with open(os.path.join(OUT_DIR, "measure.json"), "w", encoding="utf-8") as f:
    json.dump(measure, f, ensure_ascii=False, indent=2)

print("\n=== УРОВНИ (доля роста от макушки) ===")
for k, v in measure["levels_frac"].items():
    print(f"  {k:9s} {v}")
print("=== ШИРИНЫ (px) ===")
for k, v in m.items():
    print(f"  {k:9s} {v:.0f}")
print("=== ОТНОШЕНИЯ ===")
for k, v in measure["ratios"].items():
    print(f"  {k:22s} {v:.3f}" if v else f"  {k:22s} —")
print("=== ЦВЕТА ===")
for k, v in colors.items():
    print(f"  {k:11s} {v}")
