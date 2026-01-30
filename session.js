const ENCHO_USER_KEY = "encho_user_profiles_v1";
const ENCHO_ADMIN_KEY = "encho_admin_session_v1";
const ENCHO_SITE_CONFIG_KEY = "encho_site_config_v1";
const ENCHO_ADMIN_SETTINGS_KEY = "encho_admin_settings_v1";
const ENCHO_WINDOW_REGISTRY_KEY = "encho_window_registry_v1";
const ENCHO_WINDOW_ID_KEY = "encho_window_id_v1";
const DEFAULT_HOMEPAGE_SUBTITLE = "💖 1号認定の方向けに、預かり保育と延長保育の料金を簡単に計算できるポータルです";

const DEFAULT_FEATURES = [
  {
    id: "calcu",
    title: "Encho｜エンチョー",
    description: "延長・預かり保育の料金計算と日次明細の確認をまとめたメインカード",
    href: "Calcu.html",
    icon: "🌟",
    cta: "Enchoを開く →",
    featureList: [
      "EnChoからの明細配信",
      "ボタンリプライで確認依頼",
      "QR認証で保護者を紐付け",
      "日次明細の詳細確認"
    ]
  },
  {
    id: "line-diary",
    title: "カード配信",
    description: "写真＋地図＋メモをまとめた配信用カードを作成し、共有用JSONも生成",
    href: "line-diary-card.html",
    icon: "🗺️",
    cta: "カード配信を作る →",
    featureList: [
      "現在地 / EXIF / 手入力の3パターンで座標セット",
      "静的地図のプレビューと共有リンクを自動生成",
      "LINE Flex Message JSON・共有テキストをワンクリックコピー",
      "テーマ同期で既存ツールと同じ配色を保持"
    ]
  },
  {
    id: "flex-builder",
    title: "通知カードレイアウト作成",
    description: "先生向けの通知カードテンプレートを作成・保存・JSON出力",
    href: "flex-builder.html",
    icon: "🧩",
    cta: "通知カードレイアウトを開く →",
    featureList: [
      "パーツ追加でHeader/Body/Footerを組み立て",
      "プレビューとJSON生成を同時に確認",
      "テンプレ保存・複製・削除に対応",
      "明細/確認/返金の初期テンプレを用意"
    ]
  }
];

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function getDefaultFeatures() {
  return deepClone(DEFAULT_FEATURES);
}

function loadUserState() {
  try {
    const raw = localStorage.getItem(ENCHO_USER_KEY);
    if (!raw) return { activeUser: null, profiles: {} };
    const parsed = JSON.parse(raw);
    return {
      activeUser: parsed.activeUser || null,
      profiles: parsed.profiles || {}
    };
  } catch (e) {
    console.error("ログイン状態の読み込みに失敗しました", e);
    return { activeUser: null, profiles: {} };
  }
}

function saveUserState(nextState) {
  try {
    localStorage.setItem(ENCHO_USER_KEY, JSON.stringify(nextState));
    return true;
  } catch (e) {
    console.error("ログイン状態の保存に失敗しました", e);
    return false;
  }
}

function setActiveUser(username) {
  const state = loadUserState();
  state.activeUser = username;
  if (!state.profiles[username]) state.profiles[username] = {};
  return saveUserState(state);
}

function getActiveUser() {
  const state = loadUserState();
  return state.activeUser || null;
}

function getLastPage(username) {
  const state = loadUserState();
  const profile = state.profiles?.[username];
  return profile?.lastPage || null;
}

function updateLastPageForActive(pagePath) {
  const state = loadUserState();
  const user = state.activeUser;
  if (!user) return false;
  if (!state.profiles[user]) state.profiles[user] = {};
  state.profiles[user].lastPage = pagePath;
  return saveUserState(state);
}

function clearActiveUser() {
  const state = loadUserState();
  state.activeUser = null;
  return saveUserState(state);
}

