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
    throw new Error('Нужно войти');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (typeof data.detail === 'string') throw new Error(data.detail);
    if (Array.isArray(data.detail) && data.detail[0]?.msg) throw new Error('Проверьте поля: ' + data.detail[0].msg);
    throw new Error('Ошибка сервера');
  }
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

// --- пользователи ---

function renderUser(u) {
  const self = u.id === me.id;
  const name = el('span', {className: 'name'}, u.username);
  const info = el('span', {className: 'grow'}, name);
  if (u.is_admin) info.append(el('span', {className: 'badge'}, 'админ'));
  if (self) info.append(el('span', {className: 'who'}, 'это вы'));

  const pwForm = el('form', {className: 'inline', hidden: true});
  const pwInput = el('input', {type: 'password', placeholder: 'Новый пароль', minLength: 8, required: true,
                               autocomplete: 'new-password'});
  pwForm.append(pwInput, el('button', {className: 'btn', type: 'submit'}, 'Сохранить'));
  pwForm.addEventListener('submit', (e) => {
    e.preventDefault();
    run(async () => {
      await api(`/api/admin/users/${u.id}`, {method: 'PATCH', body: JSON.stringify({password: pwInput.value})});
      pwForm.hidden = true;
      pwInput.value = '';
      alertOk(`Пароль ${u.username} изменён, все его устройства разлогинены`);
    });
  });

  const actions = el('span', {className: 'row'});
  const pwBtn = el('button', {className: 'link', type: 'button'}, 'Пароль');
  pwBtn.addEventListener('click', () => { pwForm.hidden = !pwForm.hidden; if (!pwForm.hidden) pwInput.focus(); });
  actions.append(pwBtn);
  if (!self) {
    const adminBtn = el('button', {className: 'link', type: 'button'}, u.is_admin ? 'Снять админа' : 'Сделать админом');
    adminBtn.addEventListener('click', () => run(async () => {
      await api(`/api/admin/users/${u.id}`, {method: 'PATCH', body: JSON.stringify({is_admin: !u.is_admin})});
      await loadUsers();
    }));
    const delBtn = el('button', {className: 'del', type: 'button', title: 'Удалить'}, '×');
    delBtn.setAttribute('aria-label', `Удалить пользователя ${u.username}`);
    delBtn.addEventListener('click', () => {
      if (!confirm(`Удалить пользователя ${u.username}? Его токены тоже удалятся.`)) return;
      run(async () => {
        await api(`/api/admin/users/${u.id}`, {method: 'DELETE'});
        await Promise.all([loadUsers(), loadTokens()]);
      });
    });
    actions.append(adminBtn, delBtn);
  }

  return el('li', {className: 'wrap'}, info, actions, pwForm);
}

function alertOk(text) {
  const ok = el('p', {className: 'ok', role: 'status'}, text);
  errorBox.after(ok);
  setTimeout(() => ok.remove(), 5000);
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

function renderToken(t) {
  const date = new Date(t.created_at * 1000).toLocaleDateString('ru-RU');
  const info = el('span', {className: 'grow'}, el('span', {className: 'name'}, t.name),
                  el('span', {className: 'who'}, `${t.username} · создан ${date}`));
  const del = el('button', {className: 'del', type: 'button', title: 'Отозвать'}, '×');
  del.setAttribute('aria-label', `Отозвать токен ${t.name}`);
  del.addEventListener('click', () => {
    if (!confirm(`Отозвать токен «${t.name}» (${t.username})? Интеграция с ним перестанет работать.`)) return;
    run(async () => {
      await api(`/api/admin/tokens/${t.id}`, {method: 'DELETE'});
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
    const t = await api('/api/admin/tokens', {method: 'POST', body: JSON.stringify({
      user_id: Number(f.namedItem('user_id').value),
      name: f.namedItem('name').value,
    })});
    f.namedItem('name').value = '';
    $('new-token-value').textContent = t.token;
    $('new-token').hidden = false;
    await loadTokens();
  });
});

$('copy-token').addEventListener('click', () => run(async () => {
  await navigator.clipboard.writeText($('new-token-value').textContent);
  $('copy-token').textContent = 'Скопировано';
}));

$('hide-token').addEventListener('click', () => {
  $('new-token-value').textContent = '';
  $('new-token').hidden = true;
  $('copy-token').textContent = 'Скопировать';
});

run(async () => {
  me = await api('/api/me');
  await Promise.all([loadUsers(), loadTokens()]);
});
