# -*- coding: utf-8 -*-
"""Снимки примерочной в нескольких ракурсах — проверка глазами, а не «должно работать».

Поднимает локальный сервер (модули ES с file:// не грузятся из-за CORS),
открывает страницу, ждёт первый кадр WebGL и снимает: анфас, профиль, спину,
плюс смену одежды. Любая ошибка в консоли браузера печатается — без этого
пустой чёрный кадр выглядит как «просто тёмная сцена».
"""
import http.server
import os
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)
PORT = 8777


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"сервер на :{PORT}, корень {ROOT}")

errors, logs = [], []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader",
                                "--enable-unsafe-swiftshader", "--disable-gpu-sandbox"])
    pg = b.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
    pg.on("console", lambda m: (logs.append(f"{m.type}: {m.text}"),
                                errors.append(m.text) if m.type == "error" else None))
    pg.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))

    pg.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="load")
    # Ждём, пока исчезнет заглушка «Собираю фигуру…» — это и есть признак,
    # что модуль отработал без исключения.
    try:
        pg.wait_for_selector("#load", state="detached", timeout=25000)
    except Exception:
        print("[!] заглушка загрузки не исчезла — модуль упал")
    pg.wait_for_timeout(2500)

    def shot(name):
        pg.screenshot(path=os.path.join(OUT, name))
        print("  снято:", name)

    shot("01_front.png")
    pg.click("#side90"); pg.wait_for_timeout(900); shot("02_profile.png")
    pg.click("#back");   pg.wait_for_timeout(900); shot("03_back.png")
    pg.click("#front");  pg.wait_for_timeout(600)

    # сменить одежду: худи + джоггеры + ботинки + пальто
    pg.click('.tab[data-c="top"]'); pg.wait_for_timeout(250)
    pg.get_by_text("Худи", exact=True).click(); pg.wait_for_timeout(500)
    pg.click('.tab[data-c="bottom"]'); pg.wait_for_timeout(250)
    pg.get_by_text("Джоггеры", exact=True).click(); pg.wait_for_timeout(500)
    pg.click('.tab[data-c="outer"]'); pg.wait_for_timeout(250)
    pg.get_by_text("Пальто", exact=True).click(); pg.wait_for_timeout(700)
    shot("04_outfit2.png")

    pg.click("#bgBtn"); pg.wait_for_timeout(500); shot("05_light_bg.png")
    b.close()

srv.shutdown()
print("\n=== ОШИБКИ КОНСОЛИ ===")
if errors:
    for e in errors[:15]:
        print("  ", e[:300])
    sys.exit(1)
print("  нет")
