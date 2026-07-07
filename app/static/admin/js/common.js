(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("lc_admin_theme");
  if (saved === "dark") root.setAttribute("data-theme", "dark");

  const toggle = document.getElementById("darkModeToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const isDark = root.getAttribute("data-theme") === "dark";
      if (isDark) {
        root.removeAttribute("data-theme");
        localStorage.setItem("lc_admin_theme", "light");
      } else {
        root.setAttribute("data-theme", "dark");
        localStorage.setItem("lc_admin_theme", "dark");
      }
    });
  }

  if ("Notification" in window && Notification.permission === "default") {
    document.addEventListener("click", function requestOnce() {
      Notification.requestPermission();
      document.removeEventListener("click", requestOnce);
    }, { once: true });
  }

  window.LC_playNotifySound = function () {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      osc.start();
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) { /* audio not available */ }
  };

  window.LC_desktopNotify = function (title, body) {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, { body });
    }
  };
})();
