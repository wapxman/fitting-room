# -*- coding: utf-8 -*-
import http.server, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,"shots")
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def log_message(s,*a): pass
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("127.0.0.1",8791),H)
threading.Thread(target=srv.serve_forever,daemon=True).start()
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":1400,"height":900},device_scale_factor=2)
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("console",lambda m:errs.append("console: "+m.text) if m.type=="error" else None)
    pg.goto("http://127.0.0.1:8791/index.html",wait_until="load")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=os.path.join(OUT,"pick_1.png"))
    # выбрать ботинки -> сочетание снято частично (только 0 градусов)
    pg.get_by_text("Коричневые ботинки",exact=True).click(); pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(OUT,"pick_2_boot.png"))
    # выбрать худи -> сочетание ещё не снято, должна быть честная заглушка
    pg.get_by_text("Чёрное худи",exact=True).click(); pg.wait_for_timeout(1200)
    shown = pg.eval_on_selector("#msg","e=>getComputedStyle(e).display")
    print("заглушка для неснятого:", shown)
    pg.screenshot(path=os.path.join(OUT,"pick_3_notready.png"))
    b.close()
srv.shutdown()
print("ОШИБКИ:", errs if errs else "нет")
