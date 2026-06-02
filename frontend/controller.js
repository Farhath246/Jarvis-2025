/**
 * controller.js — eel-exposed functions callable from Python backend.
 * These bridge Python events into UI updates.
 */

$(document).ready(function () {

  // ── Helpers ───────────────────────────────────────────────────────────────
  function currentTime() {
    var now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function appendMessage(html) {
    var chatBox = document.getElementById('chat-canvas-body');
    if (!chatBox) return;
    var wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    var indicator = document.getElementById('typing-indicator');
    if (indicator) {
      chatBox.insertBefore(wrapper.firstChild, indicator);
    } else {
      chatBox.appendChild(wrapper.firstChild);
    }
    chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });
  }

  function showTyping() {
    var el = document.getElementById('typing-indicator');
    if (el) el.style.display = 'flex';
  }

  function hideTyping() {
    var el = document.getElementById('typing-indicator');
    if (el) el.style.display = 'none';
  }

  function setStatus(state, text) {
    if (window.setHudStatus) { window.setHudStatus(state, text); return; }
    var dot  = document.getElementById('status-dot');
    var span = document.getElementById('status-text');
    if (dot)  dot.className   = state;
    if (span) span.textContent = text;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── eel-exposed: Display Jarvis speech ───────────────────────────────────
  eel.expose(DisplayMessage);
  function DisplayMessage(message) {
    console.log('DisplayMessage:', message);

    // Update the wish/status message — works with OR without textillate
    var wishEl = document.getElementById('WishMessage');
    if (wishEl) {
      wishEl.textContent = message;
    }

    // Also try the textillate-powered version if li elements exist
    var liEl = $('.siri-message li:first');
    if (liEl.length) {
      liEl.text(message);
      try { $('.siri-message').textillate('start'); } catch(e) {}
    }

    // Also update siri-text in SiriWave section
    var siriText = document.getElementById('siri-text');
    if (siriText) siriText.textContent = message;

    showTyping();
  }

  // ── eel-exposed: Show main hood (blob) after command finishes ─────────────
  eel.expose(ShowHood);
  function ShowHood() {
    $('#Oval').removeAttr('hidden').show();
    $('#SiriWave').attr('hidden', true).hide();
    hideTyping();
    setStatus('', 'Ready');
    $('#MicBtn').removeClass('listening');
  }

  // ── eel-exposed: User message bubble ─────────────────────────────────────
  eel.expose(senderText);
  function senderText(message) {
    if (!message || !message.trim()) return;
    hideTyping();
    var time = currentTime();
    var html = '<div class="row justify-content-end mb-2 animate__animated animate__fadeInRight">'
      + '<div class="width-size">'
      + '<div class="sender_message">' + escapeHtml(message) + '</div>'
      + '<div class="msg-timestamp text-end">' + time + '</div>'
      + '</div></div>';
    appendMessage(html);
    showTyping();
    setStatus('processing', 'Processing...');
  }

  // ── eel-exposed: Jarvis response bubble ──────────────────────────────────
  eel.expose(receiverText);
  function receiverText(message) {
    if (!message || !message.trim()) return;
    hideTyping();
    var time = currentTime();
    var html = '<div class="row justify-content-start mb-2 animate__animated animate__fadeInLeft">'
      + '<div class="width-size">'
      + '<div class="receiver_message">' + escapeHtml(message) + '</div>'
      + '<div class="msg-timestamp">' + time + '</div>'
      + '</div></div>';
    appendMessage(html);
  }

  // ── eel-exposed: Live Face Preview ─────────────────────────────────────────
  eel.expose(updateFacePreview);
  function updateFacePreview(base64Image) {
    var img = document.getElementById('face-preview');
    if (img) {
      img.src = 'data:image/jpeg;base64,' + base64Image;
    }
  }

  eel.expose(updateFaceStatus);
  function updateFaceStatus(timeLeft, attempts, maxAttempts) {
    var timerEl = document.getElementById('face-timer');
    var confEl = document.getElementById('face-confidence');
    if (timerEl) timerEl.textContent = 'Timeout: ' + timeLeft + 's';
    if (confEl && (!confEl.textContent.includes('match'))) {
      confEl.textContent = 'Attempts: ' + attempts + '/' + maxAttempts;
    }
  }

  eel.expose(showFaceDetected);
  function showFaceDetected(confidence) {
    var oval = document.getElementById('face-oval');
    var confEl = document.getElementById('face-confidence');
    var textEl = document.getElementById('face-guide-text');
    if (oval) { oval.classList.remove('failed'); oval.classList.add('detected'); }
    if (confEl) confEl.textContent = confidence + '% match';
    if (textEl) textEl.textContent = 'Face detected...';
  }

  eel.expose(showFaceNotDetected);
  function showFaceNotDetected() {
    var oval = document.getElementById('face-oval');
    var textEl = document.getElementById('face-guide-text');
    if (oval) { oval.classList.remove('detected'); oval.classList.add('failed'); }
    if (textEl) textEl.textContent = 'Face not recognised';
  }

  eel.expose(playSuccessBeep);
  function playSuccessBeep() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // A5
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
      osc.start();
      osc.stop(ctx.currentTime + 0.5);
    } catch(e) { console.warn('Audio beep error', e); }
  }

  // ── eel-exposed: Hide SVG loader → show face auth animation ──────────────
  eel.expose(hideLoader);
  function hideLoader() {
    console.log('hideLoader called');
    $('#Loader').attr('hidden', true);
    $('#FaceAuth').removeAttr('hidden');
    DisplayMessage('Ready for face authentication...');
  }

  // ── eel-exposed: Face auth detected → show success animation ─────────────
  eel.expose(hideFaceAuth);
  function hideFaceAuth() {
    console.log('hideFaceAuth called — face recognised!');
    $('#FaceAuth').attr('hidden', true);
    $('#FaceAuthSuccess').removeAttr('hidden');
    DisplayMessage('Face recognised!');
  }

  // ── eel-exposed: Face auth success → show greeting animation ─────────────
  eel.expose(hideFaceAuthSuccess);
  function hideFaceAuthSuccess() {
    $('#FaceAuthSuccess').attr('hidden', true);
    $('#HelloGreet').removeAttr('hidden');
    var name = localStorage.getItem('jarvis-user-name') || 'User';
    DisplayMessage('Welcome, ' + name + '!');
  }

  // ── eel-exposed: Hide start screen → animate in the hood ─────────────────
  eel.expose(hideStart);
  function hideStart() {
    console.log('hideStart called — transitioning to main UI');
    $('#Start').attr('hidden', true);
    setTimeout(function () {
      $('#Oval')
        .addClass('animate__animated animate__zoomIn')
        .removeAttr('hidden')
        .show();
    }, 800);
  }

  // ── eel-exposed: Show auth failed state ──────────────────────────────────
  eel.expose(showAuthFailed);
  function showAuthFailed() {
    console.log('showAuthFailed called');
    $('#FaceAuth').attr('hidden', true);
    $('#HelloGreet').attr('hidden', true);
    DisplayMessage('Face not recognised. Please try again.');

    // Show retry button
    var wishEl = document.getElementById('WishMessage');
    if (wishEl) {
      wishEl.innerHTML = 'Face not recognised &mdash; '
        + '<button onclick="retryAuth()" class="retry-auth-btn">Retry</button>';
    }
  }

  window.retryAuth = function () {
    DisplayMessage('Retrying face authentication...');
    var wishEl = document.getElementById('WishMessage');
    if (wishEl) wishEl.textContent = 'Retrying...';
    $('#FaceAuth').removeAttr('hidden');
    try { eel.retryFaceAuth()(); } catch(e) { console.error('retryFaceAuth error:', e); }
  };

  // ── eel-exposed: Set user name from Python config ─────────────────────────
  eel.expose(setUserName);
  function setUserName(name) {
    localStorage.setItem('jarvis-user-name', name);
    var el = document.getElementById('userName');
    if (el) el.textContent = name;
  }

});
