// Переводы интерфейса (RU/EN). Язык: выбор пользователя (localStorage), иначе язык браузера.
// В HTML: data-i18n="ключ" — текст, data-i18n-ph — placeholder, <html data-title="ключ"> — заголовок вкладки.
const DICT = {
  ru: {
    'app.name': 'Купи',
    'lang.switch': 'EN',
    'lang.switchTitle': 'Switch to English',
    // вход
    'login.title': 'Вход · Купи',
    'login.subtitle': 'Общий список покупок. Войди, чтобы открыть.',
    'login.username': 'Логин',
    'login.password': 'Пароль',
    'login.submit': 'Войти',
    'login.failed': 'Не удалось войти',
    'login.offline': 'Нет связи с сервером',
    // список
    'list.title': 'Купи',
    'nav.admin': 'Админка',
    'nav.password': 'Пароль',
    'nav.logout': 'Выйти',
    'list.placeholder': 'Что купить?',
    'list.add': 'Добавить',
    'list.empty': 'Список пуст',
    'list.bought': 'Куплено',
    'list.clear': 'Очистить купленное',
    'list.delete': 'Удалить',
    'list.deleteAria': 'Удалить «{name}»',
    // смена пароля
    'pw.title': 'Сменить пароль',
    'pw.current': 'Текущий пароль',
    'pw.new': 'Новый пароль, от 8 символов',
    'pw.repeat': 'Новый пароль ещё раз',
    'pw.save': 'Сохранить',
    'pw.cancel': 'Отмена',
    'pw.mismatch': 'Новые пароли не совпадают',
    'pw.done': 'Пароль изменён. На других устройствах нужно войти заново.',
    // админка
    'admin.title': 'Админка · Купи',
    'admin.heading': 'Админка',
    'admin.back': '← К списку',
    'admin.users': 'Пользователи',
    'admin.newUser': 'Новый пользователь',
    'admin.username': 'Логин',
    'admin.password': 'Пароль, от 8 символов',
    'admin.isAdmin': 'администратор',
    'admin.create': 'Создать',
    'admin.badge': 'админ',
    'admin.you': 'это вы',
    'admin.pw': 'Пароль',
    'admin.newPw': 'Новый пароль',
    'admin.save': 'Сохранить',
    'admin.makeAdmin': 'Сделать админом',
    'admin.revokeAdmin': 'Снять админа',
    'admin.delete': 'Удалить',
    'admin.deleteAria': 'Удалить пользователя {name}',
    'admin.confirmDelete': 'Удалить пользователя {name}? Его токены тоже удалятся.',
    'admin.pwChanged': 'Пароль {name} изменён, все его устройства разлогинены',
    'admin.tokens': 'API-токены',
    'admin.tokensHint': 'Для интеграций (например, Claude). Токен работает только со списком покупок, админкой через него управлять нельзя.',
    'admin.tokenOnce': 'Скопируйте токен — второй раз его не показать',
    'admin.copy': 'Скопировать',
    'admin.copied': 'Скопировано',
    'admin.hide': 'Скрыть',
    'admin.newToken': 'Новый токен',
    'admin.tokenName': 'Для чего, например claude',
    'admin.createToken': 'Создать токен',
    'admin.tokenInfo': '{user} · создан {date}',
    'admin.revoke': 'Отозвать',
    'admin.revokeAria': 'Отозвать токен {name}',
    'admin.confirmRevoke': 'Отозвать токен «{name}» ({user})? Интеграция с ним перестанет работать.',
    // ошибки сервера (по коду) и общие
    'err.not_authenticated': 'Нужно войти',
    'err.session_only': 'Только через вход в браузере',
    'err.admin_only': 'Нужны права администратора',
    'err.too_many_attempts': 'Слишком много попыток, подождите 15 минут',
    'err.bad_credentials': 'Неверный логин или пароль',
    'err.wrong_current_password': 'Текущий пароль неверный',
    'err.item_not_found': 'Нет такой покупки',
    'err.empty_name': 'Пустое название',
    'err.user_not_found': 'Нет такого пользователя',
    'err.bad_username': 'Логин: буквы, цифры, точка, дефис или подчёркивание, без пробелов',
    'err.user_exists': 'Пользователь {username} уже есть',
    'err.cannot_demote_self': 'Нельзя снять права администратора с самого себя',
    'err.cannot_delete_self': 'Нельзя удалить самого себя',
    'err.token_not_found': 'Нет такого токена',
    'err.validation': 'Проверьте поля: {msg}',
    'err.server': 'Ошибка сервера',
  },
  en: {
    'app.name': 'Kupi',
    'lang.switch': 'RU',
    'lang.switchTitle': 'Переключить на русский',
    'login.title': 'Log in · Kupi',
    'login.subtitle': 'A shared shopping list. Log in to open it.',
    'login.username': 'Login',
    'login.password': 'Password',
    'login.submit': 'Log in',
    'login.failed': "Couldn't log in",
    'login.offline': 'No connection to the server',
    'list.title': 'Kupi',
    'nav.admin': 'Admin',
    'nav.password': 'Password',
    'nav.logout': 'Log out',
    'list.placeholder': 'What to buy?',
    'list.add': 'Add',
    'list.empty': 'The list is empty',
    'list.bought': 'Bought',
    'list.clear': 'Clear bought',
    'list.delete': 'Delete',
    'list.deleteAria': 'Delete “{name}”',
    'pw.title': 'Change password',
    'pw.current': 'Current password',
    'pw.new': 'New password, at least 8 characters',
    'pw.repeat': 'Repeat the new password',
    'pw.save': 'Save',
    'pw.cancel': 'Cancel',
    'pw.mismatch': "The new passwords don't match",
    'pw.done': 'Password changed. Other devices will need to log in again.',
    'admin.title': 'Admin · Kupi',
    'admin.heading': 'Admin',
    'admin.back': '← Back to the list',
    'admin.users': 'Users',
    'admin.newUser': 'New user',
    'admin.username': 'Login',
    'admin.password': 'Password, at least 8 characters',
    'admin.isAdmin': 'administrator',
    'admin.create': 'Create',
    'admin.badge': 'admin',
    'admin.you': 'you',
    'admin.pw': 'Password',
    'admin.newPw': 'New password',
    'admin.save': 'Save',
    'admin.makeAdmin': 'Make admin',
    'admin.revokeAdmin': 'Revoke admin',
    'admin.delete': 'Delete',
    'admin.deleteAria': 'Delete user {name}',
    'admin.confirmDelete': 'Delete user {name}? Their tokens will be deleted too.',
    'admin.pwChanged': "{name}'s password changed; they were logged out everywhere",
    'admin.tokens': 'API tokens',
    'admin.tokensHint': 'For integrations (e.g. Claude). A token works only with the shopping list; it cannot be used for the admin panel.',
    'admin.tokenOnce': "Copy the token — it won't be shown again",
    'admin.copy': 'Copy',
    'admin.copied': 'Copied',
    'admin.hide': 'Hide',
    'admin.newToken': 'New token',
    'admin.tokenName': 'Purpose, e.g. claude',
    'admin.createToken': 'Create token',
    'admin.tokenInfo': '{user} · created {date}',
    'admin.revoke': 'Revoke',
    'admin.revokeAria': 'Revoke token {name}',
    'admin.confirmRevoke': 'Revoke token “{name}” ({user})? Integrations using it will stop working.',
    'err.not_authenticated': 'Please log in',
    'err.session_only': 'Only available when logged in through the browser',
    'err.admin_only': 'Administrator rights required',
    'err.too_many_attempts': 'Too many attempts, wait 15 minutes',
    'err.bad_credentials': 'Wrong login or password',
    'err.wrong_current_password': 'The current password is wrong',
    'err.item_not_found': 'No such item',
    'err.empty_name': 'The name is empty',
    'err.user_not_found': 'No such user',
    'err.bad_username': 'Login: letters, digits, dot, hyphen or underscore, no spaces',
    'err.user_exists': 'User {username} already exists',
    'err.cannot_demote_self': "You can't revoke your own admin rights",
    'err.cannot_delete_self': "You can't delete yourself",
    'err.token_not_found': 'No such token',
    'err.validation': 'Check the fields: {msg}',
    'err.server': 'Server error',
  },
};

