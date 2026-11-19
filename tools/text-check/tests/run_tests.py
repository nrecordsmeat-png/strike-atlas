#!/usr/bin/env python3
"""Контрольные тесты text-check. Запуск: python tests/run_tests.py
Покрывают входы из внешней рецензии: порча отчёта при ошибке, перенос отметок, перевёрнутая причинность,
тёзки в Telegram, пустые и маленькие данные, разметка фраз, подстановки в тексте, обязательные поля.
Если установлен playwright с браузером, дополнительно проверяется поведение карты в браузере.
Только стандартная библиотека (playwright необязателен)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts")
PY = sys.executable
OK, FAIL = 0, []


def run(*args):
    return subprocess.run([PY, *args], capture_output=True, text=True)


def check(name, cond):
    global OK
    if cond:
        OK += 1
        print("ok  ", name)
    else:
        FAIL.append(name)
        print("FAIL", name)


def w(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))


with tempfile.TemporaryDirectory() as d:
    J = lambda n: os.path.join(d, n)

    # --- report.py: ошибка входа не трогает готовый файл
    w(J("old.html"), "<p>старый</p>")
    for name, data in {
        "лишние отметки (200%)": {"readers": [{"name": "A", "marks": ["+", "+"]}], "checkpoints": ["x"]},
        "пустые читатели": {"readers": [], "checkpoints": ["x"]},
        "неизвестный знак": {"readers": [{"name": "A", "marks": ["%"]}], "checkpoints": ["x"]},
        "счётчик пробела больше числа читателей": {"readers": [{"name": "A", "marks": ["+"]}], "checkpoints": ["x"],
                                                   "gaps": [{"place": "q", "count": 5}]},
    }.items():
        w(J("bad.json"), data)
        r = run(os.path.join(S, "report.py"), J("bad.json"), "--out", J("old.html"))
        check(f"report: {name} → ошибка, файл цел", r.returncode != 0 and open(J("old.html")).read() == "<p>старый</p>")

    # --- report.py: перевёрнутая причинность различима при записанных основаниях
    base = {"checkpoints": ["звонок → отправка"], "readers": [{"name": "A", "marks": [{"m": "+", "evidence": "Звонок помог отправить ящик"}]}]}
    rev = {"checkpoints": ["звонок → отправка"], "readers": [{"name": "A", "marks": [{"m": "x", "evidence": "Ящик уже отправили, поэтому позвонили"}]}]}
    w(J("a.json"), base); w(J("b.json"), rev)
    run(os.path.join(S, "report.py"), J("a.json"), "--out", J("a.html"))
    run(os.path.join(S, "report.py"), J("b.json"), "--out", J("b.html"))
    check("report: прямая и обратная причинность дают разные отчёты", open(J("a.html")).read() != open(J("b.html")).read())
    w(J("c.json"), {"checkpoints": ["x"], "readers": [{"name": "A", "marks": ["+"]}]})
    run(os.path.join(S, "report.py"), J("c.json"), "--out", J("c.html"))
    check("report: без протокола отчёт предупреждает", "нельзя перепроверить" in open(J("c.html")).read())

    # --- зеркало: ключ отметки — содержание тезиса
    def mirror(chain):
        w(J("m.json"), {"mode": "mirror", "title": "T", "readers": [{"name": "A", "main": "m"}], "chain": chain})
        run(os.path.join(S, "report.py"), J("m.json"), "--out", J("m.html"))
        return open(J("m.html")).read()
    h1 = mirror([{"point": "Звонок", "count": 1}])
    h2 = mirror([{"point": "Отметка", "count": 1}])
    import re
    id1 = re.search(r'class="pt" data-id="(\w+)"', h1).group(1)
    id2 = re.search(r'class="pt" data-id="(\w+)"', h2).group(1)
    check("зеркало: другой тезис на том же месте — другой ключ отметки", id1 != id2)
    check("зеркало: при отказе буфера нет ложного «Скопировано»", "вручную" in h1)

    # --- roots_map.py
    w(J("t.txt"), "До. Здесь. После. Здесь. Потом.\nСтрока один\nстрока два. __AUTHOR__ /*__PAYLOAD__*/ тут.")
    w(J("r.json"), {"title": "т", "author_reading": "АВТОР", "roots": [
        {"thesis": "1", "fragments": ["Здесь"], "sources": [{"who": "X", "relation": "совпадает", "year": 1900}]},
        {"thesis": "2", "fragments": [{"text": "Здесь", "occurrence": 2}], "contested": "false",
         "sources": [{"who": "Y", "relation": "расходится"}]},
        {"thesis": "3", "implicit": True, "fragments": ["нет такой"], "sources": []}]})
    r = run(os.path.join(S, "roots_map.py"), J("t.txt"), J("r.json"), "--out", J("map.html"), "--json-out", J("rep.json"))
    check("карта: собирается с предупреждениями", r.returncode == 0)
    check("карта: предупреждает о пропущенном meaning", "meaning" in r.stderr)
    check("карта: предупреждает о contested-строке", "contested" in r.stderr)
    check("карта: предупреждает о ненайденной фразе", "не найдена" in r.stderr)
    check("карта: невысказанный тезис без читателей помечен", "гипотеза координатора" in r.stderr)
    rep = json.load(open(J("rep.json")))
    check("карта: текст пользователя не тронут подстановками", "__AUTHOR__ /*__PAYLOAD__*/" in rep["text"])
    w(J("r2.json"), {"roots": [{"thesis": "1", "sources": [{"who": "X", "relation": "непонятно"}]}]})
    w(J("map2.html"), "старая")
    r = run(os.path.join(S, "roots_map.py"), J("t.txt"), J("r2.json"), "--out", J("map2.html"))
    check("карта: неизвестное отношение → ошибка, файл цел", r.returncode != 0 and open(J("map2.html")).read() == "старая")

    # --- voice.py
    os.makedirs(J("tg")); os.makedirs(J("acc"))
    words = "и в не на я что он с как это но а то все так его она вот ну да было уже еще только можно очень когда даже".split()
    import random
    random.seed(1)
    msgs = [{"type": "message", "from": "Саша", "from_id": "user1", "text": " ".join(random.choice(words) for _ in range(12))} for _ in range(400)]
    msgs.append({"type": "message", "from": "Саша", "from_id": "user2", "text": "чужоеслово второго"})
    msgs.append({"type": "message", "from": "Саша Н.", "from_id": "user1", "text": "после смены имени"})
    w(os.path.join(J("tg"), "result.json"), {"messages": msgs})
    w(os.path.join(J("acc"), "result.json"), {"chats": {"list": []}})
    r = run(os.path.join(S, "voice.py"), "build", J("tg"), "--author", "Саша", "--out", J("p.json"))
    check("голос: тёзки с разными ID → отказ с подсказкой", r.returncode != 0 and "user1" in (r.stderr + r.stdout))
    r = run(os.path.join(S, "voice.py"), "build", J("tg"), "--author", "user1", "--out", J("p.json"))
    p = json.load(open(J("p.json")))
    check("голос: выбор по from_id, чужое слово не в эталоне", r.returncode == 0 and "чужоеслово" not in p["mfw"])
    r = run(os.path.join(S, "voice.py"), "build", J("acc"), "--out", J("x.json"))
    check("голос: полный экспорт аккаунта → понятная ошибка", r.returncode != 0 and "аккаунта" in (r.stderr + r.stdout))
    w(J("e.txt"), "")
    r = run(os.path.join(S, "voice.py"), "compare", J("e.txt"), J("p.json"))
    check("голос: пустой текст → отказ без процентиля", r.returncode != 0)
    w(J("nu.txt"), "Ну?")
    r = run(os.path.join(S, "voice.py"), "compare", J("nu.txt"), J("p.json"))
    check("голос: «Ну?» — без флагов «чужое» и без процентиля", "чужое" not in r.stdout and "не считается" in r.stdout)
    small = {"messages": msgs[:30]}
    os.makedirs(J("small")); w(os.path.join(J("small"), "result.json"), small)
    r = run(os.path.join(S, "voice.py"), "build", J("small"), "--author", "user1", "--out", J("s.json"))
    check("голос: эталон меньше 2000 слов не строится", r.returncode != 0)

    # --- voice.py: HTML-экспорт — реакции, цитаты и пересланное не попадают в текст
    os.makedirs(J("tgh"))
    one = ('<div class="message default clearfix" id="m{i}"><div class="body"><div class="from_name">Аня</div>'
           '<div class="text" lang="ru">{t}</div><div class="reactions"><span class="reaction">РЕАКЦИЯМЕТКА</span></div></div></div>')
    fwd = ('<div class="message default clearfix"><div class="body"><div class="forwarded body"><div class="from_name">Чужой</div>'
           '<div class="text">ПЕРЕСЛАННОЕСЛОВО</div></div></div></div>')
    body = "".join(one.format(i=i, t=" ".join(random.choice(words) for _ in range(12)) + (" секретныймаркер" if i == 0 else "")) for i in range(300))
    w(os.path.join(J("tgh"), "messages.html"), "<html><body><div class='history'>" + fwd + body + "</div></body></html>")
    r = run(os.path.join(S, "voice.py"), "build", J("tgh"), "--author", "Аня", "--out", J("ph.json"))
    ph = json.load(open(J("ph.json"))) if r.returncode == 0 else {"mfw": [], "сообщений": 0}
    check("голос HTML: атрибуты у узла текста не мешают разбору", r.returncode == 0 and ph["сообщений"] == 300)
    check("голос HTML: реакции и пересланное не в эталоне", all(x not in ph["mfw"] for x in ("реакцияметка", "пересланноеслово", "секретныймаркерреакцияметка")))

    # --- mechanics.py
    r = run(os.path.join(S, "mechanics.py"), J("e.txt"))
    check("механика: пустой текст → отказ", r.returncode != 0)
    w(J("q.txt"), "Он спросил: «Когда?» Потом ушёл.\nYou and you.")
    r = run(os.path.join(S, "mechanics.py"), J("q.txt"), "--json", J("q.json"))
    q = json.load(open(J("q.json")))
    check("механика: кавычка после вопроса — граница предложения", q["объём"]["предложений"] == 3)
    check("механика: английские обращения считаются", q["стимуляция"]["обращения_на_1000"] > 0)
    with open(J("cp.txt"), "wb") as f:
        f.write("Текст в кодировке Windows. Второе предложение.".encode("cp1251"))
    r = run(os.path.join(S, "mechanics.py"), J("cp.txt"))
    check("механика: Windows-1251 читается", r.returncode == 0)

    # --- браузер (необязательно)
    try:
        from playwright.sync_api import sync_playwright
        exe = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(p)), None)
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else pw.chromium.launch()
            pg = b.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("file://" + J("map.html"))
            marks = pg.eval_on_selector_all("mark.fr", "e=>e.map(x=>x.dataset.ts)")
            check("браузер: без ошибок JS", not errs)
            check("браузер: второе вхождение «Здесь» отмечено вторым тезисом", marks[:2] == ["0", "1"])
            check("браузер: текст с метками шаблона показан как есть", "__AUTHOR__" in pg.inner_text("#text"))
            b.close()
    except ImportError:
        print("skip браузерные тесты: playwright не установлен")

print(f"\nПройдено: {OK}, провалено: {len(FAIL)}")
sys.exit(1 if FAIL else 0)
