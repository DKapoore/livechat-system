async function loadVisitors() {
  const search = document.getElementById("visitorSearch").value;
  const filter = document.getElementById("visitorFilter").value;
  const res = await fetch(`/admin/api/visitors?search=${encodeURIComponent(search)}&filter=${filter}`);
  const data = await res.json();
  renderVisitors(data.visitors);
}

function renderVisitors(visitors) {
  const tbody = document.getElementById("visitorsTbody");
  tbody.innerHTML = "";
  visitors.forEach((v) => {
    const tr = document.createElement("tr");
    const lastSeen = v.last_seen ? new Date(v.last_seen).toLocaleString() : "—";
    tr.innerHTML = `
      <td>${v.visitor_uid}</td>
      <td>${escapeHtml(v.name || "—")}</td>
      <td>${escapeHtml(v.mobile || "—")}</td>
      <td>${escapeHtml(v.email || "—")}</td>
      <td>${v.is_online ? "🟢 Online" : "⚪ Offline"}</td>
      <td>${v.visit_count}</td>
      <td>${v.lead_score}</td>
      <td>${(v.tags || []).join(", ") || "—"}</td>
      <td>${lastSeen}</td>
      <td>
        <button class="btn-small btn-vip" data-id="${v.id}" data-val="${!v.is_vip}">${v.is_vip ? "Unmark VIP" : "Mark VIP"}</button>
        <button class="btn-small btn-danger btn-block" data-id="${v.id}" data-val="${!v.is_blocked}">${v.is_blocked ? "Unblock" : "Block"}</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".btn-vip").forEach((btn) => {
    btn.addEventListener("click", () => updateVisitor(btn.dataset.id, { is_vip: btn.dataset.val === "true" }));
  });
  tbody.querySelectorAll(".btn-block").forEach((btn) => {
    btn.addEventListener("click", () => updateVisitor(btn.dataset.id, { is_blocked: btn.dataset.val === "true" }));
  });
}

async function updateVisitor(id, patch) {
  await fetch(`/admin/api/visitors/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  loadVisitors();
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function debounce(fn, delay) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

document.getElementById("visitorSearch").addEventListener("input", debounce(loadVisitors, 300));
document.getElementById("visitorFilter").addEventListener("change", loadVisitors);
loadVisitors();
