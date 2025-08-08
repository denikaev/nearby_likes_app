const tg = window.Telegram.WebApp;
tg.expand();

let state = {
  userId: null,
  me: null
};

async function api(path, method="GET", body=null, extraHeaders={}) {
  const headers = {"Content-Type":"application/json", ...extraHeaders};
  if (state.userId) headers["X-User-Id"] = String(state.userId);
  const res = await fetch(path, {
    method, headers,
    body: body ? JSON.stringify(body) : null
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || res.statusText);
  }
  return res.json();
}

async function register() {
  const initData = tg.initData || "";
  const me = await api("/api/register", "POST", {init_data: initData});
  state.userId = me.id;
  state.me = me;
  document.getElementById("me").innerHTML = `
    <div class="user-card">
      <div><b>Вы:</b> ${me.first_name ?? ""} ${me.last_name ?? ""} @${me.username ?? ""}</div>
      <div>Лайков получено: <b>${me.likes_received}</b></div>
    </div>`;
}

async function heartbeat() {
  const status = document.getElementById("status");
  status.textContent = "Обновляем геопозицию...";
  if (!navigator.geolocation) {
    status.textContent = "Геолокация не поддерживается";
    return;
  }
  navigator.geolocation.getCurrentPosition(async pos => {
    const {latitude, longitude} = pos.coords;
    await api("/api/heartbeat", "POST", {lat: latitude, lon: longitude});
    status.textContent = `Геопозиция обновлена: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
  }, err => {
    status.textContent = "Не удалось получить геопозицию: " + err.message;
  }, {enableHighAccuracy:true, maximumAge:10000, timeout:10000});
}

async function loadNearby() {
  const status = document.getElementById("status");
  status.textContent = "Ищем кто рядом...";
  if (!navigator.geolocation) {
    status.textContent = "Геолокация не поддерживается";
    return;
  }
  navigator.geolocation.getCurrentPosition(async pos => {
    const {latitude, longitude} = pos.coords;
    const list = await api(`/api/nearby?lat=${latitude}&lon=${longitude}`);
    status.textContent = list.length ? `Найдено рядом: ${list.length}` : "Рядом никого";
    const box = document.getElementById("nearby");
    document.getElementById("leaderboard").style.display = "none";
    box.innerHTML = list.map(u => `
      <div class="user-card">
        <div><b>${u.first_name ?? ""} ${u.last_name ?? ""}</b> @${u.username ?? ""}</div>
        <div>Дистанция: ${u.distance_m} м, Лайков: ${u.likes_received}</div>
        <button onclick="likeUser(${u.id})">Лайкнуть</button>
        <button onclick="openProfile(${u.id})">Профиль</button>
      </div>
    `).join("");
  }, err => {
    status.textContent = "Не удалось получить геопозицию: " + err.message;
  }, {enableHighAccuracy:true, maximumAge:10000, timeout:10000});
}

async function likeUser(targetId) {
  try {
    // используем последнюю геопозицию со стороны сервера (мы всё равно шлём lat/lon в теле для совместимости)
    const res = await api("/api/like", "POST", {target_user_id: targetId, lat: 0, lon: 0});
    alert(res.message);
  } catch (e) {
    alert(e.message);
  }
}

async function openProfile(userId) {
  try {
    const data = await api(`/api/profile/${userId}`);
    alert(
      `Профиль @${data.user.username}\n` +
      `Лайков: ${data.user.likes_received}\n` +
      `Вы лайкали: ${data.you_liked_them ? "да" : "нет"}\n` +
      `Он/она лайкал(а) вас: ${data.they_liked_you ? "да" : "нет"}`
    );
  } catch (e) {
    alert(e.message);
  }
}

async function showLeaderboard() {
  try {
    const lb = await api("/api/leaderboard");
    const box = document.getElementById("leaderboard");
    document.getElementById("nearby").innerHTML = "";
    box.style.display = "block";
    box.innerHTML = lb.map((item, idx) => `
      <div class="lb-item">
        <div><b>#${idx+1}</b> ${item.user.first_name ?? ""} ${item.user.last_name ?? ""} @${item.user.username ?? ""}</div>
        <div>Лайков: <b>${item.likes_received}</b></div>
        <button onclick="openProfile(${item.user.id})">Профиль</button>
      </div>
    `).join("");
  } catch (e) {
    alert(e.message);
  }
}

document.getElementById("shareLoc").addEventListener("click", heartbeat);
document.getElementById("refreshNearby").addEventListener("click", loadNearby);
document.getElementById("showLb").addEventListener("click", showLeaderboard);

(async function boot(){
  try {
    await register();
    await heartbeat();
    await loadNearby();
  } catch (e) {
    alert("Ошибка старта: " + e.message);
  }
})();