function normalizeVisibility(rawVisibility) {
  if (!rawVisibility || typeof rawVisibility !== "object" || Array.isArray(rawVisibility)) {
    return {};
  }
  return { ...rawVisibility };
}

function loadSiteConfig() {
  try {
    const raw = localStorage.getItem(ENCHO_SITE_CONFIG_KEY);
    if (!raw) {
      return { homepageSubtitle: DEFAULT_HOMEPAGE_SUBTITLE, featureVisibility: {} };
    }
    const parsed = JSON.parse(raw);
    return {
      homepageSubtitle: parsed.homepageSubtitle || DEFAULT_HOMEPAGE_SUBTITLE,
      featureVisibility: normalizeVisibility(parsed.featureVisibility)
    };
  } catch (e) {
    console.error("サイト設定の読み込みに失敗しました", e);
    return { homepageSubtitle: DEFAULT_HOMEPAGE_SUBTITLE, featureVisibility: {} };
  }
}

function saveSiteConfig(nextConfig) {
  try {
    const payload = {
      homepageSubtitle: nextConfig?.homepageSubtitle || DEFAULT_HOMEPAGE_SUBTITLE,
      featureVisibility: normalizeVisibility(nextConfig?.featureVisibility)
    };
    localStorage.setItem(ENCHO_SITE_CONFIG_KEY, JSON.stringify(payload));
    return true;
  } catch (e) {
    console.error("サイト設定の保存に失敗しました", e);
    return false;
  }
}

function setHomepageSubtitle(text) {
  const next = (text || "").trim() || DEFAULT_HOMEPAGE_SUBTITLE;
  const config = loadSiteConfig();
  config.homepageSubtitle = next;
  return saveSiteConfig(config);
}

function getHomepageSubtitle() {
  const config = loadSiteConfig();
  return config.homepageSubtitle || DEFAULT_HOMEPAGE_SUBTITLE;
}

function getFeatures() {
  const config = loadSiteConfig();
  const visibility = normalizeVisibility(config.featureVisibility);
  return getDefaultFeatures().map((feature) => {
    const hasValue = Object.prototype.hasOwnProperty.call(visibility, feature.id);
    const enabled = hasValue ? !!visibility[feature.id] : true;
    return { ...feature, enabled };
  });
}

function setFeatureVisibility(featureId, isEnabled) {
  if (!featureId) return false;
  const config = loadSiteConfig();
  const visibility = normalizeVisibility(config.featureVisibility);
  visibility[featureId] = !!isEnabled;
  config.featureVisibility = visibility;
  return saveSiteConfig(config);
}

function setFeatureVisibilityBulk(settings = []) {
  const config = loadSiteConfig();
  const visibility = normalizeVisibility(config.featureVisibility);
  let updated = false;
  settings.forEach((item) => {
    if (item?.id) {
      visibility[item.id] = !!item.enabled;
      updated = true;
    }
  });
  if (!updated) return true;
  config.featureVisibility = visibility;
  return saveSiteConfig(config);
}

function loadAdminSettings() {
  try {
    const raw = localStorage.getItem(ENCHO_ADMIN_SETTINGS_KEY);
    if (!raw) {
      return { lockMode: false, localNetworks: [] };
    }
    const parsed = JSON.parse(raw);
    return {
      lockMode: !!parsed.lockMode,
      localNetworks: Array.isArray(parsed.localNetworks) ? parsed.localNetworks : []
    };
  } catch (e) {
    console.error("管理設定の読み込みに失敗しました", e);
    return { lockMode: false, localNetworks: [] };
  }
}

function saveAdminSettings(nextSettings) {
  try {
    const payload = {
      lockMode: !!nextSettings?.lockMode,
      localNetworks: Array.isArray(nextSettings?.localNetworks) ? nextSettings.localNetworks : []
    };
    localStorage.setItem(ENCHO_ADMIN_SETTINGS_KEY, JSON.stringify(payload));
    return true;
  } catch (e) {
    console.error("管理設定の保存に失敗しました", e);
    return false;
  }
}

