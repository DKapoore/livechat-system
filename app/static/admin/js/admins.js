document.getElementById("btnAddAdmin").addEventListener("click", async () => {
  const name = document.getElementById("newAdminName").value.trim();
  const email = document.getElementById("newAdminEmail").value.trim();
  const password = document.getElementById("newAdminPassword").value.trim() || "changeme123";
  const role_id = document.getElementById("newAdminRole").value;
  if (!name || !email) { alert("Name and email are required."); return; }

  const res = await fetch("/admin/api/admins", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password, role_id }),
  });
  if (res.ok) {
    location.reload();
  } else {
    const data = await res.json().catch(() => ({}));
    alert(data.error || "Could not add team member.");
  }
});

document.querySelectorAll(".role-select").forEach((sel) => {
  sel.addEventListener("change", async () => {
    await fetch(`/admin/api/admins/${sel.dataset.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role_id: parseInt(sel.value, 10) }),
    });
  });
});

document.querySelectorAll(".btn-delete-admin").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!confirm("Remove this team member?")) return;
    const res = await fetch(`/admin/api/admins/${btn.dataset.id}`, { method: "DELETE" });
    if (res.ok) {
      btn.closest("tr").remove();
    } else {
      const data = await res.json().catch(() => ({}));
      alert(data.error || "Could not remove.");
    }
  });
});
