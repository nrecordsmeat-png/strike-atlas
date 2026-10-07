const finite = n => typeof n === 'number' && Number.isFinite(n);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (x,digits=0) => finite(x) ? new Intl.NumberFormat('ru-RU',{maximumFractionDigits:digits}).format(x) : '—';
const safeURL = value => {try {const u=new URL(value);return u.protocol==='https:'?esc(u.href):'#';}catch{return '#';}};
const date = value => new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Kyiv',day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(value));
const qualifier = {exact:'',approximately:'≈ ',greater_than:'> ',less_than:'< '};
const factValue = f => f.value === null ? '' : f.unit==='UAH' ? num(f.value/1000000)+' млн грн' : `${qualifier[f.qualifier] || ''}${num(f.value)}${f.unit==='percent_of_school_students'?'%':''}`;

export function checkCityFunctions(data) {
  if (data?.schema_version!==1 || data.method_version!=='city-functions-1' || data.overall_city_index!==null || data.causal_effect!==null || !data.as_of ||
      !Array.isArray(data.coverage) || !Array.isArray(data.heat?.observations) || !Array.isArray(data.facts) || !Array.isArray(data.medicines?.months)) throw Error('Неподдерживаемый профиль');
  if (data.heat.unique_buildings_affected!==null || data.heat.building_hours_without_heating!==null || data.heat.affected_people!==null) throw Error('Неподтверждённая потеря');
  for (const m of data.medicines.months) {
    if (m.causal_effect!==null || !m.calendar_month_closed && m.prescriptions_per_calendar_day!==null || !Number.isInteger(m.redeemed_prescriptions) || m.redeemed_prescriptions<0) throw Error('Неверная медицинская точка');
  }
  for (const f of data.facts) {
    if (f.duration_hours!==null || f.extra_cost!==null || f.affected_people!==null || f.current_state!=='unknown' || f.kind==='source_conflict' && f.value!==null) throw Error('Неподтверждённый факт');
  }
  return data;
}

export function medicineValue(month, group) {
  if (!month.calendar_month_closed) return null;
  return group==='all' ? month.redeemed_prescriptions : finite(month.groups[group]) ? month.groups[group] : null;
}

function factCard(f, title=null) {
  return `<article class="research-function"><h3>${esc(title || ({restricted:'Потеря услуги',restored:'Восстановление сообщено',reserve:'Работа через резерв',capability:'Резервная возможность',damage_cumulative:'Накопленные повреждения',observed_use:'Использование услуги',source_conflict:'Расхождение в источнике',reported_expenditure:'Выплаченный компонент расходов'}[f.kind] || 'Наблюдение'))}${factValue(f)?` · ${esc(factValue(f))}`:''}</h3><p>${esc(f.summary)}</p><p class="minor">${esc(f.scope)} · ${f.reported_at?esc(date(f.reported_at)):'В январском обзоре; точная дата сообщения не установлена'}</p><a href="${safeURL(f.source_url)}">Источник [официально] ↗</a></article>`;
}

export function heatPlot(rows, attacks) {
  const width=940,height=300,left=62,right=15,top=35,bottom=42;
  const start=Date.parse('2026-01-08T00:00:00+02:00'),end=Date.parse('2026-01-31T00:00:00+02:00');
  const position=stamp=>left+(stamp-start)/(end-start)*(width-left-right);
  const x=day=>position(Date.parse(day+'T12:00:00+02:00'));
  const y=v=>top+(6500-v)/6500*(height-top-bottom);
  let out=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Число домов без отопления по сообщениям, январь 2026"><title>20 отдельных сообщений. Приближённые числа и границы обозначены. Между сообщениями наблюдений нет.</title>`;
  for(let v=0;v<=6000;v+=1500)out+=`<line class="grid" x1="${left}" x2="${width-right}" y1="${y(v)}" y2="${y(v)}"/><text x="${left-8}" y="${y(v)+4}" text-anchor="end">${num(v)}</text>`;
  attacks.forEach(a=>{const xx=position(Date.parse(a+'T00:00:00+02:00'));out+=`<line class="event" x1="${xx}" x2="${xx}" y1="${top}" y2="${height-bottom}"/><text x="${xx+4}" y="${top-12}">Атака ${a.slice(8)}.01</text>`;});
  rows.forEach(r=>{
    // Внутридневное положение соответствует времени публикации, а не времени отключения.
    const xx=r.observation_time_precision==='date_only'?x(r.observed_date):position(Date.parse(r.reported_at)),yy=y(r.value);
    const color=['var(--blue)','var(--amber)','var(--red)'][r.phase-1];
    out+=`<circle cx="${xx}" cy="${yy}" r="4.5" fill="${r.qualifier==='exact'?color:'var(--paper)'}" stroke="${color}" stroke-width="2"><title>${esc(r.observed_date)}: ${esc(factValue(r))} домов без тепла. Фаза ${r.phase}; сведения источника.</title></circle>`;
    if(r.qualifier==='greater_than'||r.qualifier==='less_than')out+=`<text x="${xx+7}" y="${yy+3}">${r.qualifier==='greater_than'?'&gt;':'&lt;'}</text>`;
  });
  for(const d of [9,13,17,20,24,28,30]){const day=`2026-01-${String(d).padStart(2,'0')}`;out+=`<text x="${x(day)}" y="${height-14}" text-anchor="middle">${d}.01</text>`;}
  return out+'</svg>';
}

