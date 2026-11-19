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
import sys
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

from html.parser import HTMLParser


class _TgHTML(HTMLParser):
    """Разбирает экспорт Telegram в HTML деревом: границы сообщения, отправитель, узел текста.
    Реакции, цитаты, пересланное и служебные блоки в текст не попадают."""
    SKIP = {"reactions", "reaction", "blockquote", "reply_to", "forwarded", "media_wrap", "signature", "details"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.msgs, self.stack, self.cur, self.last_from = [], [], None, None
        self.mode = None  # "from" | "text"
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        cls = set((dict(attrs).get("class") or "").split())
        if tag in ("br",):
            if self.mode == "text" and not self.skip_depth:
                self.cur["text"] += "\n"
            return
        self.stack.append((tag, cls))
        if tag == "div" and {"message", "default"} <= cls:
            self.cur = {"from": self.last_from, "text": "", "fwd": False, "depth": len(self.stack)}
        if self.cur is None:
            return
        if "forwarded" in cls:
            self.cur["fwd"] = True
        if self.skip_depth or tag == "blockquote" or cls & self.SKIP:
            self.skip_depth += 1
            return
        if tag == "div" and "from_name" in cls:
            self.mode, self.cur["_from"] = "from", ""
        elif tag == "div" and "text" in cls and self.mode is None:
            self.mode = "text"
            self.cur["_tdepth"] = len(self.stack)

    def handle_endtag(self, tag):
        if tag == "br" or not self.stack:
            return
        depth = len(self.stack)
        self.stack.pop()
        if self.cur is None:
            return
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if self.mode == "from" and tag == "div":
            name = self.cur.pop("_from", "").strip()
            if name:
                self.cur["from"] = self.last_from = name
            self.mode = None
        elif self.mode == "text" and tag == "div" and depth == self.cur.get("_tdepth"):
            self.mode = None
        if depth == self.cur["depth"]:
            if self.cur["text"].strip() and not self.cur["fwd"]:
                self.msgs.append({"from": self.cur["from"], "from_id": None, "text": self.cur["text"].strip()})
            self.cur = None

    def handle_data(self, data):
        if self.cur is None or self.skip_depth:
            return
        if self.mode == "from":
            self.cur["_from"] += data
        elif self.mode == "text":
            self.cur["text"] += data


def read_html(folder):
    files = sorted(glob.glob(os.path.join(folder, "messages*.html")), key=lambda f: (len(f), f))
    out = []
    for f in files:
        p = _TgHTML()
        p.feed(open(f, encoding="utf-8-sig").read())
        out += p.msgs
    return out


def read_json(path):
    data = json.load(open(path, encoding="utf-8-sig"))
    if "messages" not in data:
        if "chats" in data:
            raise SystemExit("Это полный экспорт аккаунта. Нужен экспорт одного чата или канала: "
                             "открой чат в Telegram Desktop → три точки → «Экспорт истории чата».")
        raise SystemExit("В result.json нет списка messages: формат не распознан.")
    out = []
    for m in data["messages"]:
        if m.get("type") != "message" or m.get("forwarded_from"):
            continue
        t = m.get("text")
        if isinstance(t, list):
            t = "".join(x if isinstance(x, str) else ("" if x.get("type") == "blockquote" else x.get("text", "")) for x in t)
        if t and t.strip():
            out.append({"from": m.get("from"), "from_id": m.get("from_id"), "text": t.strip()})
    return out


def pick_author(msgs, author):
    """Выбор автора: по from_id, если он есть; по имени — только если имя однозначно."""
    if not author:
        return [m["text"] for m in msgs]
    by_id = [m for m in msgs if m.get("from_id") == author]
    if by_id:
        return [m["text"] for m in by_id]
    named = [m for m in msgs if m.get("from") == author]
    ids = {m.get("from_id") for m in named if m.get("from_id")}
    if len(ids) > 1:
        raise SystemExit(f"Имя {author!r} носят несколько участников: {', '.join(sorted(ids))}. "
                         "Укажи --author с нужным from_id.")
    if ids:  # имя однозначно — берём все сообщения этого ID, даже после смены имени
        the_id = ids.pop()
        return [m["text"] for m in msgs if m.get("from_id") == the_id]
    if named:
        print("Внимание: в HTML-экспорте нет ID участников, тёзок различить нельзя.", file=sys.stderr)
    return [m["text"] for m in named]


def clean(msg):
    msg = re.sub(r"https?://\S+", "", msg)
    # длинная цитата — внутри одной строки; кавычки на разных строках не склеиваются в одну «цитату»
    msg = re.sub(r"«[^»\n]{40,400}»", "", msg)
    msg = re.sub(r'"[^"\n]{40,400}"', "", msg)
    return "\n".join(l for l in msg.split("\n") if not re.match(r"^\s*[\U0001F1E6-\U0001F1FF]{2}", l))


MIN_WORDS = 2000  # меньше — эталон не строится: нужно хотя бы 4 блока по 500 слов


def build(folder, author, out, mfw_n=150, chunk=500):
    j = os.path.join(folder, "result.json")
    msgs = read_json(j) if os.path.exists(j) else read_html(folder)
    texts = pick_author(msgs, author)
    if not texts:
        raise SystemExit("Не нашёл сообщений. Проверь папку и, для переписки, имя или from_id в --author.")
    text = "\n".join(clean(m) for m in texts)
    W = tok(text)
    if len(W) < MIN_WORDS:
        raise SystemExit(f"Эталон не построен: {len(W)} слов, нужно не меньше {MIN_WORDS}.")
    cnt = Counter(W)
    chunks = [W[i:i + chunk] for i in range(0, len(W) - chunk + 1, chunk)]
    in_chunks = Counter(w for c in chunks for w in set(c))
    # в словарь эталона попадают только частые слова, встречающиеся минимум в двух блоках: редкие и личные слова не сохраняются
    mfw = [w for w, c in cnt.most_common() if c >= 5 and in_chunks[w] >= 2][:mfw_n]
    freqs = [[Counter(c)[w] / len(c) for w in mfw] for c in chunks]
    mu = [st.mean(col) for col in zip(*freqs)]
    sd = [st.pstdev(col) for col in zip(*freqs)]
    keep = [i for i, v in enumerate(sd) if v > 0]
    mfw, mu, sd, freqs = [mfw[i] for i in keep], [mu[i] for i in keep], [sd[i] for i in keep], [[f[i] for i in keep] for f in freqs]
    if len(mfw) < 20:
        raise SystemExit("Эталон не построен: слишком мало слов с разбросом между блоками.")
    own = sorted(st.mean(abs((f - m) / s) for f, m, s in zip(fr, mu, sd)) for fr in freqs)
    prof = {"сообщений": len(texts), "слов": len(W), "приметы": count_markers(text),
            "mfw": mfw, "mu": mu, "sd": sd, "chunk": chunk, "own_delta": own}
    json.dump(prof, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Эталон: {len(texts)} сообщений, {len(W)} слов → {out}")
    if len(W) < 20000:
        print("Внимание: меньше 20 000 слов, эталон слабый.")


def compare(textfile, proffile, jout=None):
    raw = open(textfile, "rb").read()
    try:
        t = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = raw.decode("cp1251")
    t = clean(t)  # та же очистка, что при построении эталона
    P = json.load(open(proffile, encoding="utf-8"))
    W = tok(t)
    if not W:
        raise SystemExit("Текст пуст после очистки: сравнивать нечего.")
    mine, ref = count_markers(t), P["приметы"]
    nsent = len([s for s in re.split(r"(?<=[.!?…])\s+|\n+", t) if tok(s)])
    rows, flags = [], []
    low = t.lower()
    for k in ref:
        a, b = ref[k], mine[k]
        rows.append((k, a, b))
        if k.startswith("длина"):
            continue
        expected = a * nsent / 100 if k.endswith("%") else a * len(W) / 1000
        seen = b * (nsent / 100 if k.endswith("%") else len(W) / 1000)  # сколько раз примета реально встретилась
        if b == 0 and expected >= 2:
            flags.append(f"пропало: {k} (у автора {a}, в тексте 0; ожидалось около {round(expected)} раз)")
        elif seen >= 2 and a < 0.5 and b >= 2:
            flags.append(f"чужое: {k} (у автора почти нет, в тексте {round(seen)} раз)")
        elif seen >= 2 and b >= 2 and b >= 3 * max(a, 0.3):
            flags.append(f"перебор: {k} (у автора {a}, в тексте {b}, это {round(seen)} раз)")
    pct = None
    if len(W) >= P.get("chunk", 500) and len(P.get("own_delta", [])) >= 4:
        c = Counter(W)
        z = [abs((c[w] / len(W) - m) / s) for w, m, s in zip(P["mfw"], P["mu"], P["sd"]) if s > 0]
        d = st.mean(z)
        pct = round(100 * sum(x < d for x in P["own_delta"]) / len(P["own_delta"]))
    print(f"{'примета (на 1000 слов)':38s}{'автор':>8s}{'текст':>8s}")
    for k, a, b in rows:
        print(f"{k:38s}{a:8}{b:8}")
    print("\nРасхождения с голосом автора (эвристика, пороги не валидированы):")
    print("\n".join("  " + f for f in flags) if flags else "  заметных нет")
    if pct is None:
        print(f"\nОбщая непохожесть не считается: текст короче {P.get('chunk', 500)} слов или эталон слишком мал.")
    else:
        print(f"\nОбщая непохожесть: дальше, чем {pct}% блоков самого эталона (эвристика; эти же блоки задают норму)")
    if jout:
        json.dump({"приметы": [{"имя": k, "автор": a, "текст": b} for k, a, b in rows],
                   "расхождения": flags, "дельта_перцентиль": pct, "слов": len(W)},
                  open(jout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="собрать эталон из выгрузки Telegram")
    b.add_argument("folder")
    b.add_argument("--author", help="from_id или имя автора для переписки, как в выгрузке")
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
