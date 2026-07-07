document.getElementById("btnAddFaq").addEventListener("click", async () => {
  const question = document.getElementById("faqQuestion").value.trim();
  const category = document.getElementById("faqCategory").value.trim() || "General";
  const answer = document.getElementById("faqAnswer").value.trim();
  if (!question || !answer) { alert("Question and answer are required."); return; }

  const res = await fetch("/admin/api/faq", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, category, answer }),
  });
  if (res.ok) {
    location.reload();
  } else {
    alert("Could not add FAQ.");
  }
});

document.querySelectorAll(".btn-delete-faq").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!confirm("Delete this FAQ?")) return;
    await fetch(`/admin/api/faq/${btn.dataset.id}`, { method: "DELETE" });
    btn.closest("tr").remove();
  });
});