export function medicinePlot(months, group) {
  const values=months.map(m=>medicineValue(m,group)),good=values.filter(finite);
  if(!good.length)return '<p class="no-data">Сопоставимых календарно завершённых месяцев для этой группы нет. Отсутствующая группа не равна нулю.</p>';
  const w=940,h=270,l=64,r=15,t=25,b=42,high=Math.max(1,...good)*1.15;
  const x=i=>l+i*(w-l-r)/Math.max(1,months.length-1),y=v=>t+(high-v)/high*(h-t-b);
  let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Погашенные рецепты по месяцам"><title>Фактически погашенные рецепты. Пропуски групп и незавершённые месяцы оставлены разрывами.</title>`;
  for(let i=0;i<5;i++){const v=high*i/4;svg+=`<line class="grid" x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}"/><text x="${l-8}" y="${y(v)+4}" text-anchor="end">${num(v/1000,1)}</text>`;}
  svg+=`<text x="${l}" y="13">тыс. рецептов</text>`;
  let line=[];
  const flush=()=>{if(line.length)svg+=`<polyline class="actual" points="${line.map(([i,v])=>`${x(i)},${y(v)}`).join(' ')}"/>`;line=[];};
  values.forEach((v,i)=>{if(!finite(v)){flush();return;}line.push([i,v]);svg+=`<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="var(--blue)"><title>${esc(months[i].month)}: ${num(v)} рецептов. Месячный агрегат, причинный эффект не оценён.</title></circle>`;});flush();
  months.forEach((m,i)=>{if(months.length<=12||i%6===0||i===months.length-1)svg+=`<text x="${x(i)}" y="${h-13}" text-anchor="middle">${esc(months.length<=12?m.month.slice(5):m.month)}</text>`;});
  return svg+'</svg>';
}

