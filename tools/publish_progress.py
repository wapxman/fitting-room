# -*- coding: utf-8 -*-
"""Выложить то, что доснялось: выровнять новые кадры, пересобрать каталог, запушить.

Зачем задачей по расписанию, а не «я прослежу»: матрица снимается часами, а между
сообщениями меня нет. Без планировщика обещание «буду выкладывать по мере
готовности» — пустое (та же причина, что у сторожа выпусков Taketool).

Запускается раз в 20 минут. Если нового нет — молча выходит, коммита не делает.
"""
import os
import subprocess
import sys

# Печать идёт в файл лога через планировщик, а там кодировка cp1251, и первая же
# русская строка роняла скрипт с UnicodeEncodeError — то есть публикация падала
# не по делу, а на выводе о своей же работе.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
AUTHOR = ["-c", "user.email=206386347+wapxman@users.noreply.github.com",
          "-c", "user.name=wapxman"]


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def git(*args):
    return run(["git", *args])


# 1. Выровнять (скрипт сам пропускает уже готовые) и пересобрать каталог.
for step in (["tools/align_frames.py", "frames", "frames_aligned"],
             ["tools/build_manifest.py"]):
    r = run([PY, *step])
    if r.returncode != 0:
        print(f"ОШИБКА на {step[0]}:\n{r.stdout}\n{r.stderr}")
        sys.exit(1)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")

# 2. Есть ли что публиковать.
st = git("status", "--porcelain", "frames_aligned", "assets/outfits.json")
if not st.stdout.strip():
    print("нового нет, выходим")
    sys.exit(0)

changed = len([l for l in st.stdout.splitlines() if l.strip()])
print(f"изменений: {changed}")

# 3. Коммит строго по явным путям — в дереве рядом лежат сырые кадры и логи.
git("add", "frames_aligned", "assets/outfits.json")
msg = run([PY, "-c",
           "import json,io;d=json.load(io.open('assets/outfits.json',encoding='utf-8'));"
           "print(f\"Доснято сочетаний: {d['ready']} из {d['total']}\")"]).stdout.strip()
c = git(*AUTHOR, "commit", "-q", "-m", msg or "Доснятые сочетания",
        "--", "frames_aligned", "assets/outfits.json")
if c.returncode != 0:
    print("коммит не прошёл:", c.stdout, c.stderr)
    sys.exit(1)

git("pull", "--rebase", "-q")
p = git("push", "-q", "origin", "main")
print("push:", "ок" if p.returncode == 0 else f"ОШИБКА {p.stderr[:200]}")
print(msg)
