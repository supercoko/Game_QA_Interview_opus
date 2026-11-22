(() => {
  const key = "qa-theme";
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
  const root = document.documentElement;
  const themeColor = document.querySelector('meta[name="theme-color"]');

  function readPreference() {
    try {
      const saved = window.localStorage.getItem(key);
      return saved === "light" || saved === "dark" ? saved : "system";
    } catch {
      return "system";
    }
  }

  let preference = readPreference();
  let picker;

  function applyTheme() {
    const dark = preference === "dark" || (preference === "system" && systemDark.matches);
    root.dataset.theme = dark ? "dark" : "light";
    themeColor.content = dark ? "#101914" : "#f8f7f3";
    if (picker) picker.value = preference;
  }

  applyTheme();
  systemDark.addEventListener("change", applyTheme);
  window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) {
      preference = readPreference();
      applyTheme();
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    picker = document.querySelector("#site-theme");
    picker.value = preference;
    picker.parentElement.hidden = false;
    picker.addEventListener("change", () => {
      preference = picker.value;
      try {
        if (preference === "system") {
          window.localStorage.removeItem(key);
        } else {
          window.localStorage.setItem(key, preference);
        }
      } catch {
        // The current page can still switch themes if storage is blocked.
      }
      applyTheme();
    });
  }, { once: true });
})();
