(() => {
  const rid = () => (crypto.randomUUID
    ? crypto.randomUUID()
    : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const sid = sessionStorage.getItem('sid') || rid();
  sessionStorage.setItem('sid', sid);
  const device = innerWidth < 768 ? 'mobile' : innerWidth < 1024 ? 'tablet' : 'desktop';

  const send = (payload) => {
    const data = JSON.stringify({
      session_id: sid, page: location.pathname, device,
      viewport_w: innerWidth, referrer: document.referrer, ...payload
    });
    navigator.sendBeacon('/api/analytics/collect',
      new Blob([data], { type: 'application/json' }));
  };

  // 1. page_view
  send({ event_type: 'page_view' });

  // 2. section_view — fires once per section when 50% visible
  const seen = new Set();
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting && !seen.has(e.target.id)) {
        seen.add(e.target.id);
        send({ event_type: 'section_view', section: e.target.id });
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('section[id], div[id].section')
    .forEach(s => io.observe(s));

  // 3. cta_click — any link or button
  document.addEventListener('click', ev => {
    const el = ev.target.closest('a, button');
    if (el) send({
      event_type: 'cta_click',
      label: el.id || el.getAttribute('href') || el.textContent.trim().slice(0, 40)
    });
  });

  // 4. form_funnel — view / start / submit
  const form = document.querySelector('form');
  if (form) {
    send({ event_type: 'form_funnel', label: 'view' });
    form.addEventListener('focusin', () => {
      if (!form.dataset.started) {
        form.dataset.started = '1';
        send({ event_type: 'form_funnel', label: 'start' });
      }
    });
    form.addEventListener('submit', () =>
      send({ event_type: 'form_funnel', label: 'submit' }));
  }
})();