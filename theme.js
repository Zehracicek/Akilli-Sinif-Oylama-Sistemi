/**
 * theme.js — Akıllı Sınıf Tema Yöneticisi
 * Koyu / Açık tema seçimi + localStorage kalıcılığı
 * Tüm sayfalarda <script src="theme.js"></script> ile kullanılır
 */
(function () {
  const STORAGE_KEY = 'akillisınıf_tema';

  // Varsayılan: dark
  function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || 'dark';
  }
  function setTheme(t) {
    localStorage.setItem(STORAGE_KEY, t);
    applyTheme(t);
  }
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    // Toggle butonlarını güncelle (sayfada birden fazla olabilir)
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      btn.textContent = t === 'dark' ? '☀️' : '🌙';
      btn.title = t === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç';
      btn.setAttribute('aria-label', btn.title);
    });
  }
  function toggleTheme() {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }

  // Sayfa yüklenince uygula
  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(getTheme());
  });
  // DOMContentLoaded geçmişse hemen uygula
  if (document.readyState !== 'loading') {
    applyTheme(getTheme());
  }

  // Global erişim
  window.ThemeManager = { toggleTheme, getTheme, setTheme, applyTheme };
})();