'use strict';
(() => {
  const q = s => [...document.querySelectorAll(s)];
  const get = (k, d) => { try { return localStorage.getItem(k) || d; } catch (_) { return d; } };
  const put = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
  let state = get('slb-state', 'pa');
  if (!['pa', 'md'].includes(state)) state = 'pa';
  let theme = get('slb-theme', 'light');
  if (!['light', 'dark'].includes(theme)) theme = 'light';
  const toggle = document.getElementById('tg');
  function setTheme() {
    document.documentElement.dataset.theme = theme;
    if (toggle) toggle.textContent = theme === 'light' ? 'Dark mode' : 'Light mode';
  }
  const etDay = ms => new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));
  function refresh(now = Date.now()) {
    let active = 0, expired = 0, ready = 0;
    q('.two-leg-card[data-staged="true"]').forEach(card => {
      const until = Date.parse(card.dataset.reviewUntil);
      const live = Number.isFinite(until) && now < until && etDay(now) === card.dataset.day;
      card.hidden = !live;
      if (live) { active++; if (card.querySelector('.card-status')?.textContent === 'READY') ready++; }
      else expired++;
      card.querySelectorAll('a.fd-slip').forEach(a => {
        if (live) { a.setAttribute('href', a.dataset[state]); a.removeAttribute('aria-disabled'); a.removeAttribute('tabindex'); }
        else { a.removeAttribute('href'); a.setAttribute('aria-disabled','true'); a.setAttribute('tabindex','-1'); }
      });
    });
    const note = document.getElementById('expiry-note');
    if (note) note.textContent = expired ? `${expired} expired/started card(s) hidden. Fresh research is required; this clock does not monitor sportsbook or injury news.` : '';
    const count = document.getElementById('current-count');
    if (count) count.textContent = `${active} staged: ${ready} ready / ${active-ready} conditional.`;
  }
  function setState(s) {
    state = s; put('slb-state',s);
    q('[data-s]').forEach(b => {b.classList.toggle('on', b.dataset.s === s); b.setAttribute('aria-pressed',String(b.dataset.s === s));});
    q('a.fd').forEach(a => {a.href=a.dataset[s];a.textContent=`${s.toUpperCase()} website fallback (not app prefill)`;});
    refresh();
  }
  q('[data-s]').forEach(b => b.addEventListener('click',() => setState(b.dataset.s)));
  q('a.fd-slip').forEach(a => a.addEventListener('click',event => {
    refresh();
    if (!a.hasAttribute('href') || a.getAttribute('aria-disabled') === 'true') event.preventDefault();
  }));
  if (toggle) toggle.addEventListener('click',() => {theme=theme==='light'?'dark':'light';put('slb-theme',theme);setTheme();});
  setTheme(); setState(state);
  setInterval(refresh,30000);
})();
