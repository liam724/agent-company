(function () {
  var token = new URLSearchParams(location.search).get('token') || '';
  var who = document.getElementById('who'), f = document.getElementById('manage');
  fetch('/api/me?token=' + encodeURIComponent(token)).then(function (r) { return r.json(); }).then(function (d) {
    if (d.error) { who.textContent = d.error; return; }
    who.textContent = d.email + ' · ' + (d.plan === 'pro' ? 'Pro' : 'Free plan');
    f.models.value = d.watches.join(', ');
    if (d.plan === 'pro') { document.getElementById('hookrow').hidden = false; f.webhook.value = d.webhook || ''; }
    document.getElementById('unsub').href = '/api/unsubscribe?token=' + encodeURIComponent(token);
    f.hidden = false;
  }).catch(function () { who.textContent = 'Could not reach the alert service.'; });
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var msg = f.querySelector('.result');
    fetch('/api/manage', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token: token, models: f.models.value, webhook: f.webhook.value})})
      .then(function (r) { return r.json(); })
      .then(function (d) { msg.textContent = d.message || d.error; })
      .catch(function () { msg.textContent = 'Could not reach the alert service.'; });
  });
})();
