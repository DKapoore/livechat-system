document.getElementById("btnAddCanned").addEventListener("click", async () => {
  const shortcut = document.getElementById("cannedShortcut").value.trim();
  const message = document.getElementById("cannedMessage").value.trim();
  if (!shortcut || !message) { alert("Shortcut and message are required."); return; }

  const res = await fetch("/admin/api/canned", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shortcut, message }),
  });
  if (res.ok) {
    location.reload();
  } else {
    const data = await res.json().catch(() => ({}));
    alert(data.error || "Could not add canned reply.");
  }
});

document.querySelectorAll(".btn-delete-canned").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!confirm("Delete this canned reply?")) return;
    await fetch(`/admin/api/canned/${btn.dataset.id}`, { method: "DELETE" });
    btn.closest("tr").remove();
  });
});
