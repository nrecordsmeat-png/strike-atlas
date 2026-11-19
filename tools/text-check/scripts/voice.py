#!/usr/bin/env python3
"""Голос автора: эталон из выгрузки Telegram и сверка текста с ним.

1) Собрать эталон (канал или переписка, выгрузка Telegram Desktop в HTML или JSON):
    python scripts/voice.py build ПАПКА_ВЫГРУЗКИ --out profile_channel.json
    python scripts/voice.py build ПАПКА_ВЫГРУЗКИ --author "Roman" --out profile_chat.json
   --author нужен для переписки: берутся только сообщения этого человека.
   Пересланные сообщения и цитаты (blockquote, «длинные кавычки») отбрасываются.

2) Сверить текст с эталоном:
    python scripts/voice.py compare текст.txt profile_channel.json
    python scripts/voice.py compare текст.txt profile_channel.json --json итог.json

Приметы стабильны на любом объёме. Общий показатель «похоже на автора»
(дельта Берроуза) на текстах короче ~2000 слов ненадёжен, он печатается с этой оговоркой.
Только стандартная библиотека Python 3.8+.
"""
import argparse
import glob
import html
import json
import os
import re
import statistics as st
from collections import Counter

WORD = re.compile(r"[а-яёa-z]+")
tok = lambda s: [w.replace("ё", "е") for w in WORD.findall(s.lower())]

# имя: (регулярка, по чему искать: low = текст в нижнем регистре, raw = как есть)
MARKERS = {
    "дефис-тире « - »": (r" - ", "raw"),
    "длинное тире —/–": (r"[–—]", "raw"),
    "двоеточие": (r":", "raw"),
    "кавычки «ёлочки»": (r"«", "raw"),
    'кавычки прямые ""': (r'"', "raw2"),
    "многоточие": (r"\.\.\.|…", "raw"),
    "вопрос": (r"\?", "raw"),
    "восклицание": (r"!", "raw"),
    "смайл-скобка )": (r"(?<![\w(])\)+(?=\s|$)", "raw"),
    "буква ё": (r"ё", "low"),
    "не X, а Y": (r"\bне\s+\w+[^.!?\n]{0,30},\s*а\s", "low"),
    "то есть": (r"\bто есть\b", "low"),
    "ну": (r"\bну\b", "low"),
    "вот": (r"\bвот\b", "low"),
    "просто": (r"\bпросто\b", "low"),
    "вообще": (r"\bвообще\b", "low"),
    "типа": (r"\bтипа\b", "low"),
    "как бы": (r"\bкак бы\b", "low"),
    "книжные связки": (r"\b(таким образом|более того|разумеется|ключев\w+|следовательно|тем самым)\b", "low"),
    "мат": (r"\b(бля\w*|ху[йеия]\w*|нахуй|нахуя|пизд\w*|[её]ба\w*|[её]бу\w*|заеб\w*|мудак\w*|сука)\b", "low"),
}
STARTS = ["и", "а", "но", "ну", "да", "вот", "это", "так"]


def count_markers(text):
    n = len(tok(text)) or 1
    low = text.lower()
    res = {}
    for name, (rx, mode) in MARKERS.items():
        src = low if mode == "low" else text
        c = len(re.findall(rx, src))
        if mode == "raw2":
            c //= 2
        res[name] = round(c * 1000 / n, 2)
    sents = [s for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if tok(s)]
    L = [len(tok(s)) for s in sents] or [0]
    res["длина фразы, медиана"] = st.median(L)
    first = Counter(tok(s)[0] for s in sents)
    for w in STARTS:
        res[f"фраза начинается с «{w}», %"] = round(100 * first[w] / (len(sents) or 1), 1)
    return res


# ---------- чтение выгрузок Telegram ----------

def _strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<blockquote.*?</blockquote>", "", s, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def read_html(folder, author):
    files = sorted(glob.glob(os.path.join(folder, "messages*.html")), key=lambda f: (len(f), f))
    out, last = [], None
    for f in files:
        src = open(f, encoding="utf-8").read()
        for m in re.split(r'<div class="message default', src)[1:]:
            fn = re.search(r'<div class="from_name">\s*(.*?)\s*</div>', m, re.S)
            if fn:
                last = _strip_tags(fn.group(1)).strip()
            if 'class="forwarded' in m:
                continue
            t = re.search(r'<div class="text">(.*?)</div>\s*(?:<div class="(?:reply|signature|media|photo)|</div>)', m, re.S)
            if not t:
                continue
            if author and (last or "").strip() != author:
                continue
            txt = _strip_tags(t.group(1)).strip()
            if txt:
                out.append(txt)
    return out


