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
ВНИМАНИЕ: в карту целиком встраивается сам текст. Не выкладывай её публично, если текст личный.
Только стандартная библиотека Python 3.8+.
"""
import argparse
import html
import json
import sys

REL_ORDER = ["совпадает", "развивает", "перекликается", "расходится"]


def find(text, frag, start=0):
    for hay, needle in ((text, frag), (text.lower(), frag.lower()),
                        (text.lower().replace("ё", "е"), frag.lower().replace("ё", "е"))):
        i = hay.find(needle, start)
        if i >= 0:
            return i
    return -1


def mark_text(text, roots):
    spans = []
    for ti, t in enumerate(roots):
        for f in t.get("fragments", []):
            i = find(text, f)
            if i < 0:
                print(f"не найден фрагмент тезиса {ti + 1}: {f[:60]}", file=sys.stderr)
                continue
            spans.append((i, i + len(f), ti))
    spans.sort()
    out, pos, last_end = [], 0, -1
    for a, b, ti in spans:
        if a < last_end:
            print(f"фрагмент тезиса {ti + 1} перекрывает другой, пропущен", file=sys.stderr)
            continue
        out.append(html.escape(text[pos:a]))
        own = ("" if roots[ti].get("sources") else " own") + (" imp" if roots[ti].get("implicit") else "")
        out.append(f'<mark class="fr{own}" data-t="{ti}">{html.escape(text[a:b])}</mark>')
        pos = last_end = b
    out.append(html.escape(text[pos:]))
    body = "".join(out)
    return "".join(f"<p>{p}</p>" for p in body.split("\n") if p.strip())


PAGE = r"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>__TITLE__</title><style>
:root{--bg:#fcfcfb;--fg:#0b0b0b;--mut:#6b6a66;--line:#e1e0d9;--card:#fff;--ok:#1baf7a;--dev:#2a78d6;--q:#eda100;--bad:#e34948;--own:#6250d6;--hl:#fff3c4}
@media(prefers-color-scheme:dark){:root{--bg:#151515;--fg:#f0efec;--mut:#a3a29b;--line:#2c2c2a;--card:#1f1f1e;--hl:#5a4a12;--own:#9085e9}}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;padding:1.5rem}
h1{font-size:22px;font-weight:500;margin:0 0 .2rem}.mut{color:var(--mut);font-size:13px}
.meaning{border-left:3px solid var(--own);padding:.3rem 0 .3rem .9rem;margin:1rem 0;font-size:16px}.meaning span{display:block;font-size:12px;color:var(--mut)}
.lensbar{display:flex;flex-wrap:wrap;gap:6px;margin:1rem 0 .2rem}.lensbar button{font:inherit;font-size:13px;border:1px solid var(--line);background:transparent;color:var(--fg);border-radius:6px;padding:4px 12px;cursor:pointer}.lensbar button.on{background:var(--fg);color:var(--bg)}
#author{border-left-color:var(--ok)}
svg .dim2{opacity:.12}.lensb{font-size:11px;padding:1px 7px;border-radius:6px;background:var(--line);margin-left:6px}
.warn{font-size:13px;color:var(--bad);margin:.4rem 0}
.top{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:1rem 0}
.top div{background:var(--line);border-radius:8px;padding:.6rem .8rem}.top b{display:block;font-size:22px;font-weight:500}.top span{font-size:12px;color:var(--mut)}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:1.5rem;align-items:start}
@media(max-width:900px){.wrap{grid-template-columns:1fr}}
.text p{margin:0 0 .8rem}
mark.fr{background:transparent;border-bottom:2px solid var(--dev);cursor:pointer;color:inherit;padding:0 1px}
mark.fr.own{border-bottom-color:var(--own)}mark.fr.imp{border-bottom-style:dashed}mark.fr.on{background:var(--hl)}
.side{position:sticky;top:1rem}
svg text{fill:var(--fg)}svg .node{cursor:pointer}svg .dim{opacity:.15}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;margin-top:.8rem;min-height:3rem}
.card h3{font-size:15px;font-weight:500;margin:0 0 .4rem}
.src{border-left:3px solid var(--line);padding:.1rem 0 .1rem .7rem;margin:.6rem 0}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:.3rem;font-size:14px}.cols span{display:block;font-size:11px;color:var(--mut)}
.badge{font-size:11px;padding:1px 7px;border-radius:6px;color:#fff;margin-right:6px}
.brow{display:grid;grid-template-columns:150px minmax(0,1fr) 2px minmax(0,1fr) 30px;gap:6px;align-items:center;font-size:13px;margin:3px 0;cursor:pointer;border-radius:6px;padding:2px 4px}.brow:hover,.brow.sel{background:var(--line)}.brow.head{cursor:default;font-size:11px;color:var(--mut)}.brow.head:hover{background:none}
.bl{display:flex;justify-content:flex-end;align-items:center;gap:4px}.br{display:flex;align-items:center;gap:4px}.bl i,.br i{display:block;height:10px;border-radius:3px}.bc{height:16px;background:var(--mut);opacity:.4}.bl span,.br span,.be span{font-size:11px;color:var(--mut)}
.bars .row{display:grid;grid-template-columns:150px minmax(0,1fr) 24px;gap:8px;align-items:center;font-size:13px;margin:4px 0}
.bars .tr{background:var(--line);border-radius:4px;height:10px}.bars .fi{height:10px;border-radius:4px;background:var(--dev)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--mut);margin:.4rem 0}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
a{color:var(--dev)}
</style></head><body>
<h1>__TITLE__</h1>
<p class="mut">Щёлкни подчёркнутую фразу, чтобы увидеть её родство в истории мысли, или точку на графике, чтобы найти фразу в тексте. Сходство не значит заимствование, расхождение не значит ошибку.</p>
<div class="lensbar" id="lensbar"></div>
<div class="meaning" id="author"></div>
<div class="meaning" id="meaning"></div>
<div class="top" id="top"></div>
<div class="wrap">
 <div class="text">__TEXT__</div>
 <div class="side">
  <div class="legend" id="legend"></div>
  <div id="chart"></div>
  <div class="card" id="card"><span class="mut">Выбери фразу или точку.</span></div>
  <div class="bars" id="bars" style="margin-top:1rem"></div>
 </div>
</div>
<script>
const R=__DATA__;const MEANING=__MEANING__;const LENSES=__LENSES__;const AUTHOR=__AUTHOR__;let LENS=null;
const REL={"совпадает":"--ok","развивает":"--dev","перекликается":"--q","расходится":"--bad"};
const ROWS=["совпадает","развивает","перекликается","расходится"];
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const S=[];R.forEach((t,ti)=>(t.sources||[]).forEach(s=>{if(typeof s.year==="number")S.push(Object.assign({ti},s))}));
// смысл текста
function renderMeaning(){const box=document.getElementById('meaning');const L=LENSES.find(l=>l.id===LENS);
 if(L)box.innerHTML=`<span>Как текст читает ${esc(L.name)}</span>${esc(L.meaning)}`+(L.against?`<div class="mut" style="margin-top:4px">С чем спорит, по мнению этого лагеря: ${esc(L.against)}</div>`:'');
 else box.innerHTML=MEANING?'<span>Что текст говорит (нейтральный слой, по пересказам слепых читателей, без оценки)</span>'+esc(MEANING):'';}
renderMeaning();
if(AUTHOR)document.getElementById('author').innerHTML='<span>Прочтение автора — последнее слово о смысле, но не о правоте</span>'+esc(AUTHOR);
else document.getElementById('author').style.display='none';
if(LENSES.length){const bar=document.getElementById('lensbar');
 const btn=(id,name)=>`<button data-l="${id??''}">${esc(name)}</button>`;
 bar.innerHTML='<span class="mut" style="align-self:center;margin-right:4px">Линза:</span>'+btn(null,'нейтрально')+LENSES.map(l=>btn(l.id,l.name)).join('');
 const set=id=>{LENS=id||null;bar.querySelectorAll('button').forEach(b=>b.classList.toggle('on',(b.dataset.l||null)===LENS));renderMeaning();
  document.querySelectorAll('svg .node').forEach(n=>{const s=S[+n.dataset.i];n.classList.toggle('dim2',!!LENS&&s.lens!==LENS)});
  marks.forEach(m=>{const t=R[+m.dataset.t];m.style.opacity=!LENS||(t.sources||[]).some(x=>x.lens===LENS)?1:.45});renderBars()};
 bar.querySelectorAll('button').forEach(b=>b.onclick=()=>set(b.dataset.l));setTimeout(()=>set(null),0)}
// баланс спорных тезисов
const side=r=>r==="расходится"?"contra":(r==="совпадает"||r==="развивает")?"pro":null;
const oneSided=R.map(t=>{if(!t.contested)return null;const sd=new Set((t.sources||[]).map(x=>side(x.relation)).filter(Boolean));
 return sd.size<2?(sd.has("pro")?"только совпадения":sd.has("contra")?"только расхождения":"нет ни совпадений, ни расхождений"):null});
// сводка
const ys=S.map(s=>s.year);const trad={};S.forEach(s=>{if(s.tradition)trad[s.tradition]=(trad[s.tradition]||0)+1});
const own=R.filter(t=>!(t.sources||[]).length).length;
const span=ys.length?Math.max(...ys)-Math.min(...ys):0;
const yl=y=>y<0?Math.abs(y)+" до н. э.":String(y);
document.getElementById('top').innerHTML=[
 [ys.length?"≈"+Math.round(span/100)+" в.":"—","охват родства"+(ys.length?` (${yl(Math.min(...ys))} — ${yl(Math.max(...ys))})`:"")],
 [Object.keys(trad).length,"традиций и дисциплин"],[S.length,"связей с источниками"],[own,"тезисов без близкого источника"],[oneSided.filter(Boolean).length,"спорных тезисов с корнями только с одной стороны"]]
 .map(([b,s])=>`<div><b>${b}</b><span>${s}</span></div>`).join("");
document.getElementById('legend').innerHTML=ROWS.map(r=>`<span><i style="background:var(${REL[r]})"></i>${r}</span>`).join("")+
 `<span><i style="background:var(--own)"></i>своё</span>`;
// график
(function(){const W=560,H=370,ns="http://www.w3.org/2000/svg";if(!S.length){document.getElementById('chart').innerHTML='<p class="mut">У источников не указаны годы.</p>';return}
 const mn=Math.min(...ys),mx=Math.max(...ys),L=95,Rt=W-20;const ancient=mn<1800&&mx>1800;
 const X=y=>{if(!ancient)return L+(y-mn)/((mx-mn)||1)*(Rt-L);const cut=L+(Rt-L)*0.22;
  return y<1800?L+(y-mn)/((1800-mn)||1)*(cut-L):cut+(y-1800)/((mx-1800)||1)*(Rt-cut)};
 const Y=r=>48+ROWS.indexOf(r)*80;
 const s=document.createElementNS(ns,'svg');s.setAttribute('viewBox',`0 0 ${W} ${H}`);s.setAttribute('width','100%');
 const el=(n,a,t,p)=>{const e=document.createElementNS(ns,n);for(const k in a)e.setAttribute(k,a[k]);if(t!=null)e.textContent=t;(p||s).appendChild(e);return e};
 ROWS.forEach(r=>{el('line',{x1:L,x2:Rt,y1:Y(r),y2:Y(r),stroke:css('--line'),'stroke-dasharray':'2 4'});el('text',{x:4,y:Y(r)+4,'font-size':11,opacity:.6},r)});
 if(ancient)el('line',{x1:L+(Rt-L)*0.22,x2:L+(Rt-L)*0.22,y1:20,y2:H-30,stroke:css('--line')});
 const ticks=ancient?[mn,1800,mx]:[mn,Math.round((mn+mx)/2),mx];
 ticks.forEach(y=>el('text',{x:X(y),y:H-8,'font-size':10,opacity:.5,'text-anchor':'middle'},yl(y)));
 const used={},dots={};S.forEach((src,i)=>{let x=X(src.year);const y=Y(src.relation);const dd=dots[src.relation]=dots[src.relation]||[];
  while(dd.some(o=>Math.abs(o-x)<13))x+=13;dd.push(x);const g=el('g',{class:'node','data-i':i,'data-t':src.ti});
  el('circle',{cx:x,cy:y,r:7,fill:css(REL[src.relation]),stroke:css('--bg'),'stroke-width':2},null,g);
  const u=used[src.relation]=used[src.relation]||[];const w=src.who.length*6.2+8;
  const anc=x>Rt-40?'end':x<L+30?'start':'middle';const cx=anc==='end'?x+8-w/2:anc==='start'?x-8+w/2:x;
  const slots=[y-12,y+21,y-31,y+40];let ly=slots[0];
  for(const sy of slots){if(!u.some(o=>o.y===sy&&Math.abs(o.x-cx)<(o.w+w)/2)){ly=sy;break}}
  u.push({x:cx,y:ly,w});
  el('text',{x:anc==='end'?x+8:anc==='start'?x-8:x,y:ly,'font-size':11,'text-anchor':anc},src.who,g);
  g.addEventListener('click',()=>pickSource(i))});
 document.getElementById('chart').appendChild(s)})();
// союзники и оппоненты по традициям
function renderBars(){const src=S.filter(x=>!LENS||x.lens===LENS);const g={};
 src.forEach(x=>{const t=x.tradition||'без традиции';g[t]=g[t]||{pro:0,con:0,echo:0};
  if(x.relation==='расходится')g[t].con++;else if(x.relation==='перекликается')g[t].echo++;else g[t].pro++});
 const rows=Object.entries(g).sort((a,b)=>(b[1].pro-b[1].con)-(a[1].pro-a[1].con)||(b[1].pro+b[1].con)-(a[1].pro+a[1].con));
 const mx=Math.max(1,...rows.map(([,v])=>Math.max(v.pro,v.con)));
 document.getElementById('bars').innerHTML=rows.length?'<div class="mut" style="margin-bottom:6px">С какими школами мысли текст в согласии, а с какими в споре. Щёлкни строку — подсветятся связи в тексте и на графике.</div>'+
  '<div class="brow head"><div></div><div style="text-align:right">в споре</div><div></div><div>в согласии</div><div></div></div>'+
  rows.map(([n,v])=>`<div class="brow" data-tr="${esc(n)}"><div class="bn">${esc(n)}</div>
   <div class="bl">${v.con?`<span>${v.con}</span><i style="width:${100*v.con/mx}%;background:var(--bad)"></i>`:''}</div><div class="bc"></div>
   <div class="br">${v.pro?`<i style="width:${100*v.pro/mx}%;background:var(--ok)"></i><span>${v.pro}</span>`:''}</div>
   <div class="be">${v.echo?`<span title="перекликается">≈${v.echo}</span>`:''}</div></div>`).join(''):'';
 document.querySelectorAll('.brow[data-tr]').forEach(r=>r.onclick=()=>pickTradition(r.dataset.tr))}
function pickTradition(tr){const src=S.map((x,i)=>[x,i]).filter(([x])=>(x.tradition||'без традиции')===tr&&(!LENS||x.lens===LENS));
 const ts=new Set(src.map(([x])=>x.ti));const is=new Set(src.map(([,i])=>i));
 marks.forEach(m=>m.classList.toggle('on',ts.has(+m.dataset.t)));
 document.querySelectorAll('svg .node').forEach(n=>n.classList.toggle('dim',!is.has(+n.dataset.i)));
 document.querySelectorAll('.brow[data-tr]').forEach(r=>r.classList.toggle('sel',r.dataset.tr===tr));
 const first=marks.find(m=>ts.has(+m.dataset.t));if(first)first.scrollIntoView({behavior:'smooth',block:'center'});
 document.getElementById('card').innerHTML=`<h3>${esc(tr)}: где связь с текстом</h3>`+src.map(([x])=>`<div class="mut" style="margin-top:.6rem">к тезису: ${esc(R[x.ti].thesis)}</div>`+srcHtml(x)).join('')}
// выбор
const marks=[...document.querySelectorAll('mark.fr')];
function light(ti,i){marks.forEach(m=>m.classList.toggle('on',+m.dataset.t===ti));
 document.querySelectorAll('svg .node').forEach(n=>n.classList.toggle('dim',i!=null?+n.dataset.i!==i:+n.dataset.t!==ti))}
function srcHtml(s){const c=css(REL[s.relation]);const link=s.url?` · <a href="${esc(s.url)}" target="_blank">источник</a>`:"";
 return `<div class="src" style="border-color:${c}"><span class="badge" style="background:${c}">${esc(s.relation)}</span><b>${esc(s.who)}</b>${s.lens?`<span class="lensb">${esc((LENSES.find(l=>l.id===s.lens)||{}).name||s.lens)}</span>`:''}
 <span class="mut">${esc(s.work||"")} ${esc(s.year_label||"")} ${esc(s.tag||"")}${link}</span>
 <div class="cols"><div><span>у него</span>${esc(s.idea)}</div><div><span>у тебя</span>${esc(s.vs)}</div></div></div>`}
const head=t=>{const i=R.indexOf(t);return (oneSided[i]?`<div class="warn">Спорный тезис: найдены ${oneSided[i]}. Корни с другой стороны не найдены — выбор источников может работать как вывод.</div>`:'')+(t.implicit?'<div class="mut">невысказанный тезис, восстановлен по пересказам читателей</div>':'')+`<h3>${esc(t.thesis)}</h3>`};
function pickThesis(ti){const t=R[ti];light(ti,null);
 document.getElementById('card').innerHTML=head(t)+(t.own?`<div class="src" style="border-color:var(--own)"><span class="badge" style="background:var(--own)">своё</span>${esc(t.own)}</div>`:"")+
  (t.sources||[]).map(srcHtml).join("")}
function pickSource(i){const s=S[i];light(s.ti,i);const m=marks.find(m=>+m.dataset.t===s.ti);if(m)m.scrollIntoView({behavior:'smooth',block:'center'});
 document.getElementById('card').innerHTML=head(R[s.ti])+srcHtml(s)}
marks.forEach(m=>m.addEventListener('click',()=>pickThesis(+m.dataset.t)));
renderBars();
</script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text")
    ap.add_argument("roots")
    ap.add_argument("--out", default="roots_map.html")
    a = ap.parse_args()
    text = open(a.text, encoding="utf-8").read()
    R = json.load(open(a.roots, encoding="utf-8"))
    roots = R["roots"]
    page = (PAGE.replace("__TITLE__", html.escape(R.get("title", "Корни мысли")))
            .replace("__TEXT__", mark_text(text, roots))
            .replace("__DATA__", json.dumps(roots, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__MEANING__", json.dumps(R.get("meaning", ""), ensure_ascii=False).replace("</", "<\\/"))
            .replace("__LENSES__", json.dumps(R.get("lenses", []), ensure_ascii=False).replace("</", "<\\/"))
            .replace("__AUTHOR__", json.dumps(R.get("author_reading", ""), ensure_ascii=False).replace("</", "<\\/")))
    open(a.out, "w", encoding="utf-8").write(page)
    print("Карта:", a.out)