function setLockMode(isEnabled) {
  const settings = loadAdminSettings();
  settings.lockMode = !!isEnabled;
  return saveAdminSettings(settings);
}

function getLockMode() {
  return loadAdminSettings().lockMode;
}

function getLocalNetworks() {
  return loadAdminSettings().localNetworks || [];
}

function setLocalNetworks(entries = []) {
  const settings = loadAdminSettings();
  settings.localNetworks = Array.isArray(entries) ? entries : [];
  return saveAdminSettings(settings);
}

function loadAdminSession() {
  try {
    const raw = localStorage.getItem(ENCHO_ADMIN_KEY);
    if (!raw) return { adminUser: null, signedInAt: null };
    const parsed = JSON.parse(raw);
    return {
      adminUser: parsed.adminUser || null,
      signedInAt: parsed.signedInAt || null
    };
  } catch (e) {
    console.error("管理ログイン状態の読み込みに失敗しました", e);
    return { adminUser: null, signedInAt: null };
  }
}

function saveAdminSession(nextSession) {
  try {
    localStorage.setItem(ENCHO_ADMIN_KEY, JSON.stringify(nextSession));
    return true;
  } catch (e) {
    console.error("管理ログイン状態の保存に失敗しました", e);
    return false;
  }
}

function setActiveAdmin(username) {
  return saveAdminSession({ adminUser: username, signedInAt: Date.now() });
}

function clearActiveAdmin() {
  return saveAdminSession({ adminUser: null, signedInAt: null });
}

function getActiveAdmin() {
  const session = loadAdminSession();
  return session.adminUser || null;
}

function getAdminSignedInAt() {
  const session = loadAdminSession();
  return session.signedInAt || null;
}

function storeLastPageIfSignedIn() {
  const filename = (location.pathname.split("/").pop() || "index.html") || "index.html";
  return updateLastPageForActive(filename);
}

