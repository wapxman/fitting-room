# -*- coding: utf-8 -*-
"""Снимки примерочной: проверка глазами, а не «должно работать»."""
import http.server, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,"shots"); os.makedirs(OUT,exist_ok=True)
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def log_message(s,*a): pass
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("127.0.0.1",8790),H)
threading.Thread(target=srv.serve_forever,daemon=True).start()
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":1400,"height":900},device_scale_factor=2)
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("console",lambda m:errs.append("console: "+m.text) if m.type=="error" else None)
    pg.goto("http://127.0.0.1:8790/index.html",wait_until="load")
    try: pg.wait_for_selector("#load",state="detached",timeout=25000)
    except Exception: errs.append("заглушка не исчезла")
    pg.wait_for_timeout(2500)
    pg.screenshot(path=os.path.join(OUT,"live_000.png"))
    for deg,name in ((90,"live_090.png"),(180,"live_180.png"),(315,"live_315.png")):
        pg.eval_on_selector("#rng", f"el=>{{el.value={deg};el.dispatchEvent(new Event('input'))}}")
        pg.wait_for_timeout(900)
        pg.screenshot(path=os.path.join(OUT,name))
    b.close()
srv.shutdown()
print("ошибки:", errs if errs else "нет")
