document.getElementById("btnSaveHours").addEventListener("click", async () => {
  const rows = document.querySelectorAll("#hoursTbody tr");
  const days = Array.from(rows).map((tr) => ({
    day_of_week: parseInt(tr.dataset.day, 10),
    is_closed: tr.querySelector(".hours-closed").checked,
    open_time: tr.querySelector(".hours-open").value,
    close_time: tr.querySelector(".hours-close").value,
  }));

  const res = await fetch("/admin/api/business-hours", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ days }),
  });
  if (res.ok) {
    alert("Business hours saved.");
  } else {
    alert("Could not save business hours.");
  }
});
