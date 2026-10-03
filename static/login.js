const form = document.getElementById('login');
const error = document.getElementById('error');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const button = form.querySelector('button');
  button.disabled = true;
  error.textContent = '';
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: form.username.value, password: form.password.value}),
    });
    if (res.ok) {
      location.href = '/';
      return;
    }
    const data = await res.json().catch(() => ({}));
    error.textContent = typeof data.detail === 'string' ? data.detail : 'Не удалось войти';
  } catch {
    error.textContent = 'Нет связи с сервером';
  } finally {
    button.disabled = false;
  }
});
