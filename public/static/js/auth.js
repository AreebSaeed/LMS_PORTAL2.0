const manualRoleCheckbox = document.getElementById('manual_role');
const roleSelectWrap = document.getElementById('role-select-wrap');
const roleSelect = document.getElementById('role');

if (manualRoleCheckbox && roleSelectWrap) {
  const syncRoleSelect = () => {
    const showRoleSelect = manualRoleCheckbox.checked;
    roleSelectWrap.hidden = !showRoleSelect;
    if (roleSelect) {
      roleSelect.required = showRoleSelect;
    }
  };

  manualRoleCheckbox.addEventListener('change', syncRoleSelect);
  syncRoleSelect();
}
