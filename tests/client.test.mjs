// Runs the production client scripts with a small DOM adapter.
// These checks cover rendering and interactions, not browser layout.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const read = path => readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const snapshot = JSON.parse(read('tests/fixtures/city_data.json'));
const decode = value => value.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
class Element {
  constructor(tag, attrs = {}, text = '') {
    this.tag = tag; this.attrs = attrs; this.value = attrs.value || '';
    this.hidden = Object.hasOwn(attrs, 'hidden'); this.listeners = {};
    this.dataset = Object.fromEntries(Object.entries(attrs).filter(([key]) => key.startsWith('data-')).map(([key, value]) => [key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase()), value]));
    this._html = text; this.children = [];
    if (tag === 'select' && !this.value) this.value = text.match(/<option value="([^"]*)"/)?.[1] || '';
  }
  get id() { return this.attrs.id; }
  set innerHTML(value) { this._html = value; this.children = parse(value); }
  get innerHTML() { return this._html; }
  set textContent(value) { this._html = String(value); this.children = []; }
  get textContent() { return this.tag === 'script' ? this._html : decode(this._html.replace(/<[^>]*>/g, '')); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this.attrs[name] = value; }
  getBoundingClientRect() { return { width: 360 }; }
  fire(name = 'click') { assert.ok(this.listeners[name], `Missing ${name} handler`); this.listeners[name](); }
}