function loadWindowRegistry() {
  try {
    const raw = localStorage.getItem(ENCHO_WINDOW_REGISTRY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.error("ウィンドウ状態の読み込みに失敗しました", e);
    return [];
  }
}

function saveWindowRegistry(entries) {
  try {
    localStorage.setItem(ENCHO_WINDOW_REGISTRY_KEY, JSON.stringify(entries));
    return true;
  } catch (e) {
    console.error("ウィンドウ状態の保存に失敗しました", e);
    return false;
  }
}

function getWindowId() {
  try {
    const cached = sessionStorage.getItem(ENCHO_WINDOW_ID_KEY);
    if (cached) return cached;
    const nextId = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `window-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    sessionStorage.setItem(ENCHO_WINDOW_ID_KEY, nextId);
    return nextId;
  } catch (e) {
    return `window-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}

function buildWindowEntry(windowId) {
  return {
    id: windowId,
    title: document.title || "無題",
    path: location.pathname || "",
    openedAt: Date.now(),
    lastSeen: Date.now()
  };
}

function upsertWindowEntry(entries, windowId) {
  const next = entries.filter((entry) => entry && entry.id !== windowId);
  const existing = entries.find((entry) => entry && entry.id === windowId);
  const base = existing || buildWindowEntry(windowId);
  next.push({
    ...base,
    title: document.title || base.title || "無題",
    path: location.pathname || base.path || "",
    lastSeen: Date.now()
  });
  return next;
}

function pruneWindowEntries(entries, maxAgeMs = 15000) {
  const now = Date.now();
  return entries.filter((entry) => entry && typeof entry.lastSeen === "number" && now - entry.lastSeen <= maxAgeMs);
}

function ensureMultiWindowStyles() {
  if (document.getElementById("multiWindowStyles")) return;
  const style = document.createElement("style");
  style.id = "multiWindowStyles";
  style.textContent = `
    .multi-window-modal { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; background: rgba(10, 12, 18, 0.6); z-index: 9999; }
    .multi-window-modal.is-open { display: flex; }
    .multi-window-panel { width: min(720px, 92vw); background: #fff; border-radius: 16px; box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25); padding: 20px 24px; color: #1b1b1b; }
    .multi-window-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .multi-window-title { margin: 0; font-size: 18px; font-weight: 700; }
    .multi-window-desc { margin: 8px 0 16px; font-size: 14px; color: #4b5563; line-height: 1.6; }
    .multi-window-list { display: grid; gap: 10px; padding: 0; margin: 0 0 16px; list-style: none; max-height: 240px; overflow: auto; }
    .multi-window-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px; border-radius: 12px; border: 1px solid #e5e7eb; background: #f9fafb; }
    .multi-window-item input { margin-top: 2px; }
    .multi-window-item strong { display: block; font-size: 14px; }
    .multi-window-item span { display: block; font-size: 12px; color: #6b7280; }
    .multi-window-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
    .multi-window-actions button { border: none; border-radius: 999px; padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer; }
    .multi-window-actions .primary { background: #ef4444; color: #fff; }
    .multi-window-actions .secondary { background: #f3f4f6; color: #111827; }
  `;
  document.head.appendChild(style);
}

function ensureMultiWindowModal() {
  let modal = document.getElementById("multiWindowModal");
  if (modal) return modal;
  ensureMultiWindowStyles();
  modal = document.createElement("div");
  modal.className = "multi-window-modal";
  modal.id = "multiWindowModal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-hidden", "true");
  modal.innerHTML = `
    <div class="multi-window-panel">
      <div class="multi-window-header">
        <h2 class="multi-window-title" id="multiWindowTitle">複数ウィンドウ検知警告</h2>
      </div>
      <p class="multi-window-desc">以下のウィンドウがすでに開いています。残すウィンドウを選択してください。</p>
      <ul class="multi-window-list" id="multiWindowList"></ul>
      <div class="multi-window-actions">
        <button type="button" class="secondary" id="multiWindowSaveClose">保存して閉じる</button>
        <button type="button" class="primary" id="multiWindowClose">閉じる</button>
      </div>
    </div>
  `;
  modal.addEventListener("click", (event) => {
    if (event.target === modal) event.stopPropagation();
  });
  document.body.appendChild(modal);
  return modal;
}

function renderMultiWindowList(entries, currentId) {
  const list = document.getElementById("multiWindowList");
  if (!list) return;
  list.innerHTML = "";
  entries
    .sort((a, b) => (a.openedAt || 0) - (b.openedAt || 0))
    .forEach((entry) => {
      const item = document.createElement("li");
      item.className = "multi-window-item";
      const id = `multi-window-choice-${entry.id}`;
      const isCurrent = entry.id === currentId;
      item.innerHTML = `
        <input type="radio" name="multiWindowChoice" id="${id}" value="${entry.id}" ${isCurrent ? "checked" : ""}>
        <label for="${id}">
          <strong>${entry.title || "無題"}${isCurrent ? "（このウィンドウ）" : ""}</strong>
          <span>${entry.path || ""}</span>
        </label>
      `;
      list.appendChild(item);
    });
}

function openMultiWindowModal(entries, currentId) {
  const modal = ensureMultiWindowModal();
  renderMultiWindowList(entries, currentId);
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
}

function closeMultiWindowModal() {
  const modal = document.getElementById("multiWindowModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
}

function getSelectedWindowId(currentId) {
  const selected = document.querySelector("input[name=multiWindowChoice]:checked");
  return selected?.value || currentId;
}

function dispatchCloseRequest(channel, payload) {
  if (channel) {
    channel.postMessage(payload);
  }
  try {
    localStorage.setItem("encho_multi_window_signal", JSON.stringify({ ...payload, ts: Date.now() }));
  } catch (e) {
    console.warn("ウィンドウ通知に失敗しました", e);
  }
}

function attachMultiWindowActions(channel, currentId) {
  const closeBtn = document.getElementById("multiWindowClose");
  const saveBtn = document.getElementById("multiWindowSaveClose");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      const keepId = getSelectedWindowId(currentId);
      dispatchCloseRequest(channel, { type: "encho-multiwindow-close", keepId, shouldSave: false });
    });
  }
  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      const keepId = getSelectedWindowId(currentId);
      dispatchCloseRequest(channel, { type: "encho-multiwindow-close", keepId, shouldSave: true });
    });
  }
}

