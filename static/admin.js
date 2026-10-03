// t() и errorText() — из i18n.js
const $ = (id) => document.getElementById(id);
const errorBox = $('error');
let me = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: options.body ? {'Content-Type': 'application/json'} : {},
  });
  if (res.status === 401) {
    location.href = '/login';
    throw new Error(t('err.not_authenticated'));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorText(data));
  return data;
}

function showError(e) {
  errorBox.textContent = e ? e.message || String(e) : '';
}

async function run(fn) {
  try {
    await fn();
    showError(null);
  } catch (e) {
    showError(e);
  }
}

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);  // строки добавляются как текст, не как HTML
  return node;
}

function alertOk(text) {
  const ok = el('p', {className: 'ok', role: 'status'}, text);
  errorBox.after(ok);
  setTimeout(() => ok.remove(), 5000);
}

// --- пользователи ---

function renderUser(u) {
  const self = u.id === me.id;
  const info = el('span', {className: 'grow'}, el('span', {className: 'name'}, u.username));
  if (u.is_admin) info.append(el('span', {className: 'badge'}, t('admin.badge')));
  if (self) info.append(el('span', {className: 'who'}, t('admin.you')));

  const pwForm = el('form', {className: 'inline', hidden: true});
  const pwInput = el('input', {type: 'password', placeholder: t('admin.newPw'), minLength: 8, required: true,
                               autocomplete: 'new-password'});
  pwForm.append(pwInput, el('button', {className: 'btn', type: 'submit'}, t('admin.save')));
  pwForm.addEventListener('submit', (e) => {
    e.preventDefault();
    run(async () => {
      await api(`/api/admin/users/${u.id}`, {method: 'PATCH', body: JSON.stringify({password: pwInput.value})});
      pwForm.hidden = true;
      pwInput.value = '';
      alertOk(t('admin.pwChanged', {name: u.username}));
    });
  });

  const actions = el('span', {className: 'row'});
  const pwBtn = el('button', {className: 'link', type: 'button'}, t('admin.pw'));
  pwBtn.addEventListener('click', () => { pwForm.hidden = !pwForm.hidden; if (!pwForm.hidden) pwInput.focus(); });
  actions.append(pwBtn);
  if (!self) {
    const adminBtn = el('button', {className: 'link', type: 'button'},
                        t(u.is_admin ? 'admin.revokeAdmin' : 'admin.makeAdmin'));
    adminBtn.addEventListener('click', () => run(async () => {
      await api(`/api/admin/users/${u.id}`, {method: 'PATCH', body: JSON.stringify({is_admin: !u.is_admin})});
      await loadUsers();
    }));
    const delBtn = el('button', {className: 'del', type: 'button', title: t('admin.delete')}, '×');
    delBtn.setAttribute('aria-label', t('admin.deleteAria', {name: u.username}));
    delBtn.addEventListener('click', () => {
      if (!confirm(t('admin.confirmDelete', {name: u.username}))) return;
      run(async () => {
        await api(`/api/admin/users/${u.id}`, {method: 'DELETE'});
        await Promise.all([loadUsers(), loadTokens()]);
      });
    });
    actions.append(adminBtn, delBtn);
  }

  return el('li', {className: 'wrap'}, info, actions, pwForm);
}

async function loadUsers() {
  const users = await api('/api/admin/users');
  $('users').replaceChildren(...users.map(renderUser));
  const select = $('add-token').elements.namedItem('user_id');
  const current = select.value;
  select.replaceChildren(...users.map((u) => el('option', {value: u.id}, u.username)));
  select.value = current || String(me.id);
}

$('add-user').addEventListener('submit', (e) => {
  e.preventDefault();
  const f = e.target.elements;
  run(async () => {
    await api('/api/admin/users', {method: 'POST', body: JSON.stringify({
      username: f.namedItem('username').value,
      password: f.namedItem('password').value,
      is_admin: f.namedItem('is_admin').checked,
    })});
    e.target.reset();
    await loadUsers();
  });
});

// --- токены ---

function renderToken(tok) {
  const date = new Date(tok.created_at * 1000).toLocaleDateString(document.documentElement.lang);
  const info = el('span', {className: 'grow'}, el('span', {className: 'name'}, tok.name),
                  el('span', {className: 'who'}, t('admin.tokenInfo', {user: tok.username, date})));
  const del = el('button', {className: 'del', type: 'button', title: t('admin.revoke')}, '×');
  del.setAttribute('aria-label', t('admin.revokeAria', {name: tok.name}));
  del.addEventListener('click', () => {
    if (!confirm(t('admin.confirmRevoke', {name: tok.name, user: tok.username}))) return;
    run(async () => {
      await api(`/api/admin/tokens/${tok.id}`, {method: 'DELETE'});
      await loadTokens();
    });
  });
  return el('li', {}, info, del);
}

async function loadTokens() {
  const tokens = await api('/api/admin/tokens');
  $('tokens').replaceChildren(...tokens.map(renderToken));
}

$('add-token').addEventListener('submit', (e) => {
  e.preventDefault();
  const f = e.target.elements;
  run(async () => {
    const tok = await api('/api/admin/tokens', {method: 'POST', body: JSON.stringify({
      user_id: Number(f.namedItem('user_id').value),
      name: f.namedItem('name').value,
    })});
    f.namedItem('name').value = '';
    $('new-token-value').textContent = tok.token;
    $('new-token').hidden = false;
    await loadTokens();
  });
});

$('copy-token').addEventListener('click', () => run(async () => {
  await navigator.clipboard.writeText($('new-token-value').textContent);
  $('copy-token').textContent = t('admin.copied');
}));

$('hide-token').addEventListener('click', () => {
  $('new-token-value').textContent = '';
  $('new-token').hidden = true;
  $('copy-token').textContent = t('admin.copy');
});

run(async () => {
  me = await api('/api/me');
  await Promise.all([loadUsers(), loadTokens()]);
});
