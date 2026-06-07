$(document).ready(function () {
  // Navigation
  $('#goToSignup').on('click', function() {
    $('#loginCard').attr('hidden', true);
    $('#signupCard').removeAttr('hidden');
    $('#loginError').text('');
  });

  $('#goToLogin').on('click', function() {
    $('#signupCard').attr('hidden', true);
    $('#loginCard').removeAttr('hidden');
    $('#signupError').text('');
  });

  // Auth Submit
  $('#loginBtn').on('click', async function() {
    const username = $('#loginUsername').val().trim();
    const password = $('#loginPassword').val().trim();
    if (!username || !password) {
      $('#loginError').text('Please fill all fields');
      return;
    }
    $('#loginBtn').text('LOGGING IN...').prop('disabled', true);
    let res = await eel.login_user(username, password)();
    if (res.success) {
      localStorage.setItem('jarvis-user-name', username);
      window.location.href = "index.html";
    } else {
      $('#loginError').text(res.message);
      $('#loginBtn').text('LOGIN').prop('disabled', false);
    }
  });

  $('#signupBtn').on('click', async function() {
    const username = $('#signupUsername').val().trim();
    const email = $('#signupEmail').val().trim();
    const password = $('#signupPassword').val().trim();
    if (!username || !email || !password) {
      $('#signupError').text('Please fill all fields');
      return;
    }
    $('#signupBtn').text('SIGNING UP...').prop('disabled', true);
    let res = await eel.register_user(username, email, password)();
    if (res.success) {
      $('#goToLogin').click();
      $('#loginError').text('Account created! You can now login.').css('color', '#55ff55');
    } else {
      $('#signupError').text(res.message);
    }
    $('#signupBtn').text('SIGN UP').prop('disabled', false);
  });

  // Face Auth
  $('#faceAuthBtn').on('click', function() {
    window.location.href = "face_auth.html";
  });

  // To capture Enter key press
  $('#loginPassword').on('keypress', function(e) {
    if (e.which === 13) { $('#loginBtn').click(); }
  });
  $('#signupPassword').on('keypress', function(e) {
    if (e.which === 13) { $('#signupBtn').click(); }
  });
});