function handleCloseRequest({ keepId, shouldSave }, currentId) {
  if (!keepId || keepId === currentId) return;
  if (shouldSave) {
    window.dispatchEvent(new CustomEvent("encho:multiwindow-save"));
  }
  setTimeout(() => {
    window.close();
  }, 150);
}

function initMultiWindowWarning() {
  const currentId = getWindowId();
  const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("encho-multiwindow") : null;
  const updateRegistry = () => {
    const entries = pruneWindowEntries(upsertWindowEntry(loadWindowRegistry(), currentId));
    saveWindowRegistry(entries);
    return entries;
  };
  const evaluateState = (entries) => {
    const visibleEntries = entries.filter((entry) => entry && entry.id);
    if (visibleEntries.length > 1) {
      openMultiWindowModal(visibleEntries, currentId);
    } else {
      closeMultiWindowModal();
    }
  };
  const entries = updateRegistry();
  ensureMultiWindowModal();
  attachMultiWindowActions(channel, currentId);
  evaluateState(entries);

  const heartbeat = () => {
    const nextEntries = updateRegistry();
    evaluateState(nextEntries);
  };

  const heartbeatTimer = setInterval(heartbeat, 5000);

  window.addEventListener("beforeunload", () => {
    clearInterval(heartbeatTimer);
    const nextEntries = loadWindowRegistry().filter((entry) => entry && entry.id !== currentId);
    saveWindowRegistry(nextEntries);
  });

  window.addEventListener("storage", (event) => {
    if (event.key === ENCHO_WINDOW_REGISTRY_KEY) {
      evaluateState(pruneWindowEntries(loadWindowRegistry()));
    }
    if (event.key === "encho_multi_window_signal" && event.newValue) {
      try {
        const payload = JSON.parse(event.newValue);
        if (payload?.type === "encho-multiwindow-close") {
          handleCloseRequest(payload, currentId);
        }
      } catch (e) {
        console.warn("ウィンドウ通知の解析に失敗しました", e);
      }
    }
  });

  if (channel) {
    channel.addEventListener("message", (event) => {
      if (event.data?.type === "encho-multiwindow-close") {
        handleCloseRequest(event.data, currentId);
      }
    });
  }
}

window.EnchoSession = {
  loadUserState,
  saveUserState,
  setActiveUser,
  getActiveUser,
  getLastPage,
  updateLastPageForActive,
  storeLastPageIfSignedIn,
  clearActiveUser,
  loadAdminSession,
  setActiveAdmin,
  clearActiveAdmin,
  getActiveAdmin,
  getAdminSignedInAt,
  loadSiteConfig,
  saveSiteConfig,
  setHomepageSubtitle,
  getHomepageSubtitle,
  getDefaultFeatures,
  getFeatures,
  setFeatureVisibility,
  setFeatureVisibilityBulk,
  loadAdminSettings,
  saveAdminSettings,
  setLockMode,
  getLockMode,
  getLocalNetworks,
  setLocalNetworks,
  DEFAULT_HOMEPAGE_SUBTITLE,
  initMultiWindowWarning
};

if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", initMultiWindowWarning, { once: true });
} else {
  initMultiWindowWarning();
}
