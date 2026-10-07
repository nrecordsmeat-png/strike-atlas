import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const script = fs.readFileSync(new URL('../research.js', import.meta.url),'utf8');
const data = JSON.parse(fs.readFileSync(new URL('../research_data.json',import.meta.url),'utf8'));
const {segments,checkSnapshot} = await import('data:text/javascript;base64,'+Buffer.from(script).toString('base64'));

async function render(snapshot=data, ok=true) {
  const nodes = new Map();
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {hidden:false,textContent:'',_html:'',value:'4',listeners:{},buttons:[],
      set innerHTML(value) {this._html=value; this.buttons=[...value.matchAll(/data-episode="([^"]+)"/g)].map(m=>({dataset:{episode:m[1]},attrs:{},setAttribute(k,v){this.attrs[k]=v;}}));},
      get innerHTML(){return this._html;},
      addEventListener(name, fn){this.listeners[name]=fn;},querySelectorAll(){return this.buttons;}});
    return nodes.get(id);
  }
  const context = vm.createContext({document:{getElementById:node},Intl,URL,URLSearchParams,Number,String,Array,Error,
    location:{href:'https://example.org/research-test.html',search:''},history:{replaceState(){}},
    fetch:async()=>({ok,json:async()=>snapshot})});
  vm.runInContext(script.replaceAll('export function','function'),context);
  await new Promise(resolve=>setImmediate(resolve));
  return {node,choose(id){node('research-picker').listeners.click({target:{closest:()=>({dataset:{episode:id}})}});}};
}

test('a missing observation breaks the line and an observed zero is retained',()=>{
  assert.deepEqual(segments([{v:1},{v:null},{v:0},{v:2},{v:NaN}], 'v'), [[[0,1]],[[2,0],[3,2]]]);
});

test('causal city scores and results for incomplete weeks are rejected',()=>{
  assert.equal(checkSnapshot(data),data);
  assert.throws(()=>checkSnapshot({...data,overall_city_index:91}));
  const copy=structuredClone(data);copy.episodes[1].trips.week.deviation_percent=-15;
  assert.throws(()=>checkSnapshot(copy));
});

test('all three real episodes render with appropriate missing periods',async()=>{
  const f=await render();
  assert.equal(f.node('research-content').hidden,false);
  assert.match(f.node('episode-conclusion').textContent,/24,1%/);
  assert.match(f.node('episode-conclusion').textContent,/1,4%/);
  assert.match(f.node('model-table').innerHTML,/выбран/);
  assert.match(f.node('alert-clock-note').textContent,/22 официальными/);
  f.choose('kyiv-20260924');
  assert.match(f.node('episode-conclusion').textContent,/9,9%/);
  assert.match(f.node('period-table').innerHTML,/4 из 7/);
  assert.match(f.node('function-cards').innerHTML,/Специалисты и дневной стационар/);
  assert.match(f.node('function-cards').innerHTML,/Текущее состояние неизвестно/);
  f.choose('kyiv-20261001');
  assert.match(f.node('rides-chart').innerHTML,/Поездок за октябрь.*нет/);
  assert.equal(f.node('period-table').innerHTML,'');
  assert.match(f.node('ping-chart').innerHTML,/<svg/);
  assert.doesNotMatch(f.node('research-metrics').innerHTML,/NaN|undefined/);
});

test('network baseline control updates independently of trips',async()=>{
  const f=await render();f.choose('kyiv-20260924');
  const original=f.node('ping-chart').innerHTML,rides=f.node('rides-chart').innerHTML;
  f.node('network-base').value='8';f.node('network-base').listeners.change();
  assert.notEqual(f.node('ping-chart').innerHTML,original);
  assert.equal(f.node('rides-chart').innerHTML,rides);
});

test('source markup and unsafe links cannot enter the page',async()=>{
  const copy=structuredClone(data);
  copy.episodes[0].functions[0].updates[0].summary='<script>alert(1)</script>';
  copy.episodes[0].functions[0].updates[0].source_url='javascript:alert(1)';
  const f=await render(copy);
  assert.match(f.node('function-cards').innerHTML,/&lt;script&gt;/);
  assert.doesNotMatch(f.node('function-cards').innerHTML,/<script>|javascript:/);
});

test('fetch failure hides figures and preserves an explicit error',async()=>{
  const f=await render(data,false);
  assert.equal(f.node('research-content').hidden,true);
  assert.equal(f.node('research-error').hidden,false);
  assert.match(f.node('research-error').textContent,/не загружены/);
  assert.equal(f.node('research-metrics').innerHTML,'');
});