export function mountCityFunctions(data, doc=document) {
  checkCityFunctions(data);
  const host=id=>doc.getElementById(id),facts=data.facts,by=id=>facts.find(f=>f.id===id);
  host('city-functions-content').hidden=false;host('city-functions-asof').textContent=date(data.as_of);
  const jan=data.medicines.months.find(m=>m.month==='2022-01'),march=data.medicines.months.find(m=>m.month==='2022-03');
  const decline=jan&&march?(march.redeemed_prescriptions/jan.redeemed_prescriptions-1)*100:null;
  host('city-function-results').innerHTML=
    `<div class="research-metric"><h3>Повторная потеря отопления</h3><strong>Три атаки</strong><p>9, 20 и 24 января. После почти завершённого восстановления тысячи домов снова без тепла.</p></div>`+
    `<div class="research-metric"><h3>Получение лекарств в городе</h3><strong>${finite(decline)?num(decline,1)+'%':'нет данных'}</strong><p>Март к январю 2022: погашенные рецепты. Наблюдаемое изменение; влияние бомбардировок отдельно не выделено.</p></div>`+
    `<div class="research-metric"><h3>Сохранение медицинской функции</h3><strong>${num(by('boilers13').value)} больниц</strong><p>Сообщено о работе мобильных котельных. Сохранённое тепло требует ресурсов; размер затрат неизвестен.</p></div>`+
    `<div class="research-metric"><h3>Учебные заведения с повреждениями</h3><strong>${num(by('education310').value)}</strong><p>С начала вторжения по 6 июля 2026. Накопленные повреждения; число действующих и восстановленных не определено.</p></div>`;
  host('city-function-coverage').innerHTML=`<table><caption>Что собрали и какой вывод позволяет сделать каждый вид данных</caption><thead><tr><th>Функция</th><th>Что есть</th><th>Что это показывает</th><th>Чего не хватает для потерь</th></tr></thead><tbody>${data.coverage.map(c=>`<tr><td><strong>${esc(c.name)}</strong><br><span class="minor">${esc(c.status)}</span></td><td>${esc(c.have)}</td><td>${esc(c.shows)}</td><td>${esc(c.need)}</td></tr>`).join('')}</tbody></table>`;
  host('heat-conclusion').textContent=data.heat.conclusion;
  host('heat-impact-chart').innerHTML=heatPlot(data.heat.observations,data.heat.attack_dates);
  host('heat-impact-table').innerHTML=`<table><thead><tr><th>Дата сведения</th><th>Фаза</th><th class="numeric">Домов без тепла</th><th>Публикация / источник</th></tr></thead><tbody>${data.heat.observations.map(r=>`<tr><td>${esc(r.observed_date)}</td><td>После атаки ${r.phase===1?'9':r.phase===2?'20':'24'} января</td><td class="numeric">${esc(factValue(r))}</td><td><a href="${safeURL(r.source_url)}">${esc(date(r.reported_at))} [официально] ↗</a>${r.observation_time_precision==='date_only'?'<br>О предыдущем вечере; точный час неизвестен':''}</td></tr>`).join('')}</tbody></table>`;
  host('recovery-resources').innerHTML=['bonuses44','boilers18','boilers13'].map(id=>factCard(by(id))).join('');
  host('water-impact-facts').innerHTML=['water11','water20','water24restore','combined600','water_reserve'].map(id=>factCard(by(id))).join('');
  host('medicine-observed-change').textContent=jan&&march?`В январе 2022 в аптеках города погасили ${num(jan.redeemed_prescriptions)} рецептов, в марте — ${num(march.redeemed_prescriptions)} (${num(decline,1)}%). Оба месяца — 31 день. Число аптечных точек с записями снизилось с ${num(jan.dispensing_sites_with_records)} до ${num(march.dispensing_sites_with_records)}. Это не доказательство закрытия остальных аптек: нет записи — не обязательно нет работы. Перемещение людей, доступность препаратов и изменения программы также влияют на ряд.`:'Сравнения за начало 2022 нет.';
  const years=[...new Set(data.medicines.months.map(m=>m.month.slice(0,4)))];
  host('medicine-year').innerHTML=`<option value="all">Вся история ${esc(years[0])}–${esc(years.at(-1))}</option>`+years.map(y=>`<option value="${y}">${y}</option>`).join('');
  host('medicine-year').value='2026';
  host('medicine-group').innerHTML='<option value="all">Все группы программы</option>'+data.medicines.groups.map(g=>`<option value="${esc(g)}">${esc(g)}</option>`).join('');host('medicine-group').value='all';
  function renderMedicine() {
    const year=host('medicine-year').value,group=host('medicine-group').value;
    const months=data.medicines.months.filter(m=>year==='all'||m.month.startsWith(year));
    host('medicine-use-chart').innerHTML=medicinePlot(months,group);
    host('medicine-use-note').textContent='Месячные объёмы. Незавершённый месяц не включён в линию. Общая программа расширяется: для чтения изменений выбирайте также отдельные группы. Их состав и правила всё равно требуют проверки.';
    host('medicine-use-table').innerHTML=`<table><thead><tr><th>Месяц</th><th class="numeric">Погашено рецептов</th><th class="numeric">На календарный день</th><th>Аптек с записями<br>по всей программе</th><th>Качество периода</th></tr></thead><tbody>${months.map(m=>{const value=group==='all'?m.redeemed_prescriptions:m.groups[group];const days=new Date(Number(m.month.slice(0,4)),Number(m.month.slice(5)),0).getDate();return `<tr><td>${esc(m.month)}</td><td class="numeric">${num(value)}</td><td class="numeric">${num(m.calendar_month_closed&&finite(value)?value/days:null,1)}</td><td>${num(m.dispensing_sites_with_records)}</td><td>${m.calendar_month_closed?'Месяц завершён; полнота отчётности не проверена':'Незавершённый месяц: не сравниваем'}<br><span class="minor">Срез ${esc(m.source_updated_at)}</span></td></tr>`;}).join('')}</tbody></table>`;
  }
  host('medicine-year').addEventListener('change',renderMedicine);host('medicine-group').addEventListener('change',renderMedicine);renderMedicine();
  host('medicine-use-limits').innerHTML=data.medicines.limitations.map(p=>`<p>${esc(p)}</p>`).join('')+`<p><a href="${safeURL(data.medicines.source_url)}">НСЗУ: набор данных и версии выгрузок [официально] ↗</a></p>`;
  host('medicine-reserve-facts').innerHTML=['boilers18','medicine_primary','medicine_specialists'].map(id=>factCard(by(id))).join('');
  host('education-impact-facts').innerHTML=['education85','education310','education45','education51','remote11','remote5'].map(id=>factCard(by(id))).join('');
  const d=data.causal_design;
  host('city-effect-method').innerHTML=`<p><strong>1. Прямая потеря услуги.</strong> ${esc(d.direct_reported_loss)}</p><p><strong>2. Дополнительный сбой после очередной атаки.</strong> ${esc(d.short_term_deviation)}</p><p><strong>3. Накопленные потери.</strong> ${esc(d.long_term_loss)}</p><p><strong>4. Цена сохранённой активности.</strong> ${esc(d.adaptation)}</p><p><strong>Чтобы оценить причинный эффект:</strong> ${d.comparison_requirements.map(esc).join('; ')}.</p><p>Следим за потерянным объёмом услуги, масштабом затронутой группы, остатком невосстановленной функции и дополнительными затратами. Все четыре величины нужны отдельно: выполненный объём может вернуться, пока люди продолжают тратить больше денег и времени.</p><p>Выбрать соседний город «контролем» недостаточно: общая энергосеть, другие удары и перемещение людей могут менять обе группы. Для повторных ударов нужны отдельные фазы и проверки; готовую схему однократного воздействия автоматически не применяем. <a href="https://arxiv.org/abs/1803.09015">Исследование сравнений с несколькими периодами ↗</a></p><p class="info-strip">Общего причинного процента потери городской жизни сейчас нет. Для работы и торговли отсутствует нужный ряд; суммировать поездки, рецепты, повреждения и посты с произвольными весами нельзя.</p>`;
  const rows=data.medicines.source_versions.reduce((n,s)=>n+s.source_rows,0);
  host('city-source-audit').innerHTML=`<table><caption>Проверка источников и фактический объём нового сбора</caption><thead><tr><th>Источник</th><th>Результат проверки</th><th>Статус использования</th></tr></thead><tbody><tr><td>НСЗУ [официально]</td><td>${num(rows)} строк в ${data.medicines.source_versions.length} годовых выгрузках; ${data.medicines.months.length} месяцев города. Проверены коды географии, целые счётчики и повторы.</td><td>Агрегаты по месяцам и группам. Сохранены хеши полных исходников; архив проекта содержит производные агрегаты.</td></tr><tr><td>КМДА и городские департаменты [официально]</td><td>${data.source_archive_count} точных архивов ответов; ${data.heat.observations.length} сообщений о тепле и ${data.facts.length} дополнительных фактов.</td><td>Исторические сведения. Молчание источника не закрывает перебой.</td></tr><tr><td>Автономность медицинской сети</td><td>${esc(by('autonomy_conflict').summary)}</td><td>Числовая доля исключена. <a href="${safeURL(by('autonomy_conflict').source_url)}">Источник ↗</a></td></tr><tr><td>Открытые данные Киева [официально]</td><td>Проверены запросы о потреблении, медицинских услугах, торговле и образовании. Найденные перечни объектов и оборудования не являются рядами использования.</td><td>Не подставляем реестр вместо оборота или фактических услуг.</td></tr><tr><td>NASA Black Marble</td><td>При загрузке файла получена страница Earthdata вместо спутниковых данных.</td><td>Яркость пока не подключена. Нужны доступ, маски облаков/снега и актуальное наблюдение; старое заполнение пропуска не равно свету сегодня. <a href="https://landweb.modaps.eosdis.nasa.gov/data/userguide/BlackMarbleUserGuide_Collection2.0_20241203.pdf">Описание продукта ↗</a></td></tr></tbody></table>`;
}

if(typeof document!=='undefined')fetch('city_functions_data.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Данные не загружены');return r.json();}).then(checkCityFunctions).then(data=>mountCityFunctions(data)).catch(()=>{
  document.getElementById('city-functions-content').hidden=true;
  const error=document.getElementById('city-functions-error');error.hidden=false;error.textContent='Данные городских функций не загружены или не прошли проверку. Количественные выводы недоступны; транспортный разбор имеет отдельный срез.';
});
