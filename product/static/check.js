// "Check your code": match pasted text against the registry, entirely in the browser.
(function () {
  var box = document.getElementById('paste'), out = document.getElementById('paste-result');

  var models = null;
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function slug(id) { return id.replace(/[^A-Za-z0-9._-]/g, '-'); }
  function run() {
    var text = box.value;
    if (!text.trim()) { out.innerHTML = ''; return; }
    var seen = {}, rows = [];
    models.forEach(function (m) {
      var re = new RegExp('(^|[^A-Za-z0-9_-])' + m.id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![A-Za-z0-9_-])(?!\\.[A-Za-z0-9])');
      if (!re.test(text) || seen[m.key]) return;
      seen[m.key] = 1;
      var what = m.status === 'retired' ? 'was retired on ' + m.retires
        : m.status === 'retiring' ? 'retires on ' + m.retires + ' (in ' + m.days_left + ' days)'
        : m.status === 'deprecated' ? 'is deprecated, no retirement date yet'
        : m.not_before ? 'is active, not retired before ' + m.not_before : 'is active';
      rows.push('<div class="hit"><span class="badge ' + m.status + '">' + m.status + '</span> <a href="/models/' +
        esc(m.provider) + '/' + esc(slug(m.id)) + '/"><code>' + esc(m.id) + '</code></a> ' + esc(what) +
        (m.replacement ? '. Replacement: <code>' + esc(m.replacement) + '</code>' : '') + '</div>');
    });
    out.innerHTML = rows.length ? rows.join('') : '<p class="muted">No tracked model IDs found in that text.</p>';
  }
  if (box) box.addEventListener('input', function () {
    if (models) return run();
    fetch('/api/v1/models.json').then(function (r) { return r.json(); }).then(function (d) { models = d.models; run(); })
      .catch(function () { out.innerHTML = '<p class="muted">Could not load the registry.</p>'; });
  });
  // Progressive enhancement for the subscribe forms: stay on the page and show the result.
  document.querySelectorAll('form.subscribe[action]').forEach(function (f) {
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var msg = f.querySelector('.result') || f.appendChild(document.createElement('p'));
      msg.className = 'result note'; msg.textContent = 'Sending…';
      fetch(f.action, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email: f.email.value, models: f.models.value, website: f.website.value})})
        .then(function (r) { return r.json(); })
        .then(function (d) { msg.textContent = d.message || d.error || 'Something went wrong.'; })
        .catch(function () { msg.textContent = 'Could not reach the alert service. Please try again later.'; });
    });
  });
})();
