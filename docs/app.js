/* Happenstance front-end logic */
 (async function(){
  const state = {
    restaurants: [],
    events: [],
    config: { branding: { site_title: 'Happenstance', logo_url: '' }, pairing_rules: [] },
    sort: { key: null, dir: 1 },
    filter: '',
    layout: 'cards'
  };

  async function fetchJSON(path){
    try { const r = await fetch(path); if(!r.ok) throw new Error(r.status); return await r.json(); } catch { return []; }
  }

  async function init(){
    [state.restaurants, state.events, state.config] = await Promise.all([
      fetchJSON('restaurants.json'),
      fetchJSON('events.json'),
      fetchJSON('config.json')
    ]);
    applyBranding();
    bind();
    render();
  }

  function applyBranding(){
    document.title = state.config.branding?.site_title || 'Happenstance';
    document.getElementById('site-title').textContent = state.config.branding?.site_title || 'Happenstance';
    const logo = document.getElementById('logo');
    if(state.config.branding?.logo_url){ logo.src = state.config.branding.logo_url; logo.style.display='block'; } else { logo.style.display='none'; }
  }

  function bind(){
    document.getElementById('view-select').addEventListener('change', ()=>{ resetSort(); render(); });
    document.getElementById('theme-select').addEventListener('change', e => document.body.className = e.target.value);
    document.getElementById('filter').addEventListener('input', e => { state.filter = e.target.value.toLowerCase(); render(); });
    const layoutSel = document.getElementById('layout-select');
    if(layoutSel){ layoutSel.addEventListener('change', e=>{ state.layout = e.target.value; render(); }); }
    const sortSel = document.getElementById('sort-select');
    if(sortSel){ sortSel.addEventListener('change', e=>{ const val = e.target.value; if(!val){ state.sort.key=null; render(); return;} const [k,dir] = val.split(':'); state.sort.key = k; state.sort.dir = dir==='desc' ? -1:1; render(); }); }
  }

  function resetSort(){ state.sort = { key:null, dir:1 }; const sortSel = document.getElementById('sort-select'); if(sortSel) sortSel.value=''; }

  function sortBy(key, data){
    if(state.sort.key === key){ state.sort.dir *= -1; } else { state.sort.key = key; state.sort.dir = 1; }
    data.sort((a,b)=> (a[key]||'').localeCompare(b[key]||'') * state.sort.dir);
  }

  function table(headers, rows){
    const table = document.createElement('table');
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    headers.forEach(h => { const th = document.createElement('th'); th.textContent = h.label; th.addEventListener('click', ()=>{ sortBy(h.key, rows); render(); }); trh.appendChild(th); });
    thead.appendChild(trh); table.appendChild(thead);
    const tbody = document.createElement('tbody');
    rows.forEach(r => {
      const tr = document.createElement('tr');
      headers.forEach(h => { const td = document.createElement('td'); if(h.render){ td.appendChild(h.render(r)); } else { td.textContent = r[h.key] || ''; } tr.appendChild(td); });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  function filterItems(items, keys){
    if(!state.filter) return items;
    return items.filter(it => keys.some(k => (it[k]||'').toLowerCase().includes(state.filter)));
  }

  function fuzzyMatch(a,b){ if(!a||!b) return false; a=a.toLowerCase(); b=b.toLowerCase(); return a.includes(b) || b.includes(a); }

  function computePairs(){
    const rules = state.config.pairing_rules || [];
    const pairs = [];
    state.events.forEach(ev => {
      state.restaurants.forEach(rest => {
        let reasons = [];
        rules.forEach(rule => {
          if(rule.match_on === 'category'){
            if((ev.category||'').toLowerCase().includes((rest.cuisine||'').toLowerCase()) || (rest.cuisine||'').toLowerCase().includes((ev.category||'').toLowerCase())){
              reasons.push('category match');
            }
          } else if(rule.match_on === 'location' && rule.fuzzy_match){
            if(fuzzyMatch(ev.venue, rest.address)) reasons.push('location proximity');
          }
        });
        if(reasons.length){
          pairs.push({ event_name: ev.name, date: ev.date, rest_name: rest.name, cuisine: rest.cuisine, match_reason: reasons.join(', ') });
        }
      });
    });
    return pairs;
  }

  function ensureSortOptions(view){
    const sel = document.getElementById('sort-select'); if(!sel) return; sel.innerHTML='';
    const optEmpty = document.createElement('option'); optEmpty.value=''; optEmpty.textContent='(none)'; sel.appendChild(optEmpty);
    const add = (k,label)=>{ const o=document.createElement('option'); o.value=k+':asc'; o.textContent=label; sel.appendChild(o);};
    if(view==='restaurants'){ add('name','Name'); add('cuisine','Cuisine'); }
    else if(view==='events'){ add('date','Date'); add('name','Name'); add('venue','Venue'); }
    else { add('event_name','Event'); add('rest_name','Restaurant'); add('date','Date'); }
  }

  function applySort(data){
    if(!state.sort.key) return data;
    return data.slice().sort((a,b)=> (a[state.sort.key]||'').localeCompare(b[state.sort.key]||'') * state.sort.dir);
  }

  function createRestaurantCard(r){
    const el = document.createElement('div'); el.className='card fade-in';
    const title = document.createElement('h3'); title.textContent = r.name || '(Unnamed)';
    if(r.is_new){ const badge=document.createElement('span'); badge.className='new-badge'; badge.textContent=r.badge||'New'; title.appendChild(badge); }
    el.appendChild(title);
    const meta = document.createElement('div'); meta.className='meta'; meta.innerHTML=`<span>${r.cuisine||''}</span><span>${r.address||''}</span>`; el.appendChild(meta);
    const desc = document.createElement('p'); desc.textContent = r.description || ''; el.appendChild(desc);
    if(r.link){ const a=document.createElement('a'); a.href=r.link; a.className='inline-link'; a.target='_blank'; a.rel='noopener noreferrer'; a.textContent='Website →'; el.appendChild(a); }
    return el;
  }

  function createEventCard(ev){
    const el = document.createElement('div'); el.className='card fade-in';
    const title = document.createElement('h3'); title.textContent = ev.name || '(Unnamed)';
    if(ev.is_new){ const badge=document.createElement('span'); badge.className='new-badge'; badge.textContent=ev.badge||'New'; title.appendChild(badge); }
    el.appendChild(title);
    const meta = document.createElement('div'); meta.className='meta'; meta.innerHTML=`<span>${ev.date||''}</span><span>${ev.venue||''}</span><span>${ev.category||''}</span>`; el.appendChild(meta);
    const desc = document.createElement('p'); desc.textContent = ev.description || ''; el.appendChild(desc);
    if(ev.link){ const a=document.createElement('a'); a.href=ev.link; a.className='inline-link'; a.target='_blank'; a.rel='noopener noreferrer'; a.textContent='Details →'; el.appendChild(a); }
    return el;
  }

  function countsText(view, n){
    const counts = document.getElementById('counts'); if(!counts) return; counts.textContent = `${view} • ${n}`;
  }

  function render(){
    const view = document.getElementById('view-select').value;
    const container = document.getElementById('content');
    container.innerHTML = '';
    ensureSortOptions(view);
    if(view === 'restaurants'){
      let data = filterItems([...state.restaurants], ['name','cuisine','description','address']);
      data = applySort(data);
      if(state.layout==='cards'){
        const grid=document.createElement('div'); grid.className='grid cards-restaurants';
        data.forEach(r=> grid.appendChild(createRestaurantCard(r)));
        container.appendChild(grid);
      } else {
        const headers = [
          {key:'name', label:'Name'},
          {key:'address', label:'Address'},
          {key:'cuisine', label:'Cuisine'},
          {key:'description', label:'Description'},
          {key:'link', label:'Link', render: r=>{ const a=document.createElement('a'); a.href=r.link; a.textContent='Link'; a.target='_blank'; return a;}},
          {key:'badge', label:'Badge', render: r=>{ const span=document.createElement('span'); span.className='badge-cell'; if(r.is_new){ const b=document.createElement('span'); b.className='new-badge'; b.textContent=r.badge||'New!'; span.appendChild(b);} return span; }}
        ];
        container.appendChild(table(headers, data));
      }
      countsText('Restaurants', data.length);
    } else if(view === 'events'){
      let data = filterItems([...state.events], ['name','date','venue','category','description']);
      data = applySort(data);
      if(state.layout==='cards'){
        const grid=document.createElement('div'); grid.className='grid cards-events';
        data.forEach(ev=> grid.appendChild(createEventCard(ev)));
        container.appendChild(grid);
      } else {
        const headers = [
          {key:'name', label:'Name'},
          {key:'date', label:'Date'},
          {key:'venue', label:'Venue'},
          {key:'category', label:'Category'},
          {key:'description', label:'Description'},
          {key:'link', label:'Link', render: r=>{ const a=document.createElement('a'); a.href=r.link; a.textContent='Link'; a.target='_blank'; return a;}},
          {key:'badge', label:'Badge', render: r=>{ const span=document.createElement('span'); span.className='badge-cell'; if(r.is_new){ const b=document.createElement('span'); b.className='new-badge'; b.textContent=r.badge||'New!'; span.appendChild(b);} return span; }}
        ];
        container.appendChild(table(headers, data));
      }
      countsText('Events', data.length);
    } else { // paired
      const pairs = computePairs();
      let data = filterItems(pairs, ['event_name','rest_name','cuisine','match_reason']);
      data = applySort(data);
      const headers = [ {key:'event_name', label:'Event'}, {key:'date', label:'Date'}, {key:'rest_name', label:'Restaurant'}, {key:'cuisine', label:'Cuisine'}, {key:'match_reason', label:'Match Reason'} ];
      container.appendChild(table(headers, data));
      countsText('Pairs', data.length);
    }
  }

  init();
})();
