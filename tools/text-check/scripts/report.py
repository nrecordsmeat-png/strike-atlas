#!/usr/bin/env python3
"""Отчёт с инфографикой: один самодостаточный HTML-файл.

    python scripts/report.py readers.json --mech mech.json --voice voice.json --out отчёт.html

readers.json — итог шагов «читатели / покрытие / пробелы / встречный текст»
(формат в examples/readers.json). mech.json и voice.json — вывод
mechanics.py и voice.py с флагом --json; оба необязательны.
Только стандартная библиотека Python 3.8+.
"""
import argparse
import html
import json

MARK = {"+": ("понял", "ok"), "?": ("понял, но переспросил", "q"),
        "-": ("выпало", "miss"), "x": ("искажено", "bad")}
ICON = {"+": "✓", "?": "?", "-": "–", "x": "✕"}

CSS = """
:root{--bg:#fcfcfb;--fg:#0b0b0b;--mut:#6b6a66;--line:#e1e0d9;--ok:#e3f1dc;--okf:#27500a;--q:#faeeda;--qf:#633806;
--miss:#f1efe8;--missf:#444441;--bad:#fcebeb;--badf:#791f1f;--bar:#2a78d6}
@media(prefers-color-scheme:dark){:root{--bg:#151515;--fg:#f0efec;--mut:#a3a29b;--line:#2c2c2a;--ok:#27500a;--okf:#c0dd97;
--q:#633806;--qf:#fac775;--miss:#2c2c2a;--missf:#d3d1c7;--bad:#791f1f;--badf:#f7c1c1;--bar:#3987e5}}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem}
h1{font-size:22px;font-weight:500;margin:0 0 .3rem}h2{font-size:17px;font-weight:500;margin:2rem 0 .6rem}
.mut{color:var(--mut);font-size:13px}.thesis{border-left:3px solid var(--bar);padding:.2rem 0 .2rem .8rem;margin:1rem 0}
table{border-collapse:separate;border-spacing:4px;width:100%;font-size:14px}th{font-weight:400;color:var(--mut);font-size:12px}
td.c{text-align:center;border-radius:6px;width:70px}.ok{background:var(--ok);color:var(--okf)}.q{background:var(--q);color:var(--qf)}
.miss{background:var(--miss);color:var(--missf)}.bad{background:var(--bad);color:var(--badf)}
.row{display:grid;grid-template-columns:minmax(0,1fr) 160px 24px;gap:10px;align-items:center;margin:6px 0;font-size:14px}
.track{background:var(--line);border-radius:4px;height:12px}.fill{height:12px;border-radius:4px;background:var(--bar)}
.tag{font-size:12px;padding:1px 8px;border-radius:6px;margin-left:6px}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}.kv div{background:var(--line);border-radius:8px;padding:.6rem .8rem}
.kv b{display:block;font-size:20px;font-weight:500}.kv span{font-size:12px;color:var(--mut)}
ul{padding-left:1.2rem}li{margin:.2rem 0}
"""


def e(s):
    return html.escape(str(s))


def coverage(R):
    out = ['<h2>Покрытие: какие опорные мысли дошли до читателей</h2><table><tr><th></th>']
    out += [f"<th>{e(r['name'])}</th>" for r in R["readers"]] + ["</tr>"]
    for i, cp in enumerate(R["checkpoints"]):
        out.append(f"<tr><td>{i + 1}. {e(cp)}</td>")
        for r in R["readers"]:
            m = r["marks"][i]
            out.append(f'<td class="c {MARK[m][1]}" title="{MARK[m][0]}">{ICON[m]}</td>')
        out.append("</tr>")
    out.append("</table><p class='mut'>" + " · ".join(f"{ICON[k]} {v[0]}" for k, v in MARK.items()) + "</p>")
    n = len(R["readers"]) * len(R["checkpoints"])
    full = sum(m == "+" for r in R["readers"] for m in r["marks"])
    part = sum(m == "?" for r in R["readers"] for m in r["marks"])
    return "".join(out), round(100 * full / n), round(100 * (full + part) / n)