function parse(markup) {
  const result = [];
  const tags = /<(button|div|section|select|p|main|header|nav|article|aside|footer|h[123])\b([^>]*)>/g;
  for (const match of markup.matchAll(tags)) {
    const attrs = {};
    for (const field of match[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) attrs[field[1]] = decode(field[2] || '');
    const tail = markup.slice(match.index + match[0].length);
    const end = tail.indexOf(`</${match[1]}>`);
    result.push(new Element(match[1], attrs, end < 0 ? '' : tail.slice(0, end)));
  }
  return result;
}

function inlineScripts(html) {
  return [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(x => x[1]).filter(x => x.trim());
}

function fixture(page = 'index.html', data = structuredClone(snapshot), options = {}) {
  const html = read(page), elements = parse(html.split('<script')[0]);
  const all = () => elements.flatMap(x => [x, ...x.children]);
  const matches = (element, selector) => {
    if (selector === '.plot') return (element.attrs.class || '').split(' ').includes('plot');
    if (selector === "section[id^='view-']") return element.tag === 'section' && element.attrs.id?.startsWith('view-');
    const match = selector.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
    if (!match) throw new Error(`Unsupported test selector: ${selector}`);
    return Object.hasOwn(element.attrs, match[1]) && (match[2] === undefined || element.attrs[match[1]] === match[2]);
  };
  const document = {
    getElementById(id) { const result = all().find(x => x.attrs.id === id); assert.ok(result, `Unknown DOM id: ${id}`); return result; },
    querySelectorAll(selector) { return all().filter(x => matches(x, selector)); },
    querySelector(selector) { return this.querySelectorAll(selector)[0]; },
  };
  const location = { hash: options.hash || '', href: '' };
  const sandbox = { document, location, Intl, Date, URL, console,
    history: { replaceState(_state, _title, value) { location.hash = value; } },
    INPUT: data,
    fetch: () => options.failFetch ? Promise.reject(new Error('offline')) : Promise.resolve({ ok: true, json: () => Promise.resolve(data) }),
  };
  const context = vm.createContext(sandbox);
  vm.runInContext(read('events.js'), context);
  let script = inlineScripts(html).join('\n');
  if (!options.fetch) script = script.replace(/^fetch\("city_data\.json".*$/m, '') + '\nboot(INPUT);';
  vm.runInContext(script, context);
  return { document, location, byId: id => document.getElementById(id),
    button: (key, value) => document.querySelector(`[data-${key}="${value}"]`) };
}

test('all four production pages parse as JavaScript', () => {
  for (const page of ['index.html', 'data.html', 'map.html', 'metodika.html']) {
    for (const script of inlineScripts(read(page))) new vm.Script(script, { filename: page });
  }
});

test('currently published snapshot renders on all data pages', () => {
  const current = JSON.parse(read('city_data.json'));
  for (const [page, host] of [['index.html', 'topic-grid'], ['data.html', 'rent-cards'], ['metodika.html', 'quality-table']]) {
    const f = fixture(page, structuredClone(current));
    assert.ok(f.byId('snapshot-note').textContent);
    assert.doesNotMatch(f.byId(host).innerHTML, /\bNaN\b|\bInfinity\b|undefined/);
  }
});

test('overview reports five unknown episodes with no unsupported current restriction', () => {
  const f = fixture();
  assert.match(f.byId('hero-title').textContent, /требует уточнения/);
  assert.match(f.byId('hero-meta').textContent, /5 эпизодов/);
  assert.match(f.byId('hero-meta').textContent, /Сообщений о завершении эпизода: 0/);
  assert.match(f.byId('recovery-box').textContent, /300/);
  assert.match(f.byId('episode-detail').textContent, /Не установлена/);
});

test('all navigation handlers select one panel and update the hash', () => {
  const f = fixture();
  for (const view of ['services', 'scenarios', 'overview']) {
    f.button('view', view).fire();
    assert.deepEqual(f.document.querySelectorAll("section[id^='view-']").filter(x => !x.hidden).map(x => x.id), [`view-${view}`]);
    assert.equal(f.location.hash, '#' + view);
  }
});

test('past date hides future measurements and recovery reports', () => {
  const f = fixture(), picker = f.byId('day-picker');
  picker.value = '2026-10-01'; picker.fire('change');
  assert.match(f.byId('hero-meta').textContent, /1 эпизодов/);
  assert.match(f.byId('topic-grid').textContent, /Нет замера/);
  assert.doesNotMatch(f.byId('recovery-box').textContent, /300/);
  assert.doesNotMatch(f.byId('change-list').textContent, /04\.10|05\.10|06\.10/);
});

test('service filters preserve weekly recovery and source context', () => {
  const f = fixture();
  f.button('topic', 'water_heat').fire();
  assert.equal(f.byId('service-filter').value, 'water_heat');
  assert.equal(f.document.querySelectorAll('[data-episode]').length, 1);
  f.button('topic', 'power').fire();
  assert.equal(f.document.querySelectorAll('[data-episode]').length, 0);
  assert.match(f.byId('episode-detail').textContent, /300/);
  f.byId('service-filter').value = 'mobility'; f.byId('service-filter').fire('change');
  f.button('episode', 'north-bridge-20261003').fire();
  assert.match(f.byId('episode-detail').textContent, /03\.10/);
  assert.match(f.byId('episode-detail').textContent, /Контекст · состояние услуги не обновляет/);
  assert.doesNotMatch(f.byId('episode-detail').textContent, /undefined/);
});

test('topic buttons reach matching data, quality and map pages', () => {
  const f = fixture();
  for (const [topic, target] of [['mobility', 'data.html#traffic'], ['rent', 'data.html#rent'],
                               ['food', 'metodika.html#quality'], ['strikes', 'map.html']]) {
    f.button('topic', topic).fire();
    assert.equal(f.location.href, target);
  }
});

test('six calculated scenarios render independently of the real ledger', () => {
  const f = fixture(), before = f.byId('hero-meta').textContent;
  for (const scenario of snapshot.scenarios) {
    f.button('scenario', scenario.id).fire();
    assert.match(f.byId('scenario-outcome').textContent, new RegExp(scenario.title));
    assert.equal(f.byId('hero-meta').textContent, before);
  }
  f.button('scenario', 'restored').fire();
  assert.match(f.byId('scenario-outcome').textContent, /Длительность перебоя8 ч/);
  f.button('scenario', 'silence').fire();
  assert.match(f.byId('scenario-outcome').textContent, /Длительность перебояНе установлена/);
  f.button('scenario', 'duplicate').fire();
  assert.match(f.byId('scenario-outcome').textContent, /Сообщений после удаления дублей1/);
});

test('empty history and missing scenarios render safely', () => {
  const data = structuredClone(snapshot);
  data.history = {}; data.scenarios = [];
  data.indicators = {};
  const f = fixture('index.html', data);
  assert.match(f.byId('hero-title').textContent, /Наблюдений для общей оценки пока недостаточно/);
  assert.match(f.byId('episode-list').textContent, /Отсутствие записей не доказывает/);
  assert.match(f.byId('scenario-outcome').textContent, /отсутствуют/);
  assert.equal(f.byId('day-picker').disabled, true);
});

test('fetch failure clearly says the city cannot be evaluated', async () => {
  const f = fixture('index.html', snapshot, { fetch: true, failFetch: true });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(f.byId('hero-title').textContent, /Данные сейчас недоступны/);
  assert.match(f.byId('hero-note').textContent, /оценить нельзя/);
});

test('source-supplied markup and unsafe links are not inserted as HTML', () => {
  const data = structuredClone(snapshot), latest = data.history[Object.keys(data.history).at(-1)];
  latest.episodes[0].title = '<img src=x onerror=alert(1)>';
  latest.episodes[0].updates[0].summary = '<script>alert(1)</script>';
  latest.episodes[0].updates[0].source_url = 'javascript:alert(1)';
  const f = fixture('index.html', data);
  assert.match(f.byId('episode-detail').innerHTML, /&lt;img/);
  assert.match(f.byId('episode-detail').innerHTML, /&lt;script/);
  assert.doesNotMatch(f.byId('episode-detail').innerHTML, /<img|<script|href="javascript:/);
});

test('current legacy rent points produce no deltas and no unsaved baseline', () => {
  const f = fixture('data.html');
  assert.match(f.byId('rent-cards').textContent, /7\s?262/);
  assert.match(f.byId('rent-cards').textContent, /Справочная точка · сравнение недоступно/);
  assert.doesNotMatch(f.byId('rent-cards').textContent, /Δ|бейзлайн|\+7|\+13/);
  assert.match(f.byId('rent-note').textContent, /Сопоставимых дневных точек: 0/);
  assert.doesNotMatch(f.byId('rent-note').textContent, /ночью витрина всегда|7419/);
});

test('rent comparisons only use saved comparable points', () => {
  const data = structuredClone(snapshot);
  data.indicators.rent = [
    {date:'2026-10-04',at:null,in_window:true,comparable:false,total:1000,left:400,right:600},
    {date:'2026-10-05',at:'2026-10-05T06:00:00Z',in_window:true,comparable:true,total:100,left:40,right:60},
    {date:'2026-10-05',at:'2026-10-05T20:00:00Z',in_window:false,comparable:false,total:900,left:300,right:600},
    {date:'2026-10-06',at:'2026-10-06T06:00:00Z',in_window:true,comparable:true,total:110,left:45,right:65},
  ];
  const f = fixture('data.html', data);
  assert.match(f.byId('rent-cards').textContent, /Киев всего/);
  assert.match(f.byId('rent-cards').textContent, /предыдущей сопоставимой точке \+10/);
  assert.match(f.byId('rent-cards').textContent, /к первой \(05\.10/);
  assert.doesNotMatch(f.byId('rent-cards').textContent, /\+890|-890/);
});

test('night-only and one comparable rent point never produce changes', () => {
  const data = structuredClone(snapshot);
  for (const row of [
    {date:'2026-10-05',at:'2026-10-05T20:00:00Z',in_window:false,comparable:false,total:100,left:0,right:100},
    {date:'2026-10-05',at:'2026-10-05T06:00:00Z',in_window:true,comparable:true,total:100,left:0,right:100},
  ]) {
    data.indicators.rent = [row];
    const f = fixture('data.html', data);
    assert.match(f.byId('rent-cards').textContent, /сравнение.*недоступно/);
    assert.match(f.byId('rent-cards').textContent, /0\.0%/);
    assert.doesNotMatch(f.byId('rent-cards').textContent, /Δ/);
  }
});

test('real traffic charts render finite points with method gap respected', () => {
  const f = fixture('data.html');
  assert.equal(f.document.querySelectorAll('.plot').length, 3);
  for (const plot of f.document.querySelectorAll('.plot')) {
    assert.match(plot.innerHTML, /<circle/);
    assert.doesNotMatch(plot.innerHTML, /NaN|Infinity|undefined/);
  }
});

test('train fetch failure stays visible beside the last successful snapshot', () => {
  const data = structuredClone(snapshot);
  data.indicators.uz.push({at:'2026-10-06T09:00:00Z',ok:false,ukraine_trains:null,ukraine_delay_min:null,kyiv_rows:null,kyiv_delay_min:null});
  const f = fixture('data.html', data);
  assert.match(f.byId('uz-table').textContent, /Последнее получение табло не удалось/);
  assert.match(f.byId('uz-table').textContent, /Не удалось/);
  data.indicators.uz = [data.indicators.uz.at(-1)];
  assert.match(fixture('data.html', data).byId('uz-cards').textContent, /Сведений о задержках нет/);
});

test('train history retains archive methods and unknown quality', () => {
  const data = structuredClone(snapshot);
  data.indicators.uz = [
    {at:'2026-10-05T08:32:00Z',ok:null,method:'legacy_mentions',ukraine_trains:null,kyiv_rows:null},
    {at:'2026-10-05T15:40:00Z',ok:true,method:'experimental_route',ukraine_trains:4,kyiv_rows:2,kyiv_delay_min:45},
    {at:'2026-10-06T09:34:00Z',ok:true,method:'route',ukraine_trains:12,kyiv_rows:8,kyiv_delay_min:438},
  ];
  const f = fixture('data.html', data);
  assert.match(f.byId('uz-table').textContent, /Старая схема: качество не отмечено/);
  assert.match(f.byId('uz-table').textContent, /Экспериментальный разбор/);
  assert.match(f.byId('uz-table').textContent, /Разбор маршрутов/);
  assert.match(f.byId('uz-table').textContent, /Не отмечено/);
  assert.match(f.byId('uz-cards').textContent, /строк с Киевом/);
  data.indicators.uz = [data.indicators.uz[0]];
  const legacy = fixture('data.html', data);
  assert.match(legacy.byId('uz-table').textContent, /Не отмечено/);
  assert.doesNotMatch(legacy.byId('uz-table').textContent, /Получение табло не удалось/);
});

test('food history comes only from the snapshot and preserves zero and missing values', () => {
  const data = structuredClone(snapshot);
  data.indicators.food_history = [
    {date:'2026-10-05',at:null,stores:{silpo:{price_marks:10,out_of_stock_marks:0}},silpo_median:{vegetables:11.3,meat:43.11}},
    {date:'2026-10-06',at:null,stores:{silpo:{price_marks:0,out_of_stock_marks:null},novus:{price_marks:null,out_of_stock_marks:null}},silpo_median:{vegetables:null,meat:40}},
  ];
  const f = fixture('data.html', data);
  assert.match(f.byId('food-cards').textContent, /0 \/ —/);
  assert.match(f.byId('food-status').textContent, /время не сохранено/);
  assert.match(f.byId('food-table').textContent, /05\.10/);
  assert.doesNotMatch(f.byId('food-table').textContent, /04\.10/);
  assert.match(f.byId('price-table').textContent, /43[.,]11/);
  for(const id of ['food-cards','food-table','price-cards','price-table']) {
    assert.doesNotMatch(f.byId(id).innerHTML, /NaN|Infinity|undefined/);
  }
  data.indicators.food.updated_at = '2026-10-06T09:34:00Z';
  assert.doesNotMatch(fixture('data.html', data).byId('food-status').textContent, /время не сохранено/);
  data.indicators.food_history = [];
  const empty = fixture('data.html', data);
  assert.match(empty.byId('food-cards').textContent, /Ряд витрин не сохранён/);
  assert.doesNotMatch(empty.byId('price-table').textContent, /43[.,]11|04\.10/);
});

test('HTTP 200 alert diagnostics are displayed as unknown', () => {
  const data = structuredClone(snapshot);
  data.indicators.alerts = [{at:'2026-10-06T09:34:00Z',http:200,ok:false,kyiv_active:null,reason:'unparsed_client_map'}];
  const f = fixture('metodika.html', data);
  assert.match(f.byId('quality-table').textContent, /Тревоги сейчас.*Неизвестно/);
  assert.match(f.byId('quality-table').textContent, /HTTP 200/);
  assert.doesNotMatch(f.byId('quality-table').textContent, /Тревоги нет/);
});

test('methodology agrees with rent and service status and retains unknown quality', () => {
  const f = fixture('metodika.html');
  assert.match(f.byId('quality-table').textContent, /Только справочные точки/);
  assert.match(f.byId('quality-table').textContent, /0 свежих сообщений об ограничениях, 5/);
  assert.match(f.byId('quality-table').textContent, /успешность не отмечена/);
  assert.doesNotMatch(f.byId('quality-table').textContent, /0\/16|действующих ограничений/);
  assert.match(f.byId('source-commits').textContent, /контрольные суммы 6 входных файлов/);
});
