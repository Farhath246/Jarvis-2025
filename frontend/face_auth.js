$(document).ready(function () {
  // Start Face Auth immediately on load
  eel.startFaceAuth()();

  $('#retryBtn').on('click', function() {
    $('#retryBtn').attr('hidden', true);
    $('#faceError').text('');
    $('#face-guide-text').text('Starting camera...');
    eel.startFaceAuth()();
  });

  eel.expose(updateFacePreview);
  function updateFacePreview(base64Image) {
    var img = document.getElementById('face-preview');
    if (img) { img.src = 'data:image/jpeg;base64,' + base64Image; }
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
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine'; osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
      osc.start(); osc.stop(ctx.currentTime + 0.5);
    } catch(e) { console.warn('Audio beep error', e); }
  }

  eel.expose(hideFaceAuth);
  function hideFaceAuth() {
    // Unused in standalone page
  }

  eel.expose(hideFaceAuthSuccess);
  function hideFaceAuthSuccess() {
    $('#face-guide-text').text('Success! Redirecting...');
    setTimeout(() => {
      window.location.href = "index.html";
    }, 500);
  }

  eel.expose(showAuthFailed);
  function showAuthFailed() {
    $('#faceError').text('Face not recognised. Please try again or login with password.');
    $('#retryBtn').removeAttr('hidden');
    
    // Reset preview to empty placeholder
    var img = document.getElementById('face-preview');
    if (img) { img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'; }
    $('#face-guide-text').text('Authentication Failed');
    var oval = document.getElementById('face-oval');
    if (oval) { oval.classList.remove('detected'); oval.classList.add('failed'); }
  }
});
