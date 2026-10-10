# -*- coding: utf-8 -*-
"""Круговой оборот человека: N ракурсов ОДНОГО человека через ChatGPT.

Зачем. Процедурный манекен в Three.js живым человеком не станет никогда — это
предел подхода, а не усердия. Живой вид даёт только настоящий кадр. Поэтому
снимаем «карусель»: один и тот же человек с N углов, потом их крутит вьюер, и
выглядит это как поворот 3D-модели, но фотореалистично.

ДВА РЕШЕНИЯ, НА КОТОРЫХ ВСЁ ДЕРЖИТСЯ:
1. ОДИН ЧАТ на весь оборот. В gpt_imagegen_onechat.py единый чат назван ценой
   («модель тянет стиль предыдущей картинки»), и для несвязанных сюжетов это
   верно. Здесь ровно наоборот: тянуть прошлое — цель, иначе на каждом ракурсе
   будет другой человек.
2. ОПОРНЫЙ КАДР прикрепляется файлом в первое сообщение. Без него лицо и
   телосложение уплывают уже на втором ракурсе.

Сырой CDP, а не Playwright: тот при connect_over_cdp цепляется ко ВСЕМ вкладкам
браузера владельца и падает ещё до первой картинки.

  python gpt_turntable.py jobs.json OUT_DIR REFERENCE.jpg
"""
import base64
import json
import os
import sys
import time

import requests
import websocket

CDP = "http://127.0.0.1:9222"
JOBS = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = sys.argv[2]
REF = os.path.abspath(sys.argv[3])
os.makedirs(OUT, exist_ok=True)

# Готовая картинка приходит с backend-api/estuary. naturalWidth >= 512 отсекает
# превью-заглушку, которую видно, пока идёт отрисовка.
# ⚠️ ГОТОВАЯ КАРТИНКА ПРИХОДИТ КАК blob:, А НЕ С estuary/oaiusercontent.
# Старый фильтр (унаследованный из gpt_imagegen_cdp.py) не находил НИЧЕГО, и
# прогон выглядел как «картинка не появилась», хотя она была нарисована и
# висела в чате. Проверено 10.10.2026: сгенерированный кадр — blob:…, 1086x1448.
# Селектор 'main img' тоже снят: разметка ChatGPT сменилась, атрибута
# data-message-author-role больше нет, и 'main' может не совпасть. Берём
# document.images — он не зависит от вёрстки.
LIST_IMGS = """
(() => [...document.images]
    .filter(i => { const s = i.currentSrc || i.src || '';
                   return (s.startsWith('blob:') || s.includes('estuary/content')
                           || s.includes('oaiusercontent')) && i.naturalWidth >= 512; })
    .map(i => JSON.stringify({src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight}))
)()
"""

FETCH_B64 = """
(async () => {
    const r = await fetch(%s);
    const b = await r.blob();
    return await new Promise(res => { const fr = new FileReader();
        fr.onload = () => res(fr.result); fr.readAsDataURL(b); });
})()
"""


class Tab:
    def __init__(self, url="https://chatgpt.com/", resume=False):
        # resume: сесть в уже открытый тред. Новый чат = новый человек, поэтому
        # продолжать оборот надо ТОЛЬКО в том же разговоре.
        t = None
        if resume:
            for x in requests.get(f"{CDP}/json/list", timeout=20).json():
                if x.get("type") == "page" and "chatgpt.com/c/" in x.get("url", ""):
                    t = x
                    break
            if t:
                print(f"  продолжаю тред {t['url'][-12:]}", flush=True)
        if t is None:
            t = requests.put(f"{CDP}/json/new?{url}", timeout=30).json()
        self.id = t["id"]
        self.resumed = resume and "chatgpt.com/c/" in t.get("url", "")
        self.n = 0
        # suppress_origin обязателен: Chrome отклоняет CDP-сокет с заголовком Origin.
        self.ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=120,
                                              suppress_origin=True)

    def send(self, method, **params):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr, await_promise=False):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=await_promise)
        return r.get("result", {}).get("value")

    def key(self, key, code, vk):
        for typ in ("keyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=typ, key=key, code=code,
                      windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)

    def attach_file(self, path):
        """Прицепить файл в скрытый input[type=file] композера."""
        self.send("DOM.enable")
        doc = self.send("DOM.getDocument", depth=-1, pierce=True)
        node = self.send("DOM.querySelector", nodeId=doc["root"]["nodeId"],
                         selector="input[type=file]")
        nid = node.get("nodeId")
        if not nid:
            return False
        self.send("DOM.setFileInputFiles", files=[path], nodeId=nid)
        return True

    def close(self):
        for fn in (lambda: self.ws.close(),
                   lambda: requests.get(f"{CDP}/json/close/{self.id}", timeout=10)):
            try:
                fn()
            except Exception:
                pass


def seen_set(tab):
    return {json.loads(s)["src"] for s in (tab.js(LIST_IMGS) or [])}


def wait_new(tab, seen, label, limit=150):
    """Ждать НОВЫЙ адрес (которого не было), затем — пока размер не замрёт.

    В длинном треде все прошлые картинки висят в DOM, поэтому «взять последнюю»
    скачало бы предыдущую, пока новая ещё рисуется.
    """
    stable = None
    for i in range(limit):
        time.sleep(5)
        for s in (tab.js(LIST_IMGS) or []):
            d = json.loads(s)
            if d["src"] in seen:
                continue
            key = (d["w"], d["h"])
            if stable == key:
                return d["src"]
            stable = key
        if i % 12 == 11:
            print(f"    ...{label}: ждём {(i + 1) * 5}с", flush=True)
    return None