def bars(title, items, total, label):
    out = [f"<h2>{title}</h2>"]
    for it in sorted(items, key=lambda x: -x["count"]):
        tag = ""
        if it.get("type"):
            cls = {"задуманный": "ok", "дефект": "bad"}.get(it["type"], "q")
            tag = f'<span class="tag {cls}">{e(it["type"])}</span>'
        extra = f'<div class="mut">{e(label)}: {e(it["as_read"])}</div>' if it.get("as_read") else ""
        out.append(f'<div class="row"><div>{e(it["place"])}{tag}{extra}</div>'
                   f'<div class="track"><div class="fill" style="width:{round(100 * it["count"] / total)}%"></div></div>'
                   f'<div>{it["count"]}</div></div>')
    return "".join(out)


def mech_block(M):
    p, s, k, st = M["простота"], M["структура"], M["краткость"], M["стимуляция"]
    cards = [("слов", M["объём"]["слов"]), ("фраза, медиана слов", p["длина_фразы_медиана"]),
             ("фраз от 25 слов", f'{p["доля_фраз_от_25_слов_%"]}%'), ("длинных слов", f'{p["доля_длинных_слов_5+_слогов_%"]}%'),
             ("слов на абзац", s["слов_на_абзац_медиана"]), ("вопросов на 1000", st["вопросы_на_1000"])]
    out = ["<h2>Механика понятности</h2><div class='kv'>"]
    out += [f"<div><b>{e(v)}</b><span>{e(n)}</span></div>" for n, v in cards]
    out.append("</div><p class='mut'>Счётное приближение к Гамбургской модели понятности. Показывает, где смотреть, а не оценивает мысль.</p>")
    return "".join(out)


def voice_block(V):
    out = ["<h2>Голос автора</h2>"]
    if V["расхождения"]:
        out.append("<ul>" + "".join(f"<li>{e(f)}</li>" for f in V["расхождения"]) + "</ul>")
    else:
        out.append("<p>Заметных расхождений с эталоном нет.</p>")
    note = " Текст короткий, общий показатель ненадёжен." if V["слов"] < 2000 else ""
    out.append(f"<p class='mut'>Общая непохожесть: дальше, чем {V['дельта_перцентиль']}% кусков самого автора.{note}</p>")
    return "".join(out)


MIRROR_JS = """
<script>
const KEY='textcheck:'+document.title;let S={};try{S=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};
document.querySelectorAll('.pt').forEach(el=>{const id=el.dataset.id;const st=S[id]||{};
 el.querySelectorAll('button[data-v]').forEach(b=>{if(st.v===b.dataset.v)b.classList.add('on');
  b.onclick=()=>{S[id]=S[id]||{};S[id].v=S[id].v===b.dataset.v?'':b.dataset.v;
   el.querySelectorAll('button[data-v]').forEach(x=>x.classList.toggle('on',x.dataset.v===S[id].v));save()}});
 const t=el.querySelector('textarea');t.value=st.n||'';t.oninput=()=>{S[id]=S[id]||{};S[id].n=t.value;save()}});
document.getElementById('copy').onclick=()=>{const L=[];document.querySelectorAll('.pt').forEach(el=>{const s=S[el.dataset.id]||{};
 if(s.v||s.n)L.push('- '+el.dataset.text+' → '+(s.v||'без отметки')+(s.n?' ('+s.n+')':''))});
 const out=L.length?'Мои отметки по зеркалу:\\n'+L.join('\\n'):'Отметок нет';
 const ta=document.getElementById('out');ta.value=out;ta.style.display='block';ta.select();
 try{navigator.clipboard.writeText(out);document.getElementById('copy').textContent='Скопировано'}catch(e){}};
</script>"""

MIRROR_CSS = """
.pt{border:1px solid var(--line);border-radius:10px;padding:.7rem .9rem;margin:.5rem 0}
.pt .h{display:flex;justify-content:space-between;gap:10px}.pt .who{font-size:12px;color:var(--mut);white-space:nowrap}
.btns{display:flex;gap:6px;flex-wrap:wrap;margin:.5rem 0 .3rem}
button{font:inherit;font-size:13px;border:1px solid var(--line);background:transparent;color:var(--fg);border-radius:6px;padding:3px 10px;cursor:pointer}
button.on[data-v="да, это"]{background:var(--ok);color:var(--okf)}button.on[data-v="не то"]{background:var(--bad);color:var(--badf)}
button.on[data-v="так лучше"]{background:var(--q);color:var(--qf)}
textarea{width:100%;box-sizing:border-box;font:inherit;font-size:13px;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 8px;min-height:30px}
.dots{letter-spacing:2px;color:var(--bar)}
"""


