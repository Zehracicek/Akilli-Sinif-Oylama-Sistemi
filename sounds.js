/**
 * sounds.js — Web Audio ile Kahoot tarzı ses efektleri
 * Harici dosya gerekmez; tarayıcıda sentezlenir.
 */
(function () {
  const STORAGE_KEY = 'akillisınıf_ses';
  let ctx = null;
  let muted = localStorage.getItem(STORAGE_KEY) === 'off';
  let unlocked = false;

  function getCtx() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function unlock() {
    if (unlocked) return;
    const c = getCtx();
    if (!c) return;
    unlocked = true;
    const o = c.createOscillator();
    const g = c.createGain();
    g.gain.value = 0.0001;
    o.connect(g);
    g.connect(c.destination);
    o.start();
    o.stop(c.currentTime + 0.01);
  }

  function play(fn) {
    if (muted) return;
    const c = getCtx();
    if (!c) return;
    try { fn(c, c.currentTime); } catch (e) { /* sessizce geç */ }
  }

  function tone(c, t, freq, dur, type, vol, slideTo) {
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = type || 'sine';
    o.frequency.setValueAtTime(freq, t);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol || 0.15, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g);
    g.connect(c.destination);
    o.start(t);
    o.stop(t + dur + 0.05);
  }

  function noiseBurst(c, t, dur, vol) {
    const bufferSize = c.sampleRate * dur;
    const buffer = c.createBuffer(1, bufferSize, c.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
    const src = c.createBufferSource();
    src.buffer = buffer;
    const g = c.createGain();
    g.gain.setValueAtTime(vol || 0.08, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(g);
    g.connect(c.destination);
    src.start(t);
  }

  const SFX = {
    click() {
      play((c, t) => tone(c, t, 880, 0.06, 'square', 0.06));
    },
    join() {
      play((c, t) => {
        tone(c, t, 523, 0.12, 'sine', 0.12);
        tone(c, t + 0.1, 659, 0.12, 'sine', 0.12);
        tone(c, t + 0.2, 784, 0.18, 'sine', 0.14);
      });
    },
    countdown() {
      play((c, t) => {
        tone(c, t, 440, 0.15, 'triangle', 0.18);
        noiseBurst(c, t, 0.04, 0.04);
      });
    },
    countdownGo() {
      play((c, t) => {
        tone(c, t, 880, 0.08, 'square', 0.1);
        tone(c, t + 0.08, 1175, 0.25, 'sine', 0.16, 1760);
      });
    },
    questionIn() {
      play((c, t) => {
        tone(c, t, 220, 0.2, 'sawtooth', 0.06, 660);
        tone(c, t + 0.05, 880, 0.25, 'sine', 0.1);
      });
    },
    select() {
      play((c, t) => tone(c, t, 620, 0.07, 'triangle', 0.09, 740));
    },
    tick() {
      play((c, t) => tone(c, t, 920, 0.05, 'square', 0.07));
    },
    tickUrgent() {
      play((c, t) => {
        tone(c, t, 1100, 0.06, 'square', 0.12);
        tone(c, t + 0.07, 880, 0.06, 'square', 0.1);
      });
    },
    lock() {
      play((c, t) => {
        tone(c, t, 180, 0.25, 'sawtooth', 0.08, 90);
        noiseBurst(c, t, 0.12, 0.06);
      });
    },
    correct() {
      play((c, t) => {
        [523, 659, 784, 1047].forEach((f, i) => tone(c, t + i * 0.09, f, 0.14, 'sine', 0.13));
      });
    },
    wrong() {
      play((c, t) => {
        tone(c, t, 330, 0.2, 'sawtooth', 0.1, 220);
        tone(c, t + 0.15, 220, 0.25, 'sawtooth', 0.08, 165);
      });
    },
    sent() {
      play((c, t) => tone(c, t, 740, 0.1, 'sine', 0.08, 880));
    },
    next() {
      play((c, t) => {
        tone(c, t, 440, 0.1, 'triangle', 0.1);
        tone(c, t + 0.12, 660, 0.15, 'triangle', 0.12, 880);
      });
    },
    victory() {
      play((c, t) => {
        [392, 494, 587, 784, 988].forEach((f, i) => tone(c, t + i * 0.1, f, 0.2, 'sine', 0.12));
        noiseBurst(c, t + 0.5, 0.3, 0.05);
      });
    },
    toast() {
      play((c, t) => tone(c, t, 560, 0.08, 'sine', 0.07));
    },
    error() {
      play((c, t) => tone(c, t, 200, 0.2, 'square', 0.08, 150));
    }
  };

  function setMuted(m) {
    muted = m;
    localStorage.setItem(STORAGE_KEY, m ? 'off' : 'on');
    updateToggleButtons();
  }

  function toggleMute() {
    setMuted(!muted);
  }

  function isMuted() { return muted; }

  function updateToggleButtons() {
    document.querySelectorAll('.sound-toggle-btn').forEach(btn => {
      btn.textContent = muted ? '🔇' : '🔊';
      btn.title = muted ? 'Sesleri aç' : 'Sesleri kapat';
      btn.setAttribute('aria-label', btn.title);
      btn.classList.toggle('muted', muted);
    });
  }

  function mountToggle() {
    if (document.querySelector('.sound-toggle-btn')) {
      updateToggleButtons();
      return;
    }
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sound-toggle-btn';
    btn.onclick = () => { unlock(); toggleMute(); };
    const mount = document.getElementById('sound-toggle-mount');
    (mount || document.body).appendChild(btn);
    updateToggleButtons();
  }

  document.addEventListener('click', unlock, { once: false });
  document.addEventListener('keydown', unlock, { once: false });
  document.addEventListener('DOMContentLoaded', mountToggle);
  if (document.readyState !== 'loading') mountToggle();

  window.SoundFX = Object.assign({ unlock, setMuted, toggleMute, isMuted }, SFX);
})();
