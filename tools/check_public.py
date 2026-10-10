# -*- coding: utf-8 -*-
"""Проверка ОПУБЛИКОВАННОГО адреса: телефон и десктоп, с ловлей ошибок консоли."""
import os, sys
from playwright.sync_api import sync_playwright
URL = "https://wapxman.github.io/fitting-room/"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, vp, mob in (("pub_mobile.png", {"width":390,"height":844}, True),
                          ("pub_desktop.png", {"width":1440,"height":900}, False)):
        pg = b.new_page(viewport=vp, device_scale_factor=2, is_mobile=mob, has_touch=mob)
        pg.on("pageerror", lambda e, n=name: errs.append(f"{n}: {e}"))
        pg.on("console", lambda m, n=name: errs.append(f"{n} console: {m.text}") if m.type=="error" else None)
        pg.goto(URL, wait_until="load")
        try:
            pg.wait_for_selector("#load", state="detached", timeout=40000)
        except Exception:
            errs.append(f"{n}: заглушка загрузки не исчезла")
        pg.wait_for_timeout(4000)
        # покрутить: выставить 135 градусов и убедиться, что кадр сменился
        before = pg.eval_on_selector("#lA", "e=>getComputedStyle(e).backgroundImage")
        pg.eval_on_selector("#rng", "el=>{el.value=135;el.dispatchEvent(new Event('input'))}")
        pg.wait_for_timeout(1200)
        after = pg.eval_on_selector("#lA", "e=>getComputedStyle(e).backgroundImage")
        if before == after:
            errs.append(f"{name}: кадр НЕ сменился при повороте")
        pg.screenshot(path=os.path.join(OUT, name))
        print(f"  {name}: снято, кадр сменился = {before != after}")
    b.close()
print("ОШИБКИ:", errs if errs else "нет")
sys.exit(1 if errs else 0)
