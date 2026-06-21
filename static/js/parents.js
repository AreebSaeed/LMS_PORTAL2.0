const enableLogin = document.getElementById('enable_login');
const loginFields = document.querySelectorAll('.login-fields');

if (enableLogin && loginFields.length) {
  const sync = () => {
    const show = enableLogin.checked;
    loginFields.forEach((el) => { el.hidden = !show; });
    const pwd = document.getElementById('login_password');
    if (pwd) pwd.required = show;
  };
  enableLogin.addEventListener('change', sync);
  sync();
}
