/**
 * main.js — UI interactions, simple chatbot logic, input controls.
 */

$(document).ready(function () {

  // ── Set user name ───────────────────────────────────────────────────────────
  var storedName = localStorage.getItem('jarvis-user-name') || 'User';
  var nameEl = document.getElementById('userName');
  if (nameEl) nameEl.textContent = storedName;

  // ── Restore saved theme ───────────────────────────────────────────────────
  var savedAccent = localStorage.getItem('jarvis-theme');
  if (savedAccent) {
    applyTheme(savedAccent);
    $('#settingAccent').val(savedAccent);
  }

  // ── Trigger Python init (delay slightly) ──────────────────────────────────
  setTimeout(function () {
    console.log('Calling eel.init()...');
    try {
      eel.init()();
    } catch(e) {
      console.error('eel.init() call failed:', e);
    }
  }, 200);

  // ── Settings: Theme picker ────────────────────────────────────────────────
  $('#applySettingsBtn').on('click', function () {
    var accent = $('#settingAccent').val();
    applyTheme(accent);
    localStorage.setItem('jarvis-theme', accent);
  });

  function applyTheme(accent) {
    // For pure grayscale, we'll just set text-primary / accent color
    // We expect accent to be #FFFFFF, #AAAAAA, or #555555
    document.documentElement.style.setProperty('--accent', accent);
  }

  // ── Mic button ────────────────────────────────────────────────────────────
  $('#MicBtn').on('click', function () {
    try { eel.play_assistant_sound(); } catch(e) {}

    $('#MicBtn').addClass('listening');
    setHudStatus('listening', 'Listening...');

    try { eel.takeAllCommands()(); } catch(e) { console.error('eel.takeAllCommands error:', e); }
  });

  // ── Keyboard hotkey: Win+J ────────────────────────────────────────────────
  document.addEventListener('keyup', function (e) {
    if (e.key === 'j' && e.metaKey) {
      try { eel.play_assistant_sound(); } catch(e) {}
      $('#MicBtn').addClass('listening');
      setHudStatus('listening', 'Listening...');
      try { eel.takeAllCommands()(); } catch(e) {}
    }
  });

  // ── Autocomplete for chatbox ────────────────────────────────────────────────
  var availableCommands = [
    "open google", "open youtube", "play music", "what is the time",
    "what is the date", "tell me a joke", "open monitor", "take a screenshot",
    "weather in london", "latest news", "shutdown system", "restart system", "sleep mode"
  ];

  if ($.ui && $.ui.autocomplete) {
    $('#chatbox').autocomplete({
      source: availableCommands,
      minLength: 1,
      classes: { "ui-autocomplete": "jarvis-autocomplete" },
      position: { my: "left bottom-10", at: "left top", collision: "flip" }
    });
  }

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

    setHudStatus('processing', 'Processing...');

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