def point(pid, text, who, sub=""):
    return (f'<div class="pt" data-id="{pid}" data-text="{e(text)}"><div class="h"><div>{e(text)}'
            f'{f"<div class=mut>{e(sub)}</div>" if sub else ""}</div><div class="who">{who}</div></div>'
            '<div class="btns">' + "".join(f'<button data-v="{v}">{v}</button>' for v in ("да, это", "не то", "так лучше")) +
            '</div><textarea placeholder="заметка, если нужна"></textarea></div>')


def render_mirror(R, M=None, V=None):
    n = len(R["readers"])
    title = R.get("title", "Зеркало")
    rnd = R.get("round", 1)
    p = [f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
         f"<title>{e(title)} · круг {rnd}</title><style>{CSS}{MIRROR_CSS}</style></head><body>",
         f"<h1>{e(title)}</h1><p class='mut'>Зеркало, круг {rnd} · слепых читателей: {n}. "
         "Отметь, что совпадает с твоей мыслью, а что нет. Отметки сохраняются в этом браузере.</p>",
         "<h2>Главная мысль глазами читателей</h2>"]
    p += [f"<div class='thesis'><span class='mut'>{e(r['name'])}</span><br>{e(r.get('main', ''))}</div>" for r in R["readers"]]
    p.append("<h2>Ход мысли, который видят читатели</h2>")
    for i, c in enumerate(R.get("chain", [])):
        dots = "●" * c["count"] + "○" * (n - c["count"])
        p.append(point(f"c{i}", c["point"], f"<span class='dots'>{dots}</span> {c['count']} из {n}"))
    if R.get("divergent"):
        p.append("<h2>Увидел только один: возможное второе прочтение</h2>")
        p += [point(f"d{i}", d["point"], e(d["who"])) for i, d in enumerate(R["divergent"])]
    if R.get("gaps"):
        p.append("<h2>Где читатели остановились и как поняли</h2>")
        p += [point(f"g{i}", g["place"], f"{g['count']} из {n}", "поняли как: " + g["as_read"] if g.get("as_read") else "")
              for i, g in enumerate(sorted(R["gaps"], key=lambda x: -x["count"]))]
    if R.get("rebuilds"):
        p.append("<h2>Перестроили одинаково</h2>")
        p += [point(f"r{i}", f"{r['original']} → {r['as_read']}", f"{r['count']} из {n}") for i, r in enumerate(R["rebuilds"])]
    if R.get("questions"):
        p.append("<h2>Вопросы к тебе</h2><ul>" + "".join(f"<li>{e(q)}</li>" for q in R["questions"]) + "</ul>")
    if M:
        p.append(mech_block(M))
    if V:
        p.append(voice_block(V))
    p.append("<h2>Вернуть в чат</h2><button id='copy'>Скопировать мои отметки</button>"
             "<textarea id='out' style='display:none;margin-top:8px;min-height:120px'></textarea>")
    p.append(MIRROR_JS + "</body></html>")
    return "".join(p)


REL = {"совпадает": "ok", "развивает": "dev", "расходится": "bad", "перекликается": "q", "своё": "own"}
ROOTS_CSS = """
.rt{border:1px solid var(--line);border-radius:10px;padding:.7rem .9rem;margin:.6rem 0}
.rt .th{font-weight:500;margin-bottom:.3rem}.src{border-left:3px solid var(--line);padding:.1rem 0 .1rem .7rem;margin:.5rem 0}
.src.ok{border-color:#1baf7a}.src.dev{border-color:#2a78d6}.src.bad{border-color:#e34948}.src.q{border-color:#eda100}
.badge{font-size:12px;padding:1px 8px;border-radius:6px;margin-right:6px;background:var(--line)}
.badge.ok{background:var(--ok);color:var(--okf)}.badge.bad{background:var(--bad);color:var(--badf)}.badge.q{background:var(--q);color:var(--qf)}
.badge.dev{background:#e6f1fb;color:#0c447c}.badge.own{background:#eeedfe;color:#3c3489}
@media(prefers-color-scheme:dark){.badge.dev{background:#0c447c;color:#b5d4f4}.badge.own{background:#3c3489;color:#cecbf6}}
.stack{display:flex;height:14px;border-radius:4px;overflow:hidden;margin:.4rem 0}.stack div{height:14px}
a{color:var(--bar)}
"""
REL_COLOR = {"совпадает": "#1baf7a", "развивает": "#2a78d6", "расходится": "#e34948", "перекликается": "#eda100", "своё": "#6250d6"}


