/**
 * main.js — UI interactions, live clock, SiriWave, input controls.
 */

$(document).ready(function () {

  // ── Set user name from config (exposed by Python or stored locally) ───────
  var storedName = localStorage.getItem('jarvis-user-name') || 'User';
  var nameEl = document.getElementById('userName');
  if (nameEl) nameEl.textContent = storedName;

  // ── Restore saved accent colour ───────────────────────────────────────────
  var savedAccent = localStorage.getItem('jarvis-accent');
  if (savedAccent) {
    applyAccent(savedAccent);
    $('#settingAccent').val(savedAccent);
  }

  // ── Textillate animations (must init BEFORE calling eel.init) ────────────
  try {
    $('.text').textillate({
      loop: true, speed: 1500, sync: true,
      in:  { effect: 'bounceIn' },
      out: { effect: 'bounceOut' },
    });
  } catch(e) { console.warn('textillate .text error:', e); }

  try {
    $('.siri-message').textillate({
      loop: true, sync: true,
      in:  { effect: 'fadeInUp',  sync: true },
      out: { effect: 'fadeOutUp', sync: true },
    });
  } catch(e) { console.warn('textillate .siri-message error:', e); }

  // ── SiriWave (responsive width) ────────────────────────────────────────────
  var siriWave;
  function initSiriWave() {
    var container = document.getElementById('siri-container');
    if (!container) return;
    var width = Math.min(container.parentElement.offsetWidth || 900, 900);
    try {
      siriWave = new SiriWave({
        container: container,
        width: width,
        style: 'ios9',
        amplitude: '1',
        speed: '0.30',
        height: 200,
        autostart: true,
      });
    } catch(e) { console.warn('SiriWave init error:', e); }
  }
  initSiriWave();

  // Reinitialise SiriWave on resize for responsiveness
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      var container = document.getElementById('siri-container');
      if (container) container.innerHTML = '';
      initSiriWave();
    }, 300);
  });

  // ── Live HUD clock & date ─────────────────────────────────────────────────
  function updateClock() {
    var now  = new Date();
    var time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    var date = now.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    var clockEl = document.getElementById('hud-clock');
    var dateEl  = document.getElementById('hud-date');
    if (clockEl) clockEl.textContent = time;
    if (dateEl)  dateEl.textContent  = date;
  }
  updateClock();
  setInterval(updateClock, 1000);

  // ── Trigger Python init AFTER textillate is ready (200ms delay) ───────────
  setTimeout(function () {
    console.log('Calling eel.init()...');
    try {
      eel.init()();
    } catch(e) {
      console.error('eel.init() call failed:', e);
    }
  }, 200);

  // ── Settings: accent colour picker ────────────────────────────────────────
  $('#applySettingsBtn').on('click', function () {
    var accent = $('#settingAccent').val();
    applyAccent(accent);
    localStorage.setItem('jarvis-accent', accent);
  });

  function applyAccent(accent) {
    document.documentElement.style.setProperty('--accent', accent);
    document.documentElement.style.setProperty('--accent-dim',  hexToRgba(accent, 0.15));
    document.documentElement.style.setProperty('--accent-glow', hexToRgba(accent, 0.4));
    document.documentElement.style.setProperty('--border', hexToRgba(accent, 0.2));
  }

  function hexToRgba(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  // ── Mic button ────────────────────────────────────────────────────────────
  $('#MicBtn').on('click', function () {
    try { eel.play_assistant_sound(); } catch(e) {}

    $('#MicBtn').addClass('listening');
    setHudStatus('listening', 'Listening\u2026');

    $('#Oval').attr('hidden', true).hide();
    $('#SiriWave').removeAttr('hidden').show();

    try { eel.takeAllCommands()(); } catch(e) { console.error('eel.takeAllCommands error:', e); }
  });

  // ── Keyboard hotkey: Win+J (triggered by hotword process) ────────────────
  document.addEventListener('keyup', function (e) {
    if (e.key === 'j' && e.metaKey) {
      try { eel.play_assistant_sound(); } catch(e) {}
      $('#MicBtn').addClass('listening');
      setHudStatus('listening', 'Listening\u2026');
      $('#Oval').attr('hidden', true).hide();
      $('#SiriWave').removeAttr('hidden').show();
      try { eel.takeAllCommands()(); } catch(e) {}
    }
  });

  // ── Chatbox input: toggle Mic / Send button (debounced) ───────────────────
  var inputTimer;
  $('#chatbox').on('keyup input', function () {
    clearTimeout(inputTimer);
    var self = this;
    inputTimer = setTimeout(function () {
      var msg = $(self).val().trim();
      if (msg.length > 0) {
        $('#MicBtn').attr('hidden', true);
        $('#SendBtn').removeAttr('hidden');
      } else {
        $('#MicBtn').removeAttr('hidden');
        $('#SendBtn').attr('hidden', true);
      }
    }, 100);
  });

  // ── Send button ───────────────────────────────────────────────────────────
  $('#SendBtn').on('click', function () { sendTextMessage(); });

  // ── Enter key sends message ───────────────────────────────────────────────
  $('#chatbox').on('keypress', function (e) {
    if (e.which === 13) { sendTextMessage(); }
  });

  function sendTextMessage() {
    var message = $('#chatbox').val().trim();
    if (!message) return;

    $('#Oval').attr('hidden', true).hide();
    $('#SiriWave').removeAttr('hidden').show();
    setHudStatus('processing', 'Processing\u2026');

    try { eel.takeAllCommands(message); } catch(e) { console.error('eel.takeAllCommands error:', e); }

    $('#chatbox').val('');
    $('#MicBtn').removeAttr('hidden');
    $('#SendBtn').attr('hidden', true);
  }

  // ── HUD status helper ─────────────────────────────────────────────────────
  function setHudStatus(state, text) {
    var dot  = document.getElementById('status-dot');
    var span = document.getElementById('status-text');
    if (dot)  { dot.className = state; }
    if (span) { span.textContent = text; }
  }
  window.setHudStatus = setHudStatus; // expose for controller.js

  // ── Expose setUserName for Python to call ─────────────────────────────────
  window.setUserName = function (name) {
    localStorage.setItem('jarvis-user-name', name);
    var el = document.getElementById('userName');
    if (el) el.textContent = name;
  };

});