def read_json(path, author):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for m in data.get("messages", []):
        if m.get("type") != "message" or m.get("forwarded_from"):
            continue
        if author and m.get("from") != author:
            continue
        t = m.get("text")
        if isinstance(t, list):
            t = "".join(x if isinstance(x, str) else ("" if x.get("type") == "blockquote" else x.get("text", "")) for x in t)
        if t and t.strip():
            out.append(t.strip())
    return out


def clean(msg):
    msg = re.sub(r"https?://\S+", "", msg)
    msg = re.sub(r"«[^»]{40,}»", "", msg, flags=re.S)
    msg = re.sub(r'"[^"]{40,}"', "", msg, flags=re.S)
    return "\n".join(l for l in msg.split("\n") if not re.match(r"^\s*[\U0001F1E6-\U0001F1FF]{2}", l))


def build(folder, author, out, mfw_n=150, chunk=500):
    j = os.path.join(folder, "result.json")
    msgs = read_json(j, author) if os.path.exists(j) else read_html(folder, author)
    if not msgs:
        raise SystemExit("Не нашёл сообщений. Проверь папку и, для переписки, точное имя в --author.")
    text = "\n".join(clean(m) for m in msgs)
    W = tok(text)
    mfw = [w for w, _ in Counter(W).most_common(mfw_n)]
    chunks = [W[i:i + chunk] for i in range(0, len(W) - chunk + 1, chunk)]
    freqs = [[Counter(c)[w] / len(c) for w in mfw] for c in chunks]
    mu = [st.mean(col) for col in zip(*freqs)]
    sd = [st.pstdev(col) + 1e-9 for col in zip(*freqs)]
    own = sorted(st.mean(abs((f - m) / s) for f, m, s in zip(fr, mu, sd)) for fr in freqs)
    prof = {"сообщений": len(msgs), "слов": len(W), "приметы": count_markers(text),
            "mfw": mfw, "mu": mu, "sd": sd, "chunk": chunk, "own_delta": own}
    json.dump(prof, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Эталон: {len(msgs)} сообщений, {len(W)} слов → {out}")
    if len(W) < 20000:
        print("Внимание: меньше 20 000 слов, эталон слабый.")


def compare(textfile, proffile, jout=None):
    t = open(textfile, encoding="utf-8").read()
    P = json.load(open(proffile, encoding="utf-8"))
    mine, ref = count_markers(t), P["приметы"]
    W = tok(t)
    nsent = len([s for s in re.split(r"(?<=[.!?…])\s+|\n+", t) if tok(s)])
    rows, flags = [], []
    for k in ref:
        a, b = ref[k], mine[k]
        rows.append((k, a, b))
        if k.startswith("длина"):
            continue
        # сколько раз примета ожидалась в тексте такого объёма
        expected = a * nsent / 100 if k.endswith("%") else a * len(W) / 1000
        if b == 0 and expected >= 2:
            flags.append(f"пропало: {k} (у автора {a}, в тексте 0; ожидалось около {round(expected)} раз)")
        elif a < 0.5 and b >= 2:
            flags.append(f"чужое: {k} (у автора почти нет, в тексте {b})")
        elif b >= 2 and b >= 3 * max(a, 0.3):
            flags.append(f"перебор: {k} (у автора {a}, в тексте {b})")
    c = Counter(W)
    z = [abs((c[w] / (len(W) or 1) - m) / s) for w, m, s in zip(P["mfw"], P["mu"], P["sd"])]
    d = st.mean(z)
    pct = round(100 * sum(x < d for x in P["own_delta"]) / len(P["own_delta"]))
    print(f"{'примета (на 1000 слов)':38s}{'автор':>8s}{'текст':>8s}")
    for k, a, b in rows:
        print(f"{k:38s}{a:8}{b:8}")
    print("\nРасхождения с голосом автора:")
    print("\n".join("  " + f for f in flags) if flags else "  заметных нет")
    note = "" if len(W) >= 2000 else " (текст короче 2000 слов: показатель ненадёжен)"
    print(f"\nОбщая непохожесть: дальше, чем {pct}% кусков самого автора{note}")
    if jout:
        json.dump({"приметы": [{"имя": k, "автор": a, "текст": b} for k, a, b in rows],
                   "расхождения": flags, "дельта_перцентиль": pct, "слов": len(W)},
                  open(jout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="собрать эталон из выгрузки Telegram")
    b.add_argument("folder")
    b.add_argument("--author", help="имя автора для переписки, как в выгрузке")
    b.add_argument("--out", default="profile.json")
    c = sub.add_parser("compare", help="сверить текст с эталоном")
    c.add_argument("text")
    c.add_argument("profile")
    c.add_argument("--json")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.folder, a.author, a.out)
    else:
        compare(a.text, a.profile, a.json)
