const finite = x => typeof x === 'number' && Number.isFinite(x);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (x, digits = 1) => finite(x) ? new Intl.NumberFormat('ru-RU', {maximumFractionDigits:digits}).format(x) : '—';
const percent = x => finite(x) ? `${x > 0 ? '+' : ''}${num(x)}%` : 'нет данных';
const short = s => String(s).slice(5).split('-').reverse().join('.');
const time = s => new Intl.DateTimeFormat('ru-RU', {timeZone:'Europe/Kyiv',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(s));
const safeURL = s => { try { const u = new URL(s); return u.protocol === 'https:' ? esc(u.href) : '#'; } catch { return '#'; } };
const STATES = {restricted:'Ограничение сообщено',reserve:'Резервный способ',restored:'Восстановление сообщено',partial:'Частичная доступность',announced:'Ограничение объявлено'};

export function segments(points, key) {
  const lines = []; let line = [];
  for (let i = 0; i < points.length; i++) {
    if (finite(points[i][key])) line.push([i, points[i][key]]);
    else if (line.length) { lines.push(line); line = []; }
  }
  if (line.length) lines.push(line);
  return lines;
}

export function checkSnapshot(data) {
  if (data?.schema_version !== 1 || data?.method_version !== 'episode-comparison-2' ||
      data.causal_effect !== null || data.overall_city_index !== null || !data.as_of ||
      !Array.isArray(data.episodes) || data.episodes.length !== 3) throw new Error('Неподдерживаемый исследовательский срез');
  for (const e of data.episodes) {
    if (!e.id || !e.date || !Array.isArray(e.functions) || !e.trips || !e.networks || !e.alerts)
      throw new Error('Неполный исследовательский срез');
    if (e.trips.week && !e.trips.week.complete && e.trips.week.deviation_percent !== null)
      throw new Error('Неполной неделе присвоен результат');
  }
  return data;
}

function plot(points, keys, eventDate, title, unit, reference = null) {
  const values = points.flatMap(p => keys.map(k => p[k])).filter(finite);
  if (!values.length) return '<p class="no-data">Наблюдений за этот период нет.</p>';
  const width = 940, height = 260, left = 62, right = 15, top = 24, bottom = 40;
  let low = Math.min(...values, ...(finite(reference) ? [reference] : []));
  let high = Math.max(...values, ...(finite(reference) ? [reference] : []));
  const pad = Math.max((high - low) * .16, unit === 'часов' ? .5 : unit === 'индекс' ? .2 : 20);
  low = unit === 'часов' ? 0 : Math.max(0, low - pad); high += pad;
  const x = i => left + i * (width - left - right) / Math.max(points.length - 1, 1);
  const y = v => top + (high - v) / (high - low) * (height - top - bottom);
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)}"><title>${esc(title)}. ${esc(unit)}. Пропуски показаны разрывами.</title>`;
  svg += `<text x="${left}" y="13">${esc(unit)}</text>`;
  for (let i = 0; i < 5; i++) {
    const v = low + i * (high - low) / 4, yy = y(v);
    svg += `<line class="grid" x1="${left}" x2="${width-right}" y1="${yy}" y2="${yy}"/><text x="${left-8}" y="${yy+4}" text-anchor="end">${num(v, unit==='индекс'?1:0)}</text>`;
  }
  if (finite(reference)) svg += `<line class="reference" x1="${left}" x2="${width-right}" y1="${y(reference)}" y2="${y(reference)}"/>`;
  const eventIndex = points.findIndex(p => p.date === eventDate);
  if (eventIndex >= 0) svg += `<line class="event" x1="${x(eventIndex)}" x2="${x(eventIndex)}" y1="${top}" y2="${height-bottom}"/><text x="${x(eventIndex)+5}" y="${top+12}">Начало эпизода</text>`;
  keys.forEach((key, k) => {
    for (const line of segments(points, key)) {
      svg += `<polyline class="${k === 0 ? 'actual' : 'predicted'}" points="${line.map(([i,v])=>`${x(i)},${y(v)}`).join(' ')}"/>`;
      for (const [i,v] of line) svg += `<circle cx="${x(i)}" cy="${y(v)}" r="2.5" fill="${k===0?'var(--blue)':'var(--muted)'}"><title>${esc(points[i].date)}: ${num(v)} ${esc(unit)}</title></circle>`;
    }
  });
  points.forEach((p,i)=>{if(i % 3 === 0 || i === points.length-1) svg += `<text x="${x(i)}" y="${height-12}" text-anchor="middle">${esc(short(p.date))}</text>`;});
  return svg + '</svg>';
}

