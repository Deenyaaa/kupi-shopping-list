const $ = (id) => document.getElementById(id);
const errorBox = $('error');

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
  if (!res.ok) throw new Error(errorText(data));  // errorText и t — из i18n.js
  return data;
}

function showError(e) {
  errorBox.textContent = e ? e.message || String(e) : '';
}

function renderItem(item) {
  const li = document.createElement('li');
  li.className = item.bought ? 'bought' : '';

  const label = document.createElement('label');
  const box = document.createElement('input');
  box.type = 'checkbox';
  box.checked = item.bought;
  box.addEventListener('change', () => mutate(`/api/items/${item.id}`, {
    method: 'PATCH', body: JSON.stringify({bought: box.checked}),
  }));

  // Только textContent: названия покупок вводят пользователи, в HTML их не вставляем.
  const text = document.createElement('span');
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = item.name;
  text.append(name);
  if (item.added_by) {
    const who = document.createElement('span');
    who.className = 'who';
    who.textContent = item.added_by;
    text.append(who);
  }
  label.append(box, text);

  const del = document.createElement('button');
  del.className = 'del';
  del.textContent = '×';
  del.title = t('list.delete');
  del.setAttribute('aria-label', t('list.deleteAria', {name: item.name}));
  del.addEventListener('click', () => mutate(`/api/items/${item.id}`, {method: 'DELETE'}));

  li.append(label, del);
  return li;
}

function render(items) {
  const todo = items.filter((i) => !i.bought);
  const bought = items.filter((i) => i.bought);
  $('todo').replaceChildren(...todo.map(renderItem));
  $('bought').replaceChildren(...bought.map(renderItem));
  $('empty').hidden = todo.length > 0;
  $('bought-head').hidden = bought.length === 0;
}

async function refresh() {
  try {
    render(await api('/api/items'));
    showError(null);
  } catch (e) {
    showError(e);
  }
}

async function mutate(path, options) {
  try {
    await api(path, options);
  } catch (e) {
    showError(e);
  }
  await refresh();
}

$('add').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = e.target.elements.namedItem('product');
  const name = input.value.trim();
  if (!name) return;
  input.value = '';
  await mutate('/api/items', {method: 'POST', body: JSON.stringify({name})});
  input.focus();
});

$('clear').addEventListener('click', () => mutate('/api/items/clear-bought', {method: 'POST'}));

$('logout').addEventListener('click', async () => {
  await fetch('/api/logout', {method: 'POST'});
  location.href = '/login';
});

// --- смена своего пароля ---
const pwForm = $('pw');
const pwMsg = $('pw-msg');

function togglePw(show) {
  pwForm.hidden = !show;
  pwForm.reset();
  pwMsg.textContent = '';
  if (show) pwForm.elements.namedItem('current').focus();
}

$('pw-toggle').addEventListener('click', () => togglePw(pwForm.hidden));
$('pw-cancel').addEventListener('click', () => togglePw(false));

pwForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = pwForm.elements;
  if (f.namedItem('new').value !== f.namedItem('repeat').value) {
    pwMsg.textContent = t('pw.mismatch');
    return;
  }
  try {
    await api('/api/password', {
      method: 'POST',
      body: JSON.stringify({current: f.namedItem('current').value, new: f.namedItem('new').value}),
    });
    pwForm.reset();
    pwMsg.textContent = t('pw.done');
  } catch (err) {
    pwMsg.textContent = err.message;
  }
});

api('/api/me').then((me) => {
  $('me').textContent = me.username;
  $('admin-link').hidden = !me.is_admin;
}).catch(() => {});
refresh();

// Подтягиваем изменения других пользователей, пока вкладка на экране.
setInterval(() => { if (!document.hidden) refresh(); }, 10000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
