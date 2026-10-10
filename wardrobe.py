# -*- coding: utf-8 -*-
"""Гардероб: 3 верха x 3 низа x 3 обуви = 27 сочетаний, и задания на их съёмку.

ПОЧЕМУ СОЧЕТАНИЯ СНИМАЮТСЯ ЦЕЛИКОМ, А НЕ СКЛЕИВАЮТСЯ ИЗ СЛОЁВ. Соблазн очевиден:
снять 9 вещей по 8 ракурсов (72 кадра) и складывать их друг на друга, получив
27 сочетаний даром. Отвергнуто: модель не рисует одежду отдельно от человека и
тем более не ставит её в те же пиксели, а склейка по пояснице и щиколотке даёт
видимый шов на фотореалистичном кадре — там, где у разных низов разная посадка и
своя тень. Поэтому каждое сочетание — свои кадры.

ЦЕНА РЕШЕНИЯ, ЧЕСТНО: 27 x 8 = 216 кадров это ~7 часов. Поэтому у матрицы шаг
90 градусов (4 ракурса, ~3,5 часа), а восемь ракурсов остаются у исходного
сочетания — вьюер умеет неполный круг и подмешивает соседний кадр, так что
«плотное» сочетание крутится глаже, а остальные всё равно крутятся кругом.
"""

TOPS = [
    ("tee",    "Белая футболка", "a plain white cotton crew-neck t-shirt"),
    ("hoodie", "Чёрное худи",    "a black cotton hoodie with the hood down, relaxed fit"),
    ("shirt",  "Синяя рубашка",  "a light blue oxford button-down shirt, long sleeves, untucked"),
]
BOTTOMS = [
    ("jeans",  "Тёмные джинсы",  "dark indigo straight-leg jeans"),
    ("chino",  "Бежевые чиносы", "beige slim chino trousers"),
    ("jogger", "Серые джоггеры", "grey cotton joggers with elastic cuffs"),
]
SHOES = [
    ("sneak",  "Белые кеды",     "white leather low-top sneakers"),
    ("boot",   "Коричневые ботинки", "brown leather lace-up boots"),
    ("black",  "Чёрные кроссовки",   "black running sneakers"),
]

# Шаг матрицы. У исходного сочетания 8 ракурсов — он снят раньше и не
# перезаписывается (скрипт съёмки пропускает уже существующие файлы).
ANGLES = [
    (0,   "straight-on FRONT view, he faces the camera directly"),
    (90,  "exact RIGHT-SIDE PROFILE, body turned 90 degrees"),
    (180, "straight-on BACK view, face not visible at all"),
    (270, "exact LEFT-SIDE PROFILE, body turned 270 degrees"),
]

HERO = "tee-jeans-sneak"   # уже снято на 8 ракурсов


def combos():
    for t in TOPS:
        for b in BOTTOMS:
            for s in SHOES:
                yield t, b, s


def combo_id(t, b, s):
    return f"{t[0]}-{b[0]}-{s[0]}"


def prompt(t, b, s, ang_desc):
    return (
        "Same man, same studio, same framing as before. Full-body studio photograph, "
        "photorealistic, sharp, vertical 3:4. "
        f"He wears {t[2]}, {b[2]} and {s[2]}. "
        "Relaxed A-pose, arms hanging slightly away from the body, standing straight. "
        "Seamless mid-grey studio backdrop, soft even lighting. "
        "Camera at chest height, FULL BODY from the top of the head to the soles, "
        "figure centred, same scale and distance as the previous images.\n"
        f"CAMERA ANGLE: {ang_desc}"
    )


if __name__ == "__main__":
    import json
    import os
    import sys

    out = []
    for t, b, s in combos():
        cid = combo_id(t, b, s)
        for ang, desc in ANGLES:
            out.append({"name": f"{cid}/a{ang:03d}", "prompt": prompt(t, b, s, desc)})

    # Уже снятые кадры пропускаем: скрипт съёмки смотрит на файлы, но задание
    # лучше не раздувать — так в логе видно реальный остаток.
    root = os.path.dirname(os.path.abspath(__file__))
    todo = [j for j in out
            if not os.path.exists(os.path.join(root, "frames", j["name"] + ".png"))]

    dst = os.path.join(root, "jobs_matrix.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(todo, f, ensure_ascii=False, indent=1)
    print(f"сочетаний: {len(list(combos()))}, ракурсов на сочетание: {len(ANGLES)}")
    print(f"всего кадров в матрице: {len(out)}, осталось снять: {len(todo)}")
    print(f"оценка времени: ~{len(todo)*2/60:.1f} ч")
    print("задание:", dst)
