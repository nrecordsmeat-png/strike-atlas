#!/usr/bin/env python3
"""Механика понятности русского текста.

Грубое приближение к четырём шкалам Гамбургской модели понятности
(Лангер, Шульц фон Тун, Тауш): простота, структура, краткость, стимуляция.
В оригинале модель опирается на оценки людей, здесь только счётные замеры.
Они показывают, ГДЕ смотреть, но не ставят тексту оценку.

Запуск:
    python scripts/mechanics.py текст.txt
    python scripts/mechanics.py текст.txt --json итог.json
Только стандартная библиотека Python 3.8+.
"""
import argparse
import json
import re
import statistics as st
import sys

VOWELS = set("аеёиоуыэюяaeiouy")
WORD = re.compile(r"[а-яёa-z]+(?:-[а-яёa-z]+)*", re.I)

CONNECTIVES = [
    "потому что", "поэтому", "значит", "то есть", "так что", "поскольку",
    "следовательно", "однако", "но", "зато", "хотя", "если", "тогда",
    "например", "скажем", "во-первых", "во-вторых", "итак", "в итоге",
]
ADDRESS = re.compile(r"\b(ты|тебе|тебя|тобой|твой|твоя|твоё|твое|твои|вы|вам|вас|ваш|ваша|ваши|you|your|yours)\b", re.I)
EXAMPLE = re.compile(r"\b(например|скажем|вот|допустим|к примеру)\b", re.I)


def words(s):
    return WORD.findall(s)


def syllables(w):
    return sum(ch in VOWELS for ch in w.lower())


def sentences(text):
    # одиночный перенос строки — не конец предложения; закрывающие кавычки и скобки остаются с предложением
    flat = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    parts = re.split(r"(?<=[.!?…])[»\"”)]*\s+|\n{2,}", flat)
    return [p.strip() for p in parts if words(p)]


def paragraphs(text):
    blocks = [p for p in re.split(r"\n\s*\n", text) if words(p)]
    if len(blocks) <= 1:  # текст без пустых строк — абзацем считается строка
        blocks = [p for p in text.split("\n") if words(p)]
    return blocks


def analyze(text):
    W = words(text)
    n = len(W) or 1
    S = sentences(text)
    L = [len(words(s)) for s in S] or [0]
    paras = paragraphs(text)
    P = [len(words(p)) for p in paras] or [0]
    low = text.lower()
    per1k = lambda c: round(c * 1000 / n, 1)

    long_words = sum(syllables(w) >= 5 for w in W)
    lemmas = [w.lower()[:6] for w in W if len(w) > 3]  # грубая «основа» без морфологии
    repeat = 1 - len(set(lemmas)) / (len(lemmas) or 1)
    conn = {c: len(re.findall(r"\b" + re.escape(c) + r"\b", low)) for c in CONNECTIVES}

    long_sents = [s for s, l in zip(S, L) if l >= 25]
    return {
        "объём": {"слов": len(W), "предложений": len(S), "абзацев": len(paras)},
        "простота": {
            "длина_фразы_медиана": st.median(L),
            "длина_фразы_средняя": round(st.mean(L), 1),
            "доля_фраз_от_25_слов_%": round(100 * len(long_sents) / (len(S) or 1)),
            "доля_длинных_слов_5+_слогов_%": round(100 * long_words / n, 1),
            "самые_длинные_фразы": [x[:200] + ("…" if len(x) > 200 else "") for x in sorted(long_sents, key=len, reverse=True)[:3]],
        },
        "структура": {
            "слов_на_абзац_медиана": st.median(P),
            "самый_длинный_абзац_слов": max(P),
            "связки_на_1000": per1k(sum(conn.values())),
            "связки": {k: v for k, v in conn.items() if v},
        },
        "краткость": {
            "повтор_основ_%": round(100 * repeat, 1),
        },
        "стимуляция": {
            "вопросы_на_1000": per1k(text.count("?")),
            "обращения_на_1000": per1k(len(ADDRESS.findall(text))),
            "примеры_на_1000": per1k(len(EXAMPLE.findall(text))),
            "восклицания_на_1000": per1k(text.count("!")),
        },
    }


HINTS = [
    ("простота", "длина_фразы_медиана", 15, "фразы длинные для живого текста"),
    ("простота", "доля_фраз_от_25_слов_%", 10, "много фраз от 25 слов"),
    ("простота", "доля_длинных_слов_5+_слогов_%", 8, "много длинных слов: возможен канцелярит"),
    ("структура", "самый_длинный_абзац_слов", 150, "есть абзац длиннее 150 слов"),
]


def report(r):
    out = []
    o = r["объём"]
    out.append(f"Объём: {o['слов']} слов, {o['предложений']} предложений, {o['абзацев']} абзацев")
    for block in ("простота", "структура", "краткость", "стимуляция"):
        out.append(f"\n[{block}]")
        for k, v in r[block].items():
            if isinstance(v, list):
                for s in v:
                    out.append(f"  длинная фраза: {s[:140]}{'…' if len(s) > 140 else ''}")
            else:
                out.append(f"  {k.replace('_', ' ')}: {v}")
    flags = [msg for blk, key, lim, msg in HINTS if r[blk][key] > lim]
    out.append("\nНа что посмотреть: " + ("; ".join(flags) if flags else "явных механических проблем нет"))
    out.append("Это счётные замеры, а не оценка мысли. Понятность смысла проверяется пересказом.")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("--json", help="сохранить результат в JSON")
    a = ap.parse_args()
    raw = open(a.text, "rb").read()
    try:
        t = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = raw.decode("cp1251")
    if not words(t):
        sys.exit("Текст пуст: считать нечего.")
    r = analyze(t)
    print(report(r))
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
