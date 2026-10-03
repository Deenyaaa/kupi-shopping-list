const form = document.getElementById('login');
const error = document.getElementById('error');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const button = form.querySelector('button[type=submit]');
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
    const data = await res.json().catch(() => null);
    error.textContent = data ? errorText(data) : t('login.failed');
  } catch {
    error.textContent = t('login.offline');
  } finally {
    button.disabled = false;
  }
});
