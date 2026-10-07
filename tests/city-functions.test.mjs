import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const script=fs.readFileSync(new URL('../city-functions.js',import.meta.url),'utf8');
const data=JSON.parse(fs.readFileSync(new URL('../city_functions_data.json',import.meta.url),'utf8'));
const {checkCityFunctions,medicineValue,heatPlot,medicinePlot,mountCityFunctions}=await import('data:text/javascript;base64,'+Buffer.from(script).toString('base64'));

function render(snapshot=data) {
  const nodes=new Map();
  const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,textContent:'',innerHTML:'',value:'',listeners:{},addEventListener(k,v){this.listeners[k]=v;}});return nodes.get(id);};
  mountCityFunctions(snapshot,{getElementById:node});return node;
}

test('citywide causal score and invented loss totals are refused',()=>{
  assert.equal(checkCityFunctions(data),data);
  assert.throws(()=>checkCityFunctions({...data,overall_city_index:85}));
  assert.throws(()=>checkCityFunctions({...data,heat:{...data.heat,building_hours_without_heating:120000}}));
});

test('unclosed month and absent group remain missing; recorded zero stays zero',()=>{
  const m={calendar_month_closed:true,redeemed_prescriptions:0,groups:{zero:0}};
  assert.equal(medicineValue(m,'all'),0);assert.equal(medicineValue(m,'zero'),0);assert.equal(medicineValue(m,'absent'),null);
  assert.equal(medicineValue({...m,calendar_month_closed:false},'all'),null);
  const copy=structuredClone(data);copy.medicines.months.at(-1).prescriptions_per_calendar_day=0;
  assert.throws(()=>checkCityFunctions(copy));
});

test('profile contains actual broad results and visible causality limits',()=>{
  const node=render();
  assert.equal(node('city-functions-content').hidden,false);
  assert.match(node('city-function-results').innerHTML,/71,1%/);
  assert.match(node('city-function-results').innerHTML,/13 больниц/);
  assert.match(node('city-function-coverage').innerHTML,/Работа и торговля/);
  assert.match(node('city-effect-method').innerHTML,/уже изменённой жизни/);
  assert.match(node('city-source-audit').innerHTML,/69 месяцев/);
  assert.match(node('city-source-audit').innerHTML,/Расхождение|расхождение/);
  assert.match(node('medicine-use-table').innerHTML,/Незавершённый месяц/);
});

test('year and group controls preserve differences in definitions',()=>{
  const node=render();const before=node('medicine-use-chart').innerHTML;
  node('medicine-year').value='2021';node('medicine-year').listeners.change();
  assert.notEqual(node('medicine-use-chart').innerHTML,before);
  node('medicine-group').value='несуществующая группа';node('medicine-group').listeners.change();
  assert.match(node('medicine-use-chart').innerHTML,/Отсутствующая группа не равна нулю/);
  assert.doesNotMatch(node('medicine-use-table').innerHTML,/>0<\/td>/);
});

test('heat uses isolated reports and qualifiers, without invented interpolation',()=>{
  const graph=heatPlot(data.heat.observations,data.heat.attack_dates);
  assert.equal([...graph.matchAll(/<circle/g)].length,20);
  assert.equal([...graph.matchAll(/class="event"/g)].length,3);
  assert.doesNotMatch(graph,/<polyline|NaN|undefined/);
  assert.match(graph,/&gt;|&lt;/);
  const markers=[...graph.matchAll(/<line class="event" x1="([^"]+)"/g)].map(m=>Number(m[1]));
  const points=[...graph.matchAll(/<circle cx="([^"]+)"/g)].map(m=>Number(m[1]));
  data.heat.observations.forEach((r,i)=>assert.ok(points[i]>=markers[r.phase-1],`Report from phase ${r.phase} must follow the attack date`));
  const previousEvening=data.heat.observations.findIndex(r=>r.observed_date==='2026-01-19');
  assert.ok(points[previousEvening]<markers[1], 'Previous-evening observation must remain before the next attack day');
});

test('public source text and links are escaped',()=>{
  const copy=structuredClone(data),f=copy.facts.find(x=>x.id==='water11');
  f.summary='<script>danger()</script>';f.source_url='javascript:danger()';
  const node=render(copy);
  assert.match(node('water-impact-facts').innerHTML,/&lt;script&gt;/);
  assert.doesNotMatch(node('water-impact-facts').innerHTML,/<script>|javascript:/);
});

test('all history draws finite monthly points without the two unclosed months',()=>{
  const graph=medicinePlot(data.medicines.months,'all');
  assert.doesNotMatch(graph,/NaN|undefined/);
  const closed=data.medicines.months.filter(x=>x.calendar_month_closed).length;
  assert.equal([...graph.matchAll(/<circle/g)].length,closed);
  assert.equal(closed,67);
});
