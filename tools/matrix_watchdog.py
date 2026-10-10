# -*- coding: utf-8 -*-
"""Сторож съёмки матрицы: поднимает её, если упала, и пинает, если встала.

Зачем. Съёмка 108 кадров идёт часами, а между сообщениями меня нет. За первый
же час она вставала дважды по разным причинам (Enter не отправлял текст;
кнопка отправки заблокирована, пока ChatGPT дописывает ответ). Без сторожа
Создатель нашёл бы утром 11 кадров из 108 — и моё «будет наполняться само»
оказалось бы неправдой.

Что считает нездоровьем:
  — процесса gpt_turntable нет, а неснятые кадры остались  -> запустить;
  — процесс есть, но НОВЫХ кадров нет дольше STALL_MIN     -> убить и запустить.

Второе важнее первого: повисший процесс выглядит живым и тем опаснее — он
занимает место и ничего не делает.
"""
import os
import subprocess
import sys
import time

for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = r"C:\Users\User\browser-tools\gpt_turntable.py"
JOBS = os.path.join(ROOT, "jobs_matrix.json")
FRAMES = os.path.join(ROOT, "frames")
STALL_MIN = 9          # дольше этого без нового кадра — считаем, что встало
TOTAL = 108


def pids():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "Where-Object { $_.CommandLine -match 'gpt_turntable' } | "
         "Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def shot_count_and_age():
    newest, n = 0.0, 0
    for d, _, fs in os.walk(FRAMES):
        for f in fs:
            if f.endswith(".png"):
                n += 1
                newest = max(newest, os.path.getmtime(os.path.join(d, f)))
    return n, (time.time() - newest) / 60 if newest else 1e9


def start():
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process python -ArgumentList '{GEN}','jobs_matrix.json','frames',"
         f"'assets\\reference.jpg','--resume' -WorkingDirectory '{ROOT}' "
         f"-WindowStyle Hidden -RedirectStandardOutput '{ROOT}\\matrix2.log' "
         f"-RedirectStandardError '{ROOT}\\matrix2.err'"],
        capture_output=True, text=True)


n, age = shot_count_and_age()
alive = pids()
print(f"кадров {n}/{TOTAL}, последний {age:.1f} мин назад, процессов {len(alive)}")

if n >= TOTAL:
    print("матрица снята полностью — сторож больше не нужен")
    sys.exit(0)

if not alive:
    print("процесса нет -> запускаю")
    start()
elif age > STALL_MIN:
    print(f"встало ({age:.1f} мин без новых кадров) -> перезапускаю")
    for p in alive:
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    time.sleep(3)
    start()
else:
    print("идёт штатно")
