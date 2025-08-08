// Простые утилиты
const tg = window.Telegram ? window.Telegram.WebApp : null;
const statusEl = () => document.getElementById('status');
const setStatus = (msg) => { statusEl().textContent = msg; };

let USER_ID = null;      // наш внутренний id (из /api/register)
let LAST_COORDS = null;  // { lat, lon }

function api(url, opts={}) {
  return fetch(url, {
    method: opts.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(USER_ID ? {'X-User-Id': String(USER_ID)} : {})
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined
  }).then(async r => {
    if (!r.ok) {
      const t = await r.text().catch(()=>r.statusText);
      throw new Error(t);
    }
    return r.json().catch(()=> ({}));
  });
}

// 1) Регистрация через initData
async function doRegister() {
  try {
    if (!tg) throw new Error('Telegram WebApp SDK не доступен');
    const initData = tg.initData || '';
    if (!initData) throw new Error('Откройте мини-апп из кнопки бота');

    setStatus('Регистрируемся…');
    const data = await api('/api/register', {
      method: 'POST',
      body: { init_data: initData }
    });
    USER_ID = data.id;
    setStatus(`OK, вы: #${USER_ID} (${data.username || data.first_name || 'без имени'})`);
  } catch (e) {
    setStatus('Ошибка регистрации: ' + e.message);
  }
}

// 2) Запрос геолокации и отправка heartbeat
async function doHeartbeat() {
  try {
    if (!USER_ID) throw new Error('Сначала регистрация');
    setStatus('Получаем геолокацию…');

    const coords = await getLocation();
    LAST_COORDS = coords;

    const me = await api('/api/heartbeat', {
      method: 'POST',
      body: { lat: coords.lat, lon: coords.lon }
    });
    setStatus(`Геопозиция обновлена. Лайков: ${me.likes_received}`);
  } catch (e) {
    setStatus('Ошибка геопозиции/heartbeat: ' + e.message);
  }
}

function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Geolocation не поддерживается'));
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      err => reject(new Error('Нет доступа к геолокации: ' + err.message)),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  });
}

// 3) Кто рядом
async function loadNearby() {
  try {
    if (!USER_ID) throw new Error('Сначала регистрация');
    if (!LAST_COORDS) await doHeartbeat();

    setStatus('Ищем кто рядом…');
    const q = new URLSearchParams({ lat: LAST_COORDS.lat, lon: LAST_COORDS.lon }).toString();
    const list = await api('/api/nearby?' + q);

    const box = document.getElementById('nearby');
    box.innerHTML = '';
    if (!list.length) {
      box.innerHTML = '<div class="muted">Пока никого рядом</div>';
      setStatus('Никого в радиусе.');
      return;
    }
    list.forEach(u => {
      const el = document.createElement('div');
      el.className = 'row';
      el.innerHTML = `
        <div class="user">
          <img src="${u.photo_url || ''}" onerror="this.style.display='none'"/>
          <div>
            <div><b>@${u.username || (u.first_name || 'user')}</b></div>
            <div class="muted">${u.distance_m} м · лайков: ${u.likes_received}</div>
          </div>
        </div>
        <div><button class="like" data-id="${u.id}">Лайк</button></div>`;
      box.appendChild(el);
    });

    // навесим обработчики лайка
    box.querySelectorAll('button.like').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.dataset.id);
        try {
          const res = await api('/api/like', { method: 'POST', body: { target_user_id: id } });
          setStatus(res.message || 'Лайк!');
          await loadNearby(); // обновим список
        } catch (e) {
          setStatus('Ошибка лайка: ' + e.message);
        }
      });
    });

    setStatus('Готово.');
  } catch (e) {
    setStatus('Ошибка nearby: ' + e.message);
  }
}

// 4) Лидерборд
async function loadLeaderboard() {
  try {
    const list = await api('/api/leaderboard');
    const box = document.getElementById('leaderboard');
    box.innerHTML = '';
    list.forEach((row, i) => {
      const u = row.user;
      const el = document.createElement('div');
      el.className = 'row';
      el.innerHTML = `
        <div class="rank">#${i+1}</div>
        <div class="user">
          <img src="${u.photo_url || ''}" onerror="this.style.display='none'"/>
          <div><b>@${u.username || (u.first_name || 'user')}</b></div>
        </div>
        <div class="score">${row.likes_received}</div>`;
      box.appendChild(el);
    });
  } catch (e) {
    setStatus('Ошибка лидерборда: ' + e.message);
  }
}

// wire UI
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btnRegister').addEventListener('click', doRegister);
  document.getElementById('btnHeartbeat').addEventListener('click', doHeartbeat);
  document.getElementById('btnNearby').addEventListener('click', loadNearby);
  document.getElementById('btnLeaderboard').addEventListener('click', loadLeaderboard);

  // Авто-инициализация Telegram темы
  if (tg) tg.expand();
  setStatus('Откройте из бота → нажмите "Регистрация".');
});
