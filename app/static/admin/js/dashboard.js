async function loadAnalytics() {
  const res = await fetch("/admin/api/analytics");
  if (!res.ok) return;
  const data = await res.json();

  document.getElementById("statTodayVisitors").textContent = data.today_visitors;
  document.getElementById("statOnlineVisitors").textContent = data.online_visitors;
  document.getElementById("statOfflineVisitors").textContent = data.offline_visitors;
  document.getElementById("statUnreadChats").textContent = data.unread_chats;
  document.getElementById("statTotalChats").textContent = data.total_chats;
  document.getElementById("statActiveAgents").textContent = data.active_agents;
  document.getElementById("statAvgResponse").textContent = data.avg_response_minutes + " min";

  const ctx = document.getElementById("volumeChart");
  if (window._volumeChartInstance) window._volumeChartInstance.destroy();
  window._volumeChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.chart_labels,
      datasets: [{
        label: "Chats started",
        data: data.chart_counts,
        borderColor: "#4f46e5",
        backgroundColor: "rgba(79,70,229,0.12)",
        tension: 0.35,
        fill: true,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

loadAnalytics();
setInterval(loadAnalytics, 30000);
