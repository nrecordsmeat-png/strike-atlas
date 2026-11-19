#!/usr/bin/env python3
"""Интерактивная карта корней мысли для любого текста.

    python scripts/roots_map.py текст.txt roots.json --out карта.html

Слева текст с подсвеченными фрагментами, справа график по времени: мыслители и
исследования, с которыми эти фрагменты в родстве. Щелчок по фрагменту подсвечивает
его источники, щелчок по источнику подсвечивает фрагмент. Карточка «у него / у тебя»
показывает совпадение или развилку. Сверху сводка: сколько веков и традиций задето.

Что нужно в roots.json сверх обычного блока roots (см. examples/roots.json):
  у тезиса:    "fragments": ["точная цитата из текста", ...]
  у источника: "year": -450, "year_label": "V в. до н. э.", "tradition": "буддизм"
  в корне файла: "meaning": "что текст говорит, одной-двумя фразами, без оценки"
  линзы мировоззрения: "lenses": [{"id","name","meaning","against"}], у источника "lens": "<id>"
  прочтение автора: "author_reading": "..."
  у спорного тезиса: "contested": true — карта предупредит, если корни найдены только с одной стороны
Фрагмент ищется в тексте как есть, затем без учёта регистра и разницы е/ё.
Ненайденные фрагменты печатаются предупреждением.
Карта строится общим просмотрщиком viewer/roots_view.html: тот же файл показывает
отчёты на сайте (?report=файл.json). Разметка текста делается в браузере.
ВНИМАНИЕ: в карту целиком встраивается сам текст. Не выкладывай её публично, если текст личный.
Только стандартная библиотека Python 3.8+.
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, "..", "viewer", "roots_view.html")
TOKEN = "/*__PAYLOAD__*/null"
RELATIONS = {"совпадает", "развивает", "перекликается", "расходится"}
STATUSES = {"not_searched", "searched_not_found", "searched_not_found_opposite", "found"}


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    sys.exit(f"Не удалось прочитать {path}: кодировка не UTF-8 и не Windows-1251")


def validate(R, text):
    """Возвращает (ошибки, предупреждения). Ошибки останавливают сборку, предупреждения показываются и в карте."""
    err, warn = [], []
    roots = R.get("roots")
    if not isinstance(roots, list) or not roots:
        err.append("нет списка roots")
        return err, warn
    if not R.get("meaning"):
        warn.append("не указан meaning — смысл текста")
    low = text.lower().replace("ё", "е")
    for i, t in enumerate(roots, 1):
        if not t.get("thesis"):
            err.append(f"тезис {i}: нет поля thesis")
        if "contested" in t and not isinstance(t["contested"], bool):
            warn.append(f"тезис {i}: contested={t['contested']!r} не true/false, будет считаться false")
        st = (t.get("search") or {}).get("status")
        if st and st not in STATUSES:
            err.append(f"тезис {i}: неизвестный search.status {st!r}")
        if not t.get("sources") and not st:
            warn.append(f"тезис {i}: нет источников и не записан статус поиска")
        if t.get("implicit") and not t.get("from_readers"):
            warn.append(f"тезис {i}: невысказанный тезис без from_readers будет показан как гипотеза координатора")
        for f in t.get("fragments", []):
            fx = f if isinstance(f, str) else (f or {}).get("text", "")
            if fx and fx.lower().replace("ё", "е") not in low:
                warn.append(f"тезис {i}: фраза не найдена в тексте: {fx[:60]}")
        for s in t.get("sources", []):
            if s.get("relation") not in RELATIONS:
                err.append(f"тезис {i}: у источника {s.get('who')!r} неизвестное отношение {s.get('relation')!r}")
            if "year" in s and not isinstance(s["year"], int):
                warn.append(f"тезис {i}: у {s.get('who')!r} год не число, источник уйдёт в «без даты»")
                s.pop("year")
    lens_ids = {l.get("id") for l in R.get("lenses", [])}
    for t in roots:
        for s in t.get("sources", []):
            if s.get("lens") and s["lens"] not in lens_ids:
                warn.append(f"источник {s.get('who')!r}: линза {s['lens']!r} не объявлена в lenses")
    return err, warn


def write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def build(text, R):
    payload = dict(R)
    payload["text"] = text
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    tpl = open(VIEWER, encoding="utf-8").read()
    if tpl.count(TOKEN) != 1:
        sys.exit("Шаблон просмотрщика повреждён: метка данных должна встречаться ровно один раз")
    head, tail = tpl.split(TOKEN)
    return head + data + tail  # данные вставляются один раз и больше не обрабатываются


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("roots")
    ap.add_argument("--out", default="roots_map.html")
    ap.add_argument("--json-out", help="сохранить полный отчёт (текст + корни) одним JSON для сайта")
    a = ap.parse_args()
    text = read_text(a.text)
    try:
        R = json.load(open(a.roots, encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        sys.exit(f"roots.json не читается: {e}")
    err, warn = validate(R, text)
    for w in warn:
        print("предупреждение:", w, file=sys.stderr)
    if err:
        sys.exit("Карта не собрана, старый файл не тронут:\n  " + "\n  ".join(err))
    write_atomic(a.out, build(text, R))
    if a.json_out:
        json.dump(dict(R, text=text), open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Карта:", a.out)