const range = p => p ? `${short(p.start)}–${short(p.end)}` : '—';
const metric = (title, value, note) => `<div class="research-metric"><h3>${esc(title)}</h3><strong>${esc(value)}</strong><p>${esc(note)}</p></div>`;
const prefixValidation = trips => trips.candidates.find(c=>c.model===trips.selected_model)?.prefix_validation;

function boot(data) {
  const host = id => document.getElementById(id);
  host('research-asof').textContent = time(data.as_of) + ' по Киеву';
  const params = new URLSearchParams(location.search);
  let selected = data.episodes.find(e=>e.id===params.get('episode'))?.id || data.episodes[0].id;
  host('research-content').hidden = false;
  host('research-picker').innerHTML = data.episodes.map(e=>`<button type="button" data-episode="${esc(e.id)}" aria-pressed="false">${esc(e.title)}</button>`).join('');
  host('research-picker').addEventListener('click', event=>{
    const button = event.target.closest('[data-episode]');
    if (!button) return;
    selected = button.dataset.episode;
    const url = new URL(location.href); url.searchParams.set('episode',selected);
    history.replaceState(null,'',url);
    render();
  });
  host('network-base').addEventListener('change',render);

  function render() {
    const e = data.episodes.find(x=>x.id===selected), t = e.trips;
    host('research-picker').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.episode===selected)));
    host('episode-period').textContent = `${short(e.date)}–${short(e.end_date)}.2026 · ${e.scope}`;
    host('episode-title').textContent = e.title;
    const val = prefixValidation(t), p = t.covered_period;
    const conclusion = e.id === 'kyiv-20260908' ?
      `В день атаки учтённые поездки отклонились от прогноза на ${percent(t.day.deviation_percent)}. За 8–14 сентября отклонение составило ${percent(t.week.deviation_percent)}; средняя ошибка прежних недельных прогнозов — ${num(t.selected_validation_week_mae_percent)}%. Поездки вернулись к уровню близкому к прогнозу, при этом режим транспорта с 10 сентября изменился. Длительное падение использования транспорта этим сравнением не подтверждено.` :
      e.id === 'kyiv-20260924' ?
      `За 24–27 сентября учтённые поездки отклонились от прогноза на ${percent(p.deviation_percent)}. Для прежних четырёхдневных окон средняя ошибка — ${num(val['4'].mean_absolute_error_percent)}%. Официально описаны повторные ограничения транспорта и остановка отдельных медицинских услуг. Полной недели и следующих дат поездок нет; срок восстановления оценить нельзя.` :
      'Официальные сообщения описывают ограничения на мостах и нарушение подачи горячей воды. Наблюдения сетей продолжаются, но поездок после 27 сентября источник пока не опубликовал. Потерю поездок и срок восстановления для этого эпизода рассчитать нельзя.';
    host('episode-conclusion').textContent = conclusion;
    host('episode-limits').textContent = e.limits.join(' ');
    const weeks = Number(host('network-base').value), net = e.networks['ping-slash24'].find(x=>x.weeks===weeks && x.date===e.date);
    const alert = e.alerts.find(a=>a.date===e.date);
    const periodTitle = p?.expected_days === 7 ? 'Поездки за первую неделю' : p ? `Поездки за ${p.expected_days} дня` : 'Поездки после начала';
    host('research-metrics').innerHTML =
      metric('Поездки в первый день', t.day ? percent(t.day.deviation_percent) : 'нет данных', t.day ? `${num(t.day.actual,0)} учтённых поездок; отклонение от прогноза.` : `Последняя дата источника: ${short(t.latest_date)}.2026.`) +
      metric(periodTitle, p ? percent(p.deviation_percent) : 'нет данных', p ? `${range(p)}. Средняя ошибка таких прежних прогнозов: ${num(val[String(p.expected_days)].mean_absolute_error_percent)}%.` : 'Отсутствие наблюдений не означает отсутствие поездок.') +
      metric('Сетевой сигнал в первый день', percent(finite(net?.median_index) ? net.median_index-100 : null), `Активные пробы, база ${weeks} недель. Геолокационная группа сетей, не доля жителей со связью.`) +
      metric('Тревоги: часы в записях', num(alert?.recorded_hours), 'В первый день. Часы сверены на выбранных отметках; полнота истории не подтверждена.');
    if (t.status === 'observed') {
      host('rides-note').textContent = `${t.selected_model_name}. Способ выбран по предыдущим 12 неделям; базу после начала эпизода не переобучаем.`;
      host('rides-chart').innerHTML = plot(t.points.map(x=>({...x, actual:finite(x.actual)?x.actual/1000:null,predicted:finite(x.predicted)?x.predicted/1000:null})),['actual','predicted'],e.date,'Учтённые поездки и прогноз','тыс. поездок');
      host('rides-reading').textContent = `Средняя ошибка прежних прогнозов первого дня: ${num(val['1'].mean_absolute_error_percent)}%; диапазон их отклонений: ${percent(val['1'].error_range_percent[0])}…${percent(val['1'].error_range_percent[1])}. Перед эпизодом на графике — отдельный прогноз, построенный до тех семи дней. Для дня начала погода: ${num(t.points.find(x=>x.date===e.date)?.weather?.[0])} °C. Диапазон прежних ошибок не является причинным доверительным интервалом.`;
      const periods = [t.week,t.second_week];
      host('period-table').innerHTML = `<table><thead><tr><th>Период после начала</th><th>Дней с данными</th><th class="numeric">Учтено поездок</th><th class="numeric">Отклонение</th></tr></thead><tbody>${periods.map((q,i)=>`<tr><td>${i===0?'Первая':'Следующая'} неделя: ${range(q)}</td><td>${q.observed_days} из ${q.expected_days}</td><td class="numeric">${num(q.actual,0)}</td><td class="numeric">${q.complete?percent(q.deviation_percent):'не рассчитано'}</td></tr>`).join('')}${!t.week.complete&&p?`<tr><td>Наблюдаемая часть: ${range(p)}</td><td>${p.observed_days} из ${p.expected_days}</td><td class="numeric">${num(p.actual,0)}</td><td class="numeric">${percent(p.deviation_percent)}</td></tr>`:''}</tbody></table>`;
      host('model-table').innerHTML = `<table><caption class="minor">Все способы сравнения. Выбранный выделен; последний столбец относится к ${range(p)}.</caption><thead><tr><th>Способ</th><th class="numeric">Средняя ошибка<br>прежних недель</th><th class="numeric">Смещение<br>прежних недель</th><th class="numeric">Первый день</th><th class="numeric">Наблюдаемый период</th></tr></thead><tbody>${t.candidates.map(c=>`<tr class="${c.model===t.selected_model?'selected':''}"><td>${esc(c.name)}${c.model===t.selected_model?' · выбран':''}</td><td class="numeric">${num(c.mean_absolute_week_error_percent)}%</td><td class="numeric">${percent(c.week_bias_percent)}</td><td class="numeric">${percent(c.day_deviation_percent)}</td><td class="numeric">${percent(c.covered_period?.deviation_percent)}</td></tr>`).join('')}</tbody></table>`;
    } else {
      host('rides-note').textContent = 'Данные АСОП заканчиваются 27 сентября. Октябрьский эффект по этому ряду пока не измеряется.';
      host('rides-chart').innerHTML = '<p class="no-data">Поездок за октябрь в сохранённом источнике нет.</p>';
      host('rides-reading').textContent = 'Цифры сентябрьского индекса не описывают ограничения октября.';
      host('period-table').innerHTML = '';
      host('model-table').innerHTML = '<p class="minor">Модели для октябрьского эпизода не оценены: наблюдаемых поездок за этот период нет.</p>';
    }
    host('function-cards').innerHTML = e.functions.map(f=>{
      const latest = f.updates[f.updates.length-1];
      return `<article class="research-function"><h3>${esc(f.name)}</h3><p class="minor">${esc(f.scope)}</p><span class="badge ${latest.state==='restored'?'good':latest.state==='reserve'?'info':'caution'}">${esc(STATES[latest.state])}</span><ol>${f.updates.map(u=>`<li><time datetime="${esc(u.reported_at)}">Сообщение ${esc(time(u.reported_at))}, Киев</time>${esc(u.summary)}<br><a href="${safeURL(u.source_url)}">${esc(u.source_name)} [официально] ↗</a></li>`).join('')}</ol><p class="minor">Текущее состояние неизвестно. Точная длительность не установлена.</p></article>`;
    }).join('');
    for (const [signal,id] of [['ping-slash24','ping-chart'],['bgp','bgp-chart']]) {
      const points = e.networks[signal].filter(x=>x.weeks===weeks);
      host(id).innerHTML = plot(points,['median_index'],e.date,signal==='bgp'?'Видимость маршрутов BGP':'Активные ответы наблюдаемых сетей','индекс',100);
    }
    host('alert-chart').innerHTML = plot(e.alerts,['recorded_hours'],e.date,'Время тревог в сохранённых записях','часов');
  }
  const c = data.coverage;
  const clock = c.alerts.clock_check;
  host('alert-clock-note').textContent = clock.passed ?
    `На 24–25 сентября часы сверены с ${clock.matched} официальными отметками КМДА: расхождение не превышает ${num(clock.largest_difference_seconds,0)} секунд. Для летнего окна 1 сентября — 5 октября используем время Киева. Полнота истории не подтверждена: это часы в сохранённых записях, а не проверенное полное время тревог. Текущий статус тревоги здесь не показывается.` :
    'Часы не прошли проверку: время тревог не рассчитано. Полнота истории и текущий статус тревоги неизвестны.';
  const sourceLink = label => safeURL(data.sources.find(s=>s.label===label)?.source_url);
  host('source-table').innerHTML = `<table><thead><tr><th>Ряд</th><th>Покрытие</th><th>Ограничение измерения</th></tr></thead><tbody>
    <tr><td><a href="${sourceLink('rides')}">АСОП · КМДА [официально]</a></td><td>${c.rides.start}–${c.rides.end}<br>${c.rides.days} дней; пропусков ${c.rides.missing_days}</td><td>Поездки, а не уникальные люди и не все перемещения.</td></tr>
    <tr><td><a href="https://ioda.inetintel.cc.gatech.edu/">IODA</a></td><td>01.06–05.10.2026<br>${num(c.networks.bgp.slots+c.networks['ping-slash24'].slots,0)} временных слотов</td><td>BGP: шаг 5 минут, ${c.networks.bgp.missing_slots} пропусков. Активные пробы: шаг 10 минут, ${c.networks['ping-slash24'].missing_slots} пропуска. Причину изменений и охват жителей ряд не устанавливает.</td></tr>
    <tr><td><a href="https://open-meteo.com/en/docs/historical-weather-api">Open-Meteo · ERA5</a></td><td>${c.weather.start}–${c.weather.end}<br>${c.weather.days} дней с данными</td><td>Модельная погода в районе города. За запрошенное 1 октября значения отсутствуют.</td></tr>
    <tr><td><a href="https://kyiv.digital/open-api/docs/air-alert.html">Kyiv Digital [официально]</a></td><td>Часы анализируем за 01.09–05.10.2026</td><td>Архив получен 06.10 в 15:41 по Киеву. Совпадение часов проверено на выбранных отметках, полнота истории неизвестна.</td></tr>
    <tr><td>КМДА и департамент здравоохранения [официально]</td><td>Подборка 13 функций в трёх эпизодах</td><td>Сообщения о конкретных услугах; знаменателей жителей, затрат и полного реестра ограничений нет.</td></tr>
    </tbody></table>`;
  render();
}

if (typeof document !== 'undefined') {
  fetch('research_data.json', {cache:'no-store'}).then(r=>{
    if (!r.ok) throw new Error('Исследовательский срез не загружен');
    return r.json();
  }).then(checkSnapshot).then(boot).catch(()=>{
    document.getElementById('research-content').hidden = true;
    const error = document.getElementById('research-error'); error.hidden=false;
    error.textContent='Данные исследования не загружены или не прошли проверку. Показатели за эпизоды недоступны. Описание метода и ссылки остаются ниже.';
    document.getElementById('research-asof').textContent='срез недоступен';
  });
}