const LANG = (() => {
  try {
    const saved = localStorage.getItem('lang');
    if (saved in DICT) return saved;
  } catch { /* приватный режим и т.п. — берём язык браузера */ }
  return (navigator.language || 'ru').toLowerCase().startsWith('ru') ? 'ru' : 'en';
})();

function t(key, params = {}) {
  const s = DICT[LANG][key] ?? DICT.ru[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (k in params ? String(params[k]) : `{${k}}`));
}

// Текст ошибки из ответа сервера: по коду — перевод, иначе detail как есть.
function errorText(data) {
  if (data && data.code && DICT[LANG][`err.${data.code}`]) return t(`err.${data.code}`, data.params || {});
  if (data && typeof data.detail === 'string') return data.detail;
  if (data && Array.isArray(data.detail) && data.detail[0]?.msg) return t('err.validation', {msg: data.detail[0].msg});
  return t('err.server');
}

function applyI18n(root = document) {
  document.documentElement.lang = LANG;
  const titleKey = document.documentElement.dataset.title;
  if (titleKey) document.title = t(titleKey);
  root.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  const sw = document.getElementById('lang');
  if (sw) {
    sw.textContent = t('lang.switch');
    sw.title = t('lang.switchTitle');
    sw.addEventListener('click', () => {
      try {
        localStorage.setItem('lang', LANG === 'ru' ? 'en' : 'ru');
      } catch {
        return;  // хранилище недоступно (приватный режим) — остаёмся на языке браузера
      }
      location.reload();
    });
  }
}

applyI18n();
