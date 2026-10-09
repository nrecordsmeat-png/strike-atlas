import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const read = path => readFileSync(new URL('../'+path, import.meta.url), 'utf8');
function mapFixture() {
  const html=read('map.html'),elements=new Map(),markers=[];
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1],{value:'',textContent:'',innerHTML:'',children:[],classList:{toggle(){}},appendChild(child){this.children.push(child);}});
  const document={documentElement:{},getElementById:id=>elements.get(id),createElement:()=>({classList:{toggle(){}}})};
  const layer={addTo(){return this;},clearLayers(){markers.length=0;}};
  const shape=(coordinates)=>{
    assert.ok(coordinates.every(Number.isFinite),'Leaflet received missing coordinates');
    return {bindPopup(){return this;},addTo(){markers.push(coordinates);return this;}};
  };
  const L={map:()=>({setView(){return this;}}),tileLayer:()=>({addTo(){}}),layerGroup:()=>layer,circle:shape,circleMarker:shape};
  const context=vm.createContext({document,L,getComputedStyle:()=>({getPropertyValue:()=> '#123456'})});
  vm.runInContext(read('events.js'),context);
  for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) if(match[1].trim()) vm.runInContext(match[1],context);
  return {elements,markers,context,at(day){elements.get('dateSlider').value=vm.runInContext('DATES.indexOf('+JSON.stringify(day)+')',context);elements.get('dateSlider').oninput();}};
}

test('observations without coordinates remain visible and never reach Leaflet',()=>{
  const f=mapFixture();
  assert.equal(f.elements.get('map-counts').textContent,'30 на карте · 13 без точной привязки');
  assert.equal(f.elements.get('pending-count').textContent,13);
  assert.match(f.elements.get('pending-events').innerHTML,/Соломенский район: магазин/);
  assert.match(f.elements.get('pending-events').innerHTML,/https:\/\/t.me\/dsns_telegram\/76993/);
  assert.ok(f.markers.length>0);
  assert.equal(vm.runInContext('hasEventLocation({lat:null,lng:null})',f.context),false);
  assert.equal(vm.runInContext('hasEventLocation({lat:50,lng:30,unlocated:true})',f.context),false);
});

test('date and object filters also apply to observations waiting for geolocation',()=>{
  const f=mapFixture();
  f.elements.get('modeBtn').onclick();
  f.at('2026-10-07');
  assert.equal(f.elements.get('map-counts').textContent,'0 на карте · 9 без точной привязки');
  assert.equal(f.markers.length,0);
  assert.doesNotMatch(f.elements.get('pending-events').innerHTML,/магазин и склад/);
  f.at('2026-10-08');
  assert.equal(f.elements.get('pending-count').textContent,4);
  for(const chip of f.elements.get('chips').children) if(!chip.innerHTML.includes('Пром, склады, ИТ')) chip.onclick();
  assert.equal(f.elements.get('pending-count').textContent,1);
  assert.match(f.elements.get('pending-events').innerHTML,/Соломенский район: магазин/);
});
