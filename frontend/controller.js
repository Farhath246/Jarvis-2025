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

  function appendSystemMessage(msg) {
    var time = currentTime();
    var html = '<div class="d-flex justify-content-center mb-2">'
      + '<div style="font-size: 0.8rem; color: var(--text-muted); background: var(--bg-secondary); padding: 4px 12px; border-radius: 12px;">'
      + escapeHtml(msg) + ' &middot; ' + time
      + '</div></div>';
    appendMessage(html);
  }

  // ── eel-exposed: Display Jarvis speech ───────────────────────────────────
  eel.expose(DisplayMessage);
  function DisplayMessage(message) {
    console.log('DisplayMessage:', message);
    var wishEl = document.getElementById('WishMessage');
    if (wishEl) {
      wishEl.textContent = message;
    }
    showTyping();
  }

  // ── eel-exposed: Reset state after command ───────────────────────────────
  eel.expose(ShowHood);
  function ShowHood() {
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
    var html = '<div class="d-flex justify-content-end mb-2">'
      + '<div class="width-size">'
      + '<div class="sender_message">' + escapeHtml(message) + '</div>'
      + '<div class="msg-timestamp text-end">' + time + '</div>'
      + '</div></div>';
    appendMessage(html);
    showTyping();
    setStatus('processing', 'Processing...');
  }

  function formatMessage(message) {
    let escaped = escapeHtml(message);
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/`(.*?)`/g, '<code>$1</code>');
    escaped = escaped.replace(/\[(.*?)\]\((https?:\/\/.*?)\)/g, function(match, text, url) {
      return '<a href="' + url + '" target="_blank" class="chat-source-link">' + text + '</a>';
    });
    return escaped.replace(/\n/g, '<br/>');
  }

  // ── eel-exposed: Jarvis response bubble ──────────────────────────────────
  eel.expose(receiverText);
  function receiverText(message, sources) {
    if (!message || !message.trim()) return;
    hideTyping();
    var time = currentTime();
    var formattedMessage = formatMessage(message);

    var html = '<div class="d-flex justify-content-start mb-2">'
      + '<div class="width-size">'
      + '<div class="receiver_message">' + formattedMessage;

    if (sources && sources.length > 0) {
      html += '<div class="sources-container">';
      sources.forEach(function (src) {
        var domain = '';
        try { domain = new URL(src.url).hostname.replace('www.', ''); } catch(e) { domain = 'Link'; }
        html += '<a href="' + src.url + '" target="_blank" class="source-chip" title="' + escapeHtml(src.title) + '">'
          + '<i class="bi bi-globe"></i> ' + escapeHtml(src.title || domain)
          + '</a>';
      });
      html += '</div>';
    }

    html += '</div>'
      + '<div class="msg-timestamp">' + time + '</div>'
      + '</div></div>';
    appendMessage(html);
  }

  // ── Set Wish Message on Load ──────────────────────────────────────────────
  function setWishMessage() {
    var wishEl = document.getElementById('WishMessage');
    if (wishEl) {
      var time = new Date().getHours();
      if (time < 12) wishEl.textContent = "Good Morning";
      else if (time < 18) wishEl.textContent = "Good Afternoon";
      else wishEl.textContent = "Good Evening";
    }
  }
  setWishMessage();

  eel.expose(setUserName);
  function setUserName(name) {
    localStorage.setItem('jarvis-user-name', name);
    var el = document.getElementById('userName');
    if (el) el.textContent = name;
  }

  eel.expose(setWebStatus);
  function setWebStatus(state, text) {
    setStatus(state, text);
  }

});
