(function () {
  const RAIL_ID = "swipeRail";
  const AUTO_HIDE_MS = 4000;
  const EDGE_TRIGGER_PX = 72;
  let hideTimer = null;
  let rail = null;

  function ensureRail() {
    let railEl = document.getElementById(RAIL_ID);
    if (!railEl) {
      railEl = document.createElement("div");
      railEl.id = RAIL_ID;
      railEl.className = "swipe-rail swipe-rail--collapsed";
      railEl.setAttribute("aria-label", "スワイプ・スクロール操作エリア");
      railEl.innerHTML = `
        <span class="swipe-rail__label">SWIPE &amp; SCROLL</span>
        <span class="swipe-rail__divider" aria-hidden="true"></span>
      `;
      document.body.prepend(railEl);
    }
    rail = railEl;
    return railEl;
  }

  function hideRail() {
    if (!rail) return;
    rail.classList.add("swipe-rail--collapsed");
  }

  function showRail({ autoHide = true } = {}) {
    if (!rail) return;
    rail.classList.remove("swipe-rail--collapsed");
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
    if (autoHide) {
      hideTimer = window.setTimeout(() => {
        hideRail();
      }, AUTO_HIDE_MS);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    ensureRail();
    hideRail();
  });

  window.addEventListener("load", () => {
    ensureRail();
    requestAnimationFrame(() => {
      showRail({ autoHide: true });
    });
  });

  document.addEventListener("pointerdown", (event) => {
    if (!rail) return;
    if (rail.contains(event.target)) {
      showRail({ autoHide: true });
      return;
    }
    const distanceFromEdge = window.innerWidth - event.clientX;
    if (distanceFromEdge <= EDGE_TRIGGER_PX) {
      showRail({ autoHide: true });
    }
  });

  let lastTouchEnd = 0;
  const interactiveSelector =
    "a, button, input, textarea, select, label, summary, [role='button'], [role='link']";
  document.addEventListener(
    "touchend",
    (event) => {
      if (event.target && event.target.closest?.(interactiveSelector)) {
        lastTouchEnd = Date.now();
        return;
      }
      const now = Date.now();
      if (now - lastTouchEnd <= 300) {
        event.preventDefault();
      }
      lastTouchEnd = now;
    },
    { passive: false }
  );
})();