def roots_block(roots):
    links = [s for t in roots for s in t.get("sources", [])]
    cnt = {k: 0 for k in REL}
    for t in roots:
        if not t.get("sources"):
            cnt["своё"] += 1
    for s in links:
        cnt[s["relation"]] = cnt.get(s["relation"], 0) + 1
    total = sum(cnt.values()) or 1
    out = ["<h2>Корни мысли: откуда растут тезисы и где автор расходится</h2>",
           "<div class='stack'>" + "".join(f"<div style='width:{100 * v / total}%;background:{REL_COLOR[k]}' title='{k}: {v}'></div>"
                                          for k, v in cnt.items() if v) + "</div>",
           "<p class='mut'>" + " · ".join(f"<span class='badge {REL[k]}'>{k}</span>{v}" for k, v in cnt.items() if v) + "</p>"]
    for i, t in enumerate(roots):
        out.append(f"<div class='rt'><div class='th'>{i + 1}. {e(t['thesis'])}</div>")
        if t.get("own"):
            out.append(f"<div class='src'><span class='badge own'>своё</span>{e(t['own'])}</div>")
        for s in t.get("sources", []):
            link = f" · <a href='{e(s['url'])}'>источник</a>" if s.get("url") else ""
            out.append(f"<div class='src {REL[s['relation']]}'><span class='badge {REL[s['relation']]}'>{e(s['relation'])}</span>"
                       f"<b>{e(s['who'])}</b> <span class='mut'>{e(s.get('work', ''))} {e(s.get('tag', ''))}{link}</span>"
                       f"<div>{e(s['idea'])}</div><div class='mut'>{e(s['vs'])}</div></div>")
        out.append("</div>")
    out.append("<p class='mut'>Сходство не значит заимствование, расхождение не значит ошибку. Показано родство мыслей, а не правота.</p>")
    return "".join(out)


def render(R, M=None, V=None):
    html_ = _render(R, M, V)
    if R.get("roots"):
        html_ = html_.replace("</style>", ROOTS_CSS + "</style>", 1).replace("</body>", roots_block(R["roots"]) + "</body>", 1)
    return html_


def _render(R, M=None, V=None):
    if R.get("mode") == "roots":
        t = e(R.get("title", "Корни мысли"))
        return (f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                f"<title>{t}</title><style>{CSS}</style></head><body><h1>{t}</h1></body></html>")
    if R.get("mode") == "mirror":
        return render_mirror(R, M, V)
    cov, full, any_ = coverage(R)
    nread = len(R["readers"])
    parts = [f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
             f"<title>{e(R.get('title', 'Проверка текста'))}</title><style>{CSS}</style></head><body>",
             f"<h1>{e(R.get('title', 'Проверка текста'))}</h1>",
             f"<p class='mut'>Слепых читателей: {nread} · опорных мыслей: {len(R['checkpoints'])}</p>"]
    if R.get("thesis"):
        parts.append(f"<div class='thesis'><span class='mut'>Замысел автора</span><br>{e(R['thesis'])}</div>")
    parts.append(f"<div class='kv'><div><b>{full}%</b><span>мыслей понято сразу</span></div>"
                 f"<div><b>{any_}%</b><span>понято, считая с переспросом</span></div>"
                 f"<div><b>{len(R.get('gaps', []))}</b><span>мест, где читатели остановились</span></div></div>")
    parts.append(cov)
    if R.get("gaps"):
        parts.append(bars("Пробелы: где читатели остановились и как поняли", R["gaps"], nread, "как поняли"))
    if R.get("rebuilds"):
        parts.append(bars("Встречный текст: что читатели перестроили одинаково",
                          [{"place": r["original"], "as_read": r["as_read"], "count": r["count"]} for r in R["rebuilds"]],
                          nread, "прочитали как"))
    if M:
        parts.append(mech_block(M))
    if V:
        parts.append(voice_block(V))
    if R.get("notes"):
        parts.append(f"<h2>Вывод</h2><p>{e(R['notes'])}</p>")
    parts.append("</body></html>")
    return "".join(parts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("readers")
    ap.add_argument("--mech")
    ap.add_argument("--voice")
    ap.add_argument("--out", default="report.html")
    a = ap.parse_args()
    load = lambda p: json.load(open(p, encoding="utf-8")) if p else None
    open(a.out, "w", encoding="utf-8").write(render(load(a.readers), load(a.mech), load(a.voice)))
    print("Отчёт:", a.out)
