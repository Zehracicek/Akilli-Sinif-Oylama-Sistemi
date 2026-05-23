/**
 * theme.js — Tema yöneticisi + Kahoot tarzı açık/koyu atmosfer
 */
(function () {
  const STORAGE_KEY = 'akillisınıf_tema';

  const KAHOOT_DISCS = [
    { color: '#e21b3c', size: 240, x: -4, y: 6, rot: -14, delay: 0 },
    { color: '#1368ce', size: 200, x: 86, y: 2, rot: 10, delay: -2 },
    { color: '#d89e00', size: 170, x: 90, y: 58, rot: -18, delay: -4 },
    { color: '#26890c', size: 210, x: -6, y: 62, rot: 16, delay: -1 },
    { color: '#7c3aed', size: 150, x: 72, y: 82, rot: -8, delay: -3 },
    { color: '#ec4899', size: 130, x: 6, y: 32, rot: 22, delay: -5 },
    { color: '#1368ce', size: 110, x: 42, y: -2, rot: -12, delay: -6, op: 0.62 },
    { color: '#e21b3c', size: 95, x: 58, y: 44, rot: 8, delay: -7, op: 0.58 },
    { color: '#d89e00', size: 85, x: 24, y: 88, rot: -25, delay: -8, op: 0.55 },
    { color: '#26890c', size: 75, x: 88, y: 38, rot: 15, delay: -9, op: 0.52 }
  ];

  const KAHOOT_TRIS = [
    { color: '#e21b3c', size: 90, x: 78, y: 22, rot: 15, delay: 0 },
    { color: '#1368ce', size: 70, x: 12, y: 18, rot: -20, delay: -3 },
    { color: '#d89e00', size: 60, x: 92, y: 82, rot: 8, delay: -5 },
    { color: '#7c3aed', size: 55, x: 2, y: 48, rot: -12, delay: -2 },
    { color: '#26890c', size: 50, x: 48, y: 90, rot: 25, delay: -4 }
  ];

  const EMOJI_LAYOUT = [
    { emoji: '🎓', tier: 'hero', x: -2, y: -2 },
    { emoji: '🎯', tier: 'hero', x: 78, y: -4 },
    { emoji: '🏆', tier: 'hero', x: 80, y: 68 },
    { emoji: '📚', tier: 'hero', x: -4, y: 72 },
    { emoji: '🎉', tier: 'mega', x: 10, y: 34 },
    { emoji: '💡', tier: 'mega', x: 76, y: 38 },
    { emoji: '🌈', tier: 'mega', x: 4, y: 54 },
    { emoji: '⚡', tier: 'mega', x: 90, y: 24 },
    { emoji: '🔥', tier: 'mega', x: 68, y: 86 },
    { emoji: '✨', tier: 'lg', x: 20, y: 10 },
    { emoji: '⭐', tier: 'lg', x: 66, y: 14 },
    { emoji: '📝', tier: 'lg', x: 36, y: 6 },
    { emoji: '🎮', tier: 'lg', x: 50, y: 80 },
    { emoji: '👨‍🏫', tier: 'lg', x: 14, y: 86 },
    { emoji: '👨‍🎓', tier: 'lg', x: 92, y: 50 },
    { emoji: '❓', tier: 'md', x: 46, y: 20 },
    { emoji: '✅', tier: 'md', x: 26, y: 46 },
    { emoji: '🚀', tier: 'md', x: 60, y: 36 },
    { emoji: '📊', tier: 'md', x: 6, y: 46 },
    { emoji: '🎨', tier: 'md', x: 82, y: 60 },
    { emoji: '🌟', tier: 'md', x: 40, y: 90 },
    { emoji: '💫', tier: 'md', x: 74, y: 6 },
    { emoji: '💜', tier: 'sm', x: 32, y: 68 },
    { emoji: '💙', tier: 'sm', x: 54, y: 58 },
    { emoji: '💛', tier: 'sm', x: 88, y: 12 },
    { emoji: '🟣', tier: 'sm', x: 2, y: 24 },
    { emoji: '🔵', tier: 'sm', x: 96, y: 68 },
    { emoji: '🟢', tier: 'sm', x: 18, y: 62 },
    { emoji: '🔴', tier: 'sm', x: 62, y: 8 }
  ];

  const CONFETTI_COLORS = ['#e21b3c', '#1368ce', '#d89e00', '#26890c', '#7c3aed', '#ec4899', '#06b6d4', '#f97316'];

  const DARK_EMOJI_LAYOUT = [
    { emoji: '🌙', tier: 'hero', x: 2, y: 4 },
    { emoji: '⭐', tier: 'hero', x: 82, y: 6 },
    { emoji: '🚀', tier: 'hero', x: 78, y: 72 },
    { emoji: '🌌', tier: 'hero', x: 4, y: 78 },
    { emoji: '💫', tier: 'mega', x: 14, y: 32 },
    { emoji: '🔮', tier: 'mega', x: 72, y: 36 },
    { emoji: '⚡', tier: 'mega', x: 8, y: 52 },
    { emoji: '🛸', tier: 'mega', x: 88, y: 22 },
    { emoji: '✨', tier: 'mega', x: 62, y: 84 },
    { emoji: '🎓', tier: 'lg', x: 22, y: 12 },
    { emoji: '📡', tier: 'lg', x: 64, y: 14 },
    { emoji: '🎯', tier: 'lg', x: 38, y: 8 },
    { emoji: '🏆', tier: 'lg', x: 48, y: 82 },
    { emoji: '💡', tier: 'lg', x: 12, y: 86 },
    { emoji: '📊', tier: 'lg', x: 92, y: 48 },
    { emoji: '🔥', tier: 'md', x: 44, y: 22 },
    { emoji: '🌠', tier: 'md', x: 28, y: 48 },
    { emoji: '🪐', tier: 'md', x: 58, y: 38 },
    { emoji: '🎮', tier: 'md', x: 6, y: 44 },
    { emoji: '❓', tier: 'md', x: 84, y: 58 },
    { emoji: '🎉', tier: 'sm', x: 34, y: 66 },
    { emoji: '💜', tier: 'sm', x: 52, y: 58 },
    { emoji: '💙', tier: 'sm', x: 90, y: 10 },
    { emoji: '💛', tier: 'sm', x: 2, y: 26 }
  ];

  const DARK_ORBS = [
    { color: '#7c3aed', size: 420, x: -8, y: -12, delay: 0 },
    { color: '#2563eb', size: 360, x: 72, y: 58, delay: -4 },
    { color: '#ec4899', size: 280, x: 58, y: -10, delay: -2 },
    { color: '#06b6d4', size: 240, x: -5, y: 62, delay: -6 },
    { color: '#6366f1', size: 200, x: 82, y: 18, delay: -3 },
    { color: '#f59e0b', size: 160, x: 20, y: 38, delay: -5, op: 0.45 }
  ];

  const NEON_PARTICLE_COLORS = ['#60a5fa', '#a78bfa', '#f472b6', '#34d399', '#fbbf24', '#22d3ee'];

  function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || 'dark';
  }

  function ensureLightBgStructure() {
    document.querySelectorAll('.bg-light').forEach(bg => {
      if (!bg.querySelector('.bg-light-rays')) {
        const grad = bg.querySelector('.bg-light-grad');
        const rays = document.createElement('div');
        rays.className = 'bg-light-rays';
        bg.insertBefore(rays, grad ? grad.nextSibling : bg.firstChild);
      }
      if (!bg.querySelector('.bg-light-blob')) {
        const dots = bg.querySelector('.bg-light-dots');
        ['lb1', 'lb2', 'lb3', 'lb4', 'lb5', 'lb6'].forEach(cls => {
          const blob = document.createElement('div');
          blob.className = 'bg-light-blob ' + cls;
          bg.insertBefore(blob, dots || null);
        });
      }
      if (!bg.querySelector('.bg-light-ring')) {
        const dots = bg.querySelector('.bg-light-dots');
        ['lr1', 'lr2', 'lr3', 'lr4'].forEach(cls => {
          const ring = document.createElement('div');
          ring.className = 'bg-light-ring ' + cls;
          bg.insertBefore(ring, dots || null);
        });
      }
    });
  }

  function createWave() {
    const wrap = document.createElement('div');
    wrap.className = 'party-wave';
    wrap.innerHTML = '<svg viewBox="0 0 1440 140" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path fill="rgba(124,58,237,.12)" d="M0,80 C240,120 480,40 720,70 C960,100 1200,30 1440,60 L1440,140 L0,140 Z"/>' +
      '<path fill="rgba(19,104,206,.1)" d="M0,90 C360,50 720,110 1080,65 C1260,45 1380,75 1440,85 L1440,140 L0,140 Z"/>' +
      '<path fill="rgba(226,27,60,.08)" d="M0,100 C480,130 960,60 1440,95 L1440,140 L0,140 Z"/>' +
      '</svg>';
    return wrap;
  }

  function mountLightDecor() {
    ensureLightBgStructure();
    unmountLightDecor();

    const root = document.createElement('div');
    root.id = 'light-party-bg';
    root.className = 'light-party-bg';
    root.setAttribute('aria-hidden', 'true');

    root.appendChild(Object.assign(document.createElement('div'), { className: 'party-mesh' }));
    root.appendChild(Object.assign(document.createElement('div'), { className: 'party-vignette' }));

    KAHOOT_DISCS.forEach(d => {
      const disc = document.createElement('div');
      disc.className = 'party-disc';
      disc.style.cssText = [
        'width:' + d.size + 'px',
        'height:' + d.size + 'px',
        'left:' + d.x + '%',
        'top:' + d.y + '%',
        'background:' + d.color,
        '--rot:' + d.rot + 'deg',
        'opacity:' + (d.op || 0.68),
        'animation-delay:' + d.delay + 's'
      ].join(';');
      root.appendChild(disc);
    });

    KAHOOT_TRIS.forEach(t => {
      const tri = document.createElement('div');
      tri.className = 'party-tri';
      const h = Math.round(t.size * 0.866);
      tri.style.cssText = [
        'left:' + t.x + '%',
        'top:' + t.y + '%',
        '--rot:' + t.rot + 'deg',
        'animation-delay:' + t.delay + 's',
        'border-left:' + (t.size / 2) + 'px solid transparent',
        'border-right:' + (t.size / 2) + 'px solid transparent',
        'border-bottom:' + h + 'px solid ' + t.color
      ].join(';');
      root.appendChild(tri);
    });

    root.appendChild(createWave());

    for (let i = 0; i < 16; i++) {
      const b = document.createElement('div');
      b.className = 'party-bubble';
      const sz = 40 + Math.random() * 80;
      b.style.cssText = [
        'width:' + sz + 'px',
        'height:' + sz + 'px',
        'left:' + (Math.random() * 96) + '%',
        'top:' + (Math.random() * 96) + '%',
        'animation-duration:' + (14 + Math.random() * 12) + 's',
        'animation-delay:' + (-Math.random() * 14) + 's'
      ].join(';');
      root.appendChild(b);
    }

    for (let i = 0; i < 8; i++) {
      const p = document.createElement('div');
      p.className = 'party-plus';
      p.textContent = '+';
      p.style.cssText = [
        'font-size:' + (48 + Math.random() * 64) + 'px',
        'left:' + (Math.random() * 90) + '%',
        'top:' + (Math.random() * 90) + '%',
        'animation-duration:' + (18 + Math.random() * 20) + 's',
        'animation-delay:' + (-Math.random() * 10) + 's'
      ].join(';');
      root.appendChild(p);
    }

    const emojiLayer = document.createElement('div');
    emojiLayer.className = 'light-party-emoji-layer';

    EMOJI_LAYOUT.forEach((item, i) => {
      const el = document.createElement('div');
      el.className = 'light-float light-float-' + item.tier;
      el.textContent = item.emoji;
      el.style.cssText = [
        'left:' + item.x + '%',
        'top:' + item.y + '%',
        'animation-duration:' + (8 + (i % 6) * 2 + Math.random() * 4) + 's',
        'animation-delay:' + (-i * 0.8 - Math.random() * 3) + 's'
      ].join(';');
      emojiLayer.appendChild(el);
    });
    root.appendChild(emojiLayer);

    const fxLayer = document.createElement('div');
    fxLayer.className = 'light-float-layer';

    for (let i = 0; i < 55; i++) {
      const c = document.createElement('div');
      c.className = 'party-confetti';
      const w = 8 + Math.random() * 12;
      const h = 6 + Math.random() * 10;
      c.style.cssText = [
        'left:' + (Math.random() * 100) + '%',
        'width:' + w + 'px',
        'height:' + h + 'px',
        'background:' + CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        'border-radius:' + (Math.random() > 0.5 ? '50%' : '2px'),
        'animation-duration:' + (6 + Math.random() * 10) + 's',
        'animation-delay:' + (-Math.random() * 12) + 's'
      ].join(';');
      fxLayer.appendChild(c);
    }

    for (let i = 0; i < 45; i++) {
      const sp = document.createElement('div');
      sp.className = 'light-sparkle';
      const size = 6 + Math.random() * 12;
      sp.style.cssText = [
        'left:' + (Math.random() * 100) + '%',
        'top:' + (Math.random() * 100) + '%',
        'width:' + size + 'px',
        'height:' + size + 'px',
        'animation-duration:' + (1.5 + Math.random() * 2.5) + 's',
        'animation-delay:' + (-Math.random() * 4) + 's'
      ].join(';');
      fxLayer.appendChild(sp);
    }

    root.appendChild(fxLayer);

    const bgLight = document.querySelector('.bg-light');
    if (bgLight && bgLight.parentNode) {
      bgLight.parentNode.insertBefore(root, bgLight.nextSibling);
    } else {
      document.body.insertBefore(root, document.body.firstChild);
    }
    root.style.zIndex = '1';
    document.documentElement.classList.add('party-active');
    document.body.classList.add('party-active');
  }

  function unmountLightDecor() {
    document.getElementById('light-party-bg')?.remove();
    document.documentElement.classList.remove('party-active');
    document.body.classList.remove('party-active');
  }

  function mountDarkDecor() {
    unmountDarkDecor();

    const root = document.createElement('div');
    root.id = 'dark-party-bg';
    root.className = 'dark-party-bg';
    root.setAttribute('aria-hidden', 'true');

    root.appendChild(Object.assign(document.createElement('div'), { className: 'dark-nebula' }));
    root.appendChild(Object.assign(document.createElement('div'), { className: 'dark-aurora dark-aurora-a' }));
    root.appendChild(Object.assign(document.createElement('div'), { className: 'dark-aurora dark-aurora-b' }));
    root.appendChild(Object.assign(document.createElement('div'), { className: 'dark-grid' }));
    root.appendChild(Object.assign(document.createElement('div'), { className: 'dark-scanline' }));

    const orbLayer = document.createElement('div');
    orbLayer.className = 'dark-orb-layer';
    DARK_ORBS.forEach(o => {
      const el = document.createElement('div');
      el.className = 'dark-neon-orb';
      el.style.cssText = [
        'width:' + o.size + 'px',
        'height:' + o.size + 'px',
        'left:' + o.x + '%',
        'top:' + o.y + '%',
        'background:' + o.color,
        'opacity:' + (o.op || 0.55),
        'animation-delay:' + o.delay + 's'
      ].join(';');
      orbLayer.appendChild(el);
    });
    root.appendChild(orbLayer);

    const starLayer = document.createElement('div');
    starLayer.className = 'dark-starfield';
    for (let i = 0; i < 90; i++) {
      const s = document.createElement('div');
      s.className = 'dark-star';
      const sz = 1 + Math.random() * 2.8;
      s.style.cssText = [
        'left:' + (Math.random() * 100) + '%',
        'top:' + (Math.random() * 100) + '%',
        'width:' + sz + 'px',
        'height:' + sz + 'px',
        'animation-duration:' + (2 + Math.random() * 4) + 's',
        'animation-delay:' + (-Math.random() * 5) + 's',
        'opacity:' + (0.35 + Math.random() * 0.65)
      ].join(';');
      starLayer.appendChild(s);
    }
    root.appendChild(starLayer);

    const shootLayer = document.createElement('div');
    shootLayer.className = 'dark-shoot-layer';
    for (let i = 0; i < 7; i++) {
      const sh = document.createElement('div');
      sh.className = 'dark-shooting-star';
      sh.style.cssText = [
        'left:' + (Math.random() * 80) + '%',
        'top:' + (Math.random() * 40) + '%',
        'animation-duration:' + (4 + Math.random() * 6) + 's',
        'animation-delay:' + (-Math.random() * 8) + 's'
      ].join(';');
      shootLayer.appendChild(sh);
    }
    root.appendChild(shootLayer);

    const emojiLayer = document.createElement('div');
    emojiLayer.className = 'dark-emoji-layer';
    DARK_EMOJI_LAYOUT.forEach((item, i) => {
      const el = document.createElement('div');
      el.className = 'dark-float dark-float-' + item.tier;
      el.textContent = item.emoji;
      el.style.cssText = [
        'left:' + item.x + '%',
        'top:' + item.y + '%',
        'animation-duration:' + (9 + (i % 5) * 2 + Math.random() * 3) + 's',
        'animation-delay:' + (-i * 0.7 - Math.random() * 2) + 's'
      ].join(';');
      emojiLayer.appendChild(el);
    });
    root.appendChild(emojiLayer);

    const particleLayer = document.createElement('div');
    particleLayer.className = 'dark-particle-layer';
    for (let i = 0; i < 36; i++) {
      const p = document.createElement('div');
      p.className = 'dark-particle';
      const sz = 3 + Math.random() * 5;
      p.style.cssText = [
        'left:' + (Math.random() * 100) + '%',
        'width:' + sz + 'px',
        'height:' + sz + 'px',
        'background:' + NEON_PARTICLE_COLORS[i % NEON_PARTICLE_COLORS.length],
        'box-shadow:0 0 ' + (6 + Math.random() * 10) + 'px currentColor',
        'animation-duration:' + (8 + Math.random() * 12) + 's',
        'animation-delay:' + (-Math.random() * 10) + 's'
      ].join(';');
      particleLayer.appendChild(p);
    }
    root.appendChild(particleLayer);

    root.appendChild(Object.assign(document.createElement('div'), { className: 'dark-vignette' }));

    const anchor = document.querySelector('.bg-light') || document.querySelector('.bg') || document.body.firstChild;
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(root, anchor.nextSibling);
    } else {
      document.body.insertBefore(root, document.body.firstChild);
    }
    root.style.zIndex = '1';
    document.documentElement.classList.add('party-active-dark');
    document.body.classList.add('party-active-dark');
  }

  function unmountDarkDecor() {
    document.getElementById('dark-party-bg')?.remove();
    document.documentElement.classList.remove('party-active-dark');
    document.body.classList.remove('party-active-dark');
  }

  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      const iconChar = t === 'dark' ? '☀️' : '🌙';
      const icon = btn.querySelector('.theme-btn-ic');
      if (icon) icon.textContent = iconChar;
      else btn.textContent = iconChar;
      btn.title = t === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç';
      btn.setAttribute('aria-label', btn.title);
    });
    if (t === 'light') {
      unmountDarkDecor();
      mountLightDecor();
    } else {
      unmountLightDecor();
      mountDarkDecor();
    }
  }

  function setTheme(t) {
    localStorage.setItem(STORAGE_KEY, t);
    applyTheme(t);
  }

  function readUrlTheme() {
    try {
      const t = new URLSearchParams(location.search).get('tema');
      if (t === 'light' || t === 'dark') return t;
    } catch (e) { /* ignore */ }
    return null;
  }

  function initTheme() {
    const urlTheme = readUrlTheme();
    if (urlTheme) {
      localStorage.setItem(STORAGE_KEY, urlTheme);
      applyTheme(urlTheme);
    } else {
      applyTheme(getTheme());
    }
  }

  function toggleTheme() {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }

  function sunumHref() {
    return 'sunum.html?tema=' + encodeURIComponent(getTheme());
  }

  document.addEventListener('DOMContentLoaded', initTheme);
  if (document.readyState !== 'loading') {
    initTheme();
  }
  window.addEventListener('load', function () {
    const t = getTheme();
    if (t === 'light' && !document.getElementById('light-party-bg')) mountLightDecor();
    if (t === 'dark' && !document.getElementById('dark-party-bg')) mountDarkDecor();
  });

  window.ThemeManager = { toggleTheme, getTheme, setTheme, applyTheme, sunumHref };
})();
