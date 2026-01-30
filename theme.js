(function () {
  const STORAGE_KEY = "encho_theme_preset_v1";

  const THEMES = {
    violet: {
      label: "バイオレット × オレンジ",
      accent: "#8b5cf6",
      accent2: "#f59e0b",
      accent3: "#22d3ee",
      accent4: "#fb7185",
      muted: "#2f2a40",
      panel: "#ffffff",
      panelSub: "#fdf7ff",
      border: "#e7dff2",
      text: "#1f1b2d",
      subtext: "#6b6477",
      bg: "radial-gradient(circle at 18% 20%, rgba(255,221,235,.8), transparent 40%), radial-gradient(circle at 80% 8%, rgba(189,227,255,.7), transparent 34%), linear-gradient(180deg,#fff8fd,#f5f7ff)",
      panelOverlay: "rgba(255,255,255,.92)",
      weekdayBg: "rgba(139,92,246,.12)",
      weekendBg: "rgba(245,158,11,.12)",
      glow: "0 12px 45px rgba(139, 92, 246, 0.26)"
    },
    sunrise: {
      label: "サンライズ × コーラル",
      accent: "#f97316",
      accent2: "#ec4899",
      accent3: "#fde68a",
      accent4: "#fb7185",
      muted: "#2e1f1a",
      panel: "#fffaf5",
      panelSub: "#fff3eb",
      border: "#ffd9c2",
      text: "#2b1c15",
      subtext: "#7a5a4a",
      bg: "radial-gradient(circle at 15% 20%, rgba(255, 213, 186, 0.75), transparent 38%), radial-gradient(circle at 80% 10%, rgba(248, 180, 204, 0.65), transparent 36%), linear-gradient(180deg, #fff7f0, #ffe8de)",
      panelOverlay: "rgba(255, 247, 240, .9)",
      weekdayBg: "rgba(249,115,22,.14)",
      weekendBg: "rgba(236,72,153,.14)",
      glow: "0 12px 45px rgba(249, 115, 22, 0.24)"
    },
    forest: {
      label: "フォレスト × アクア",
      accent: "#22c55e",
      accent2: "#0ea5e9",
      accent3: "#a7f3d0",
      accent4: "#86efac",
      muted: "#0f2f26",
      panel: "#f6fffa",
      panelSub: "#edfdf4",
      border: "#c5f0db",
      text: "#0f1f1a",
      subtext: "#3f5f56",
      bg: "radial-gradient(circle at 14% 18%, rgba(195, 245, 214, 0.62), transparent 36%), radial-gradient(circle at 78% 12%, rgba(163, 222, 251, 0.56), transparent 34%), linear-gradient(180deg, #f6fffa, #ecfdf3)",
      panelOverlay: "rgba(246, 255, 250, .9)",
      weekdayBg: "rgba(34,197,94,.14)",
      weekendBg: "rgba(14,165,233,.14)",
      glow: "0 12px 45px rgba(34, 197, 94, 0.24)"
    },
    sakura: {
      label: "さくら × レモン",
      accent: "#f472b6",
      accent2: "#facc15",
      accent3: "#fcd34d",
      accent4: "#fb7185",
      muted: "#361624",
      panel: "#fff7fb",
      panelSub: "#fff0f7",
      border: "#ffd5e7",
      text: "#2b0f1e",
      subtext: "#6b3f59",
      bg: "radial-gradient(circle at 15% 18%, rgba(252, 231, 243, 0.7), transparent 36%), radial-gradient(circle at 70% 12%, rgba(250, 232, 150, 0.62), transparent 34%), linear-gradient(180deg, #fff7fb, #fff0f5)",
      panelOverlay: "rgba(255, 247, 251, .9)",
      weekdayBg: "rgba(244,114,182,.16)",
      weekendBg: "rgba(250,204,21,.14)",
      glow: "0 12px 45px rgba(244, 114, 182, 0.24)"
    },
    mint: {
      label: "ミントクリーム × ソーダ",
      accent: "#34d399",
      accent2: "#67e8f9",
      accent3: "#a5f3fc",
      accent4: "#86efac",
      muted: "#13322a",
      panel: "#f4fffb",
      panelSub: "#ecfdf6",
      border: "#ccf4e5",
      text: "#0f221c",
      subtext: "#3c6f63",
      bg: "radial-gradient(circle at 12% 18%, rgba(198, 246, 231, 0.65), transparent 32%), radial-gradient(circle at 75% 10%, rgba(186, 245, 255, 0.58), transparent 36%), linear-gradient(180deg, #f4fffb, #e6fff6)",
      panelOverlay: "rgba(244, 255, 251, .9)",
      weekdayBg: "rgba(52,211,153,.16)",
      weekendBg: "rgba(103,232,249,.16)",
      glow: "0 12px 45px rgba(103, 232, 249, 0.26)"
    },
    candy: {
      label: "キャンディ × ユニコーン",
      accent: "#a78bfa",
      accent2: "#fb7185",
      accent3: "#f9a8d4",
      accent4: "#7dd3fc",
      muted: "#2e1c35",
      panel: "#fef7ff",
      panelSub: "#fdf2ff",
      border: "#ead5ff",
      text: "#25152b",
      subtext: "#65406e",
      bg: "radial-gradient(circle at 12% 20%, rgba(227, 204, 255, 0.7), transparent 34%), radial-gradient(circle at 78% 12%, rgba(252, 213, 236, 0.62), transparent 34%), linear-gradient(180deg, #fef7ff, #fdf2ff)",
      panelOverlay: "rgba(254, 247, 255, .9)",
      weekdayBg: "rgba(167,139,250,.16)",
      weekendBg: "rgba(251,113,133,.16)",
      glow: "0 12px 45px rgba(251, 113, 133, 0.26)"
    },
    midnight: {
      label: "ミッドナイト × ネオン",
      accent: "#60a5fa",
      accent2: "#c084fc",
      accent3: "#22d3ee",
      accent4: "#f472b6",
      muted: "#94a3b8",
      panel: "#0f172a",
      panelSub: "#111827",
      border: "#1f2937",
      text: "#e2e8f0",
      subtext: "#cbd5e1",
      bg: "radial-gradient(circle at 16% 18%, rgba(59, 130, 246, 0.25), transparent 34%), radial-gradient(circle at 78% 12%, rgba(236, 72, 153, 0.22), transparent 32%), linear-gradient(180deg, #0b1021, #0f172a)",
      panelOverlay: "rgba(15, 23, 42, .92)",
      weekdayBg: "rgba(96,165,250,.14)",
      weekendBg: "rgba(192,132,252,.14)",
      glow: "0 12px 45px rgba(96, 165, 250, 0.24)"
    },
    dusk: {
      label: "ダスク × コーラル",
      accent: "#fb7185",
      accent2: "#f97316",
      accent3: "#fbbf24",
      accent4: "#38bdf8",
      muted: "#f5e7e0",
      panel: "#211722",
      panelSub: "#1b1320",
      border: "#37263a",
      text: "#fdf2f8",
      subtext: "#f3cfdc",
      bg: "radial-gradient(circle at 18% 20%, rgba(251, 113, 133, 0.18), transparent 32%), radial-gradient(circle at 72% 10%, rgba(56, 189, 248, 0.18), transparent 34%), linear-gradient(180deg, #0f0a14, #1b0f1f)",
      panelOverlay: "rgba(27, 19, 31, .9)",
      weekdayBg: "rgba(251,113,133,.12)",
      weekendBg: "rgba(56,189,248,.12)",
      glow: "0 12px 45px rgba(251, 113, 133, 0.22)"
    }
  };

  function saveActiveThemeName(name) {
    const themeKey = THEMES[name] ? name : "violet";
    localStorage.setItem(STORAGE_KEY, themeKey);
  }

  function getActiveThemeName() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored && THEMES[stored] ? stored : "violet";
  }

  function applyTheme(name, doc = document) {
    const theme = THEMES[name] || THEMES.violet;
    const root = doc.documentElement;
    const map = {
      accent: "--accent",
      accent2: "--accent-2",
      accent3: "--accent-3",
      accent4: "--accent-4",
      muted: "--muted",
      panel: "--panel",
      panelSub: "--panel-sub",
      border: "--border",
      text: "--text",
      subtext: "--subtext",
      bg: "--bg",
      panelOverlay: "--panel-overlay",
      weekdayBg: "--weekday-bg",
      weekendBg: "--weekend-bg",
      glow: "--glow"
    };

    Object.entries(map).forEach(([key, cssVar]) => {
      root.style.setProperty(cssVar, theme[key]);
    });
  }

  function applyCurrentTheme(doc = document) {
    applyTheme(getActiveThemeName(), doc);
  }

  window.EnchoTheme = {
    THEMES,
    getActiveThemeName,
    saveActiveThemeName,
    applyTheme,
    applyCurrentTheme
  };
})();