def save(tab, url, dst):
    data = tab.js(FETCH_B64 % json.dumps(url), await_promise=True)
    if not data or "," not in data:
        return False
    with open(dst, "wb") as f:
        f.write(base64.b64decode(data.split(",", 1)[1]))
    return True


RESUME = "--resume" in sys.argv
tab = Tab(resume=RESUME)
done = 0
try:
    time.sleep(4 if tab.resumed else 9)
    if not tab.js("""(() => { const b = document.querySelector('#prompt-textarea')
                       || document.querySelector("div[contenteditable='true']");
                       if (!b) return false; b.focus(); return true; })()"""):
        print("НЕ НАЙДЕН композер — вероятно, не выполнен вход в ChatGPT")
        sys.exit(2)

    for idx, job in enumerate(JOBS):
        dst = os.path.join(OUT, job["name"] + ".png")
        # Имя задания может быть «сочетание/ракурс» — тогда нужен подкаталог.
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst) and os.path.getsize(dst) > 30000:
            print(f"  [{job['name']}] уже есть", flush=True)
            done += 1
            continue

        seen = seen_set(tab)

        # ⚠️ ЖДЁМ, ПОКА КНОПКА ОТПРАВКИ СТАНЕТ АКТИВНОЙ. Пока ChatGPT дописывает
        # предыдущий ответ, кнопка заблокирована, и клик по ней уходит в никуда
        # (Enter в это время тоже не срабатывает). Из-за этого 11.10 кадр
        # tee-jeans-boot/a270 был набран в поле, но не отправлен. Картинка
        # появляется РАНЬШЕ, чем ход завершается, поэтому «дождались картинки»
        # не означает «можно слать следующий».
        for _ in range(60):
            if tab.js("""(() => {
                const b = document.querySelector('button[data-testid="send-button"]')
                       || document.querySelector('#composer-submit-button');
                const stop = document.querySelector('button[data-testid="stop-button"]');
                return !!b && !b.disabled && !stop;
            })()"""):
                break
            time.sleep(3)

        # Чистим поле: после неудачной отправки там остаётся прошлый текст, и
        # новый допишется к нему, превратив задание в кашу.
        tab.js("""(() => { const b = document.querySelector('#prompt-textarea')
                   || document.querySelector("div[contenteditable='true']");
                   if (!b) return; b.focus();
                   document.execCommand('selectAll', false, null);
                   document.execCommand('delete', false, null); })()""")
        time.sleep(0.6)
        # Опорный кадр цепляем ТОЛЬКО к первому сообщению: дальше человек уже
        # «в контексте» треда, а повторная загрузка сбивает композер.
        if idx == 0 and not tab.resumed:
            if tab.attach_file(REF):
                print("  опорный кадр прикреплён", flush=True)
                time.sleep(7)
            else:
                print("  [!] поле загрузки не найдено — иду без опорного кадра", flush=True)

        tab.send("Input.insertText", text=job["prompt"])
        time.sleep(1.5)
        # ⚠️ НЕ ПОЛАГАТЬСЯ НА ENTER. 11.10 съёмка встала намертво: текст был
        # набран в поле, Enter не сработал, и скрипт ждал картинку, которой
        # никто не просил. Жмём саму кнопку отправки, Enter — только запасной
        # путь. И ПРОВЕРЯЕМ, что поле опустело: пустой композер = ушло.
        sent = tab.js("""(() => {
            const b = document.querySelector('button[data-testid="send-button"]')
                   || document.querySelector('#composer-submit-button')
                   || document.querySelector('button[aria-label*="Send"]')
                   || document.querySelector('button[aria-label*="тправ"]');
            if (!b || b.disabled) return false;
            b.click(); return true;
        })()""")
        if not sent:
            tab.key("Enter", "Enter", 13)
        time.sleep(2.5)
        left = tab.js("""(() => { const b = document.querySelector('#prompt-textarea')
                  || document.querySelector("div[contenteditable='true']");
                  return b ? (b.innerText || '').trim().length : -1; })()""")
        if left and left > 10:
            tab.key("Enter", "Enter", 13)   # вторая попытка
            time.sleep(2)
            left = tab.js("""(() => { const b = document.querySelector('#prompt-textarea')
                      || document.querySelector("div[contenteditable='true']");
                      return b ? (b.innerText || '').trim().length : -1; })()""")
            if left and left > 10:
                print(f"  [{job['name']}] НЕ УШЛО (в поле осталось {left} симв.), пропускаю", flush=True)
                continue
        print(f"  [{job['name']}] отправлено", flush=True)

        url = wait_new(tab, seen, job["name"])
        if not url:
            print(f"  [{job['name']}] картинка не появилась", flush=True)
            continue
        if save(tab, url, dst):
            print(f"  [{job['name']}] OK -> {os.path.getsize(dst)//1024} КБ", flush=True)
            done += 1
        else:
            print(f"  [{job['name']}] не скачалась", flush=True)
finally:
    if not tab.resumed:
        tab.close()

print(f"\nготово: {done} из {len(JOBS)}")
