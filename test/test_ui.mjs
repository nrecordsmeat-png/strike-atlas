// Node-only smoke checks of the real client script with a minimal DOM adapter.
// This checks rendering and event handlers, not browser layout or accessibility.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';

const html = readFileSync(fileURLToPath(new URL('./overview.html', import.meta.url)), 'utf8');
const payload = html.match(/<script id="city-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
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

function fixture(data = JSON.parse(payload)) {
  const elements = parse(html.split('<script id="city-data"')[0]);
  const dataElement = new Element('script', { id: 'city-data' }, JSON.stringify(data));
  elements.push(dataElement);
  const all = () => elements.flatMap(element => [element, ...element.children]);
  function matches(element, selector) {
    if (selector === '.plot') return (element.attrs.class || '').split(' ').includes('plot');
    if (selector === "section[id^='view-']") return element.tag === 'section' && element.attrs.id?.startsWith('view-');
    const match = selector.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
    if (!match) throw new Error(`Unsupported test selector: ${selector}`);
    return Object.hasOwn(element.attrs, match[1]) && (match[2] === undefined || element.attrs[match[1]] === match[2]);
  }
  const document = {
    getElementById(id) { const value = all().find(x => x.attrs.id === id); assert.ok(value, `Unknown DOM id: ${id}`); return value; },
    querySelectorAll(selector) { return all().filter(x => matches(x, selector)); },
    querySelector(selector) { return this.querySelectorAll(selector)[0]; },
  };
  vm.runInNewContext(script, { document, Intl, Date, URL, console });
  return { document, byId: id => document.getElementById(id), button: (key, value) => document.querySelector(`[data-${key}="${value}"]`) };
}

test('snapshot renders attributed data without fake service recovery', () => {
  const f = fixture();
  assert.match(f.byId('hero-meta').textContent, /5 эпизодов/);
  assert.match(f.byId('hero-meta').textContent, /Сообщений о завершении эпизода: 0/);
  assert.match(f.byId('topic-grid').textContent, /18,2 мин/);
  assert.match(f.byId('recovery-box').textContent, /300/);
  assert.match(f.byId('episode-detail').textContent, /Не установлена/);
});

test('every navigation handler selects one panel and renders finite chart points', () => {
  const f = fixture();
  for (const name of ['services', 'dynamics', 'quality', 'scenarios', 'overview']) {
    f.button('view', name).fire();
    const visible = f.document.querySelectorAll("section[id^='view-']").filter(x => !x.hidden);
    assert.deepEqual(visible.map(x => x.attrs.id), [`view-${name}`]);
  }
  for (const plot of f.document.querySelectorAll('.plot')) {
    assert.match(plot.innerHTML, /<circle/);
    assert.doesNotMatch(plot.innerHTML, /NaN|Infinity|undefined/);
  }
});

test('earlier date hides future measurements and weekly recovery', () => {
  const f = fixture(), picker = f.byId('day-picker');
  picker.value = '2026-10-01'; picker.fire('change');
  assert.match(f.byId('hero-meta').textContent, /1 эпизодов/);
  assert.match(f.byId('topic-grid').textContent, /Нет замера/);
  assert.doesNotMatch(f.byId('recovery-box').textContent, /300/);
  picker.value = '2026-10-05'; picker.fire('change');
  assert.match(f.byId('topic-grid').textContent, /25,9 мин/);
  assert.doesNotMatch(f.byId('traffic-table').textContent, /06\.10/);
});

test('overview links and service filters keep the selected context', () => {
  const f = fixture();
  f.button('topic', 'water_heat').fire();
  assert.equal(f.byId('service-filter').value, 'water_heat');
  assert.equal(f.document.querySelectorAll('[data-episode]').length, 1);
  assert.match(f.byId('episode-detail').textContent, /Деснянском/);
  f.button('topic', 'power').fire();
  assert.equal(f.document.querySelectorAll('[data-episode]').length, 0);
  assert.match(f.byId('episode-detail').textContent, /300/);
  f.button('open-episode', 'north-bridge-20261003').fire();
  assert.equal(f.byId('service-filter').value, 'all');
  assert.match(f.byId('episode-detail').textContent, /Северному/);
});

test('quality display preserves unknown legacy quality', () => {
  const f = fixture();
  assert.match(f.byId('quality-table').textContent, /успешность не отмечена/);
  assert.doesNotMatch(f.byId('quality-table').textContent, /0\/16|полки стабильны/);
});

test('missing observations remain missing instead of producing a healthy city', () => {
  const data = JSON.parse(payload);
  for (const state of Object.values(data.history)) {
    state.episodes = []; state.recovery_reports = [];
    state.counts = { total: 0, restored: 0, unclosed: 0, unknown: 0, fresh_restrictions: 0 };
  }
  data.indicators.traffic = []; data.indicators.uz = []; data.indicators.rent = [];
  data.indicators.food = { status: 'missing', categories: 0 };
  const f = fixture(data);
  assert.match(f.byId('hero-title').textContent, /Наблюдений для общей оценки пока недостаточно/);
  assert.match(f.byId('topic-grid').textContent, /Нет замера/);
  assert.match(f.byId('episode-list').textContent, /Отсутствие записей не доказывает отсутствие перебоев/);
  assert.doesNotMatch(f.byId('topic-grid').textContent, /стабильны|без перебоев|0 категорий/);
});

test('six scenario handlers render distinct outcomes outside the real ledger', () => {
  const f = fixture(), before = f.byId('hero-meta').textContent;
  for (const scenario of JSON.parse(payload).scenarios) {
    f.button('scenario', scenario.id).fire();
    assert.match(f.byId('scenario-outcome').textContent, new RegExp(scenario.title));
    assert.equal(f.byId('hero-meta').textContent, before);
  }
  f.button('scenario', 'restored').fire();
  assert.match(f.byId('scenario-outcome').textContent, /Длительность перебоя8 ч/);
  f.button('scenario', 'silence').fire();
  assert.match(f.byId('scenario-outcome').textContent, /Текущее состояние неизвестно/);
  assert.match(f.byId('scenario-outcome').textContent, /Длительность перебояНе установлена/);
  f.button('scenario', 'duplicate').fire();
  assert.match(f.byId('scenario-outcome').textContent, /Сообщений после удаления дублей1/);
});

test('source-supplied markup is escaped by actual client rendering', () => {
  const data = JSON.parse(payload), day = Object.keys(data.history).at(-1);
  data.history[day].episodes[0].title = '<img src=x onerror=alert(1)>';
  data.history[day].episodes[0].updates[0].summary = '<script>alert(1)</script>';
  const f = fixture(data);
  assert.match(f.byId('episode-detail').innerHTML, /&lt;img/);
  assert.match(f.byId('episode-detail').innerHTML, /&lt;script/);
  assert.doesNotMatch(f.byId('episode-detail').innerHTML, /<img|<script/);
});
