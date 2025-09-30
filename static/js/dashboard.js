// === Tab Switching ===
function openTab(evt, tabName) {
  let tabcontent = document.getElementsByClassName("tabcontent");
  for (let i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }
  let tablinks = document.getElementsByClassName("tablinks");
  for (let i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }
  document.getElementById(tabName).style.display = "block";
  evt.currentTarget.className += " active";
}
document.getElementById("defaultOpen").click();

// === DB Status Banner ===
async function checkDbStatus(){
  try{
    let res = await fetch('/api/db_status');
    if(!res.ok) throw new Error('status');
    let data = await res.json();
    if(!data.available){
      document.getElementById('dbBanner').style.display = 'block';
    } else {
      document.getElementById('dbBanner').style.display = 'none';
    }
  }catch(e){
    document.getElementById('dbBanner').style.display = 'block';
  }
}
checkDbStatus();

// === Pending Decisions ===
async function loadDecisions() {
  let res = await fetch("/decisions/pending");
  let data = await res.json();
  let html = "";
  data.forEach(d => {
    html += `<div class="decision">
      <b>Agent:</b> ${d.agent} | <b>Step:</b> ${d.step}<br>
      <b>Recommendation:</b> ${d.recommendation} | <b>Severity:</b> ${d.severity}<br>
      <b>Tool Stats:</b><br><ul>`;
    d.stats.forEach(s => {
      html += `<li>${s.tool}: Success Rate ${Math.round(s.success_rate*100)}% 
                (${s.successes}/${s.total}), Failures ${s.failures}, 
                Last Used: ${s.last_used || "N/A"}<br>
                <i>Why not?</i> ${d.explanations[s.tool]}</li>`;
    });
    html += `</ul>
      <button onclick="approve('${d.id}','${d.recommendation}')">Approve ${d.recommendation}</button>
      ${d.tools.filter(t=>t!==d.recommendation)
               .map(t=>`<button onclick="approve('${d.id}','${t}')">Override ${t}</button>`).join(" ")}
      </div><hr>`;
  });
  document.getElementById("decisions").innerHTML = html;
}
async function approve(id, choice) {
  await fetch(`/decisions/${id}/approve`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({choice})
  });
  loadDecisions();
}

// === Policy Editor ===
async function loadPolicy() {
  let res = await fetch("/policy");
  let policy = await res.json();
  document.getElementById("policyEditor").value = JSON.stringify(policy, null, 2);
}
async function savePolicy() {
  let updated = document.getElementById("policyEditor").value;
  try {
    let parsed = JSON.parse(updated);
    await fetch("/policy", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(parsed)
    });
    alert("Policy updated!");
    loadHistory();
  } catch (e) {
    alert("Invalid JSON: " + e);
  }
}

// === Policy History ===
async function loadHistory() {
  let res = await fetch("/policy/history");
  let data = await res.json();
  let html = "<ul>";
  data.forEach(h => {
    html += `<li><b>User:</b> ${h.user} | <b>Time:</b> ${h.timestamp}<br>
             <pre>${h.diff}</pre></li>`;
  });
  html += "</ul>";
  document.getElementById("policyHistory").innerHTML = html;
}

// === Export Compliance Decisions ===
function exportDecisions(e) {
  e.preventDefault();
  let agent = document.getElementById("agentFilter").value;
  let status = document.getElementById("statusFilter").value;
  let days = document.getElementById("daysFilter").value;
  let format = document.getElementById("formatFilter").value;
  let url = `/decisions/export?format=${format}`;
  if (agent) url += `&agent=${agent}`;
  if (status) url += `&status=${status}`;
  if (days) url += `&days=${days}`;
  window.open(url, "_blank");
}

// === Live Metrics ===
let usageChart, successChart, apiRpaChart, approvalChart;
let trendAgent = "All";
let trendDays = 1;

async function loadMetrics() {
  let res = await fetch("/metrics/live");
  let data = await res.json();

  document.getElementById("totalDecisions").innerText = data.total;
  document.getElementById("apiPct").innerText = data.api_pct.toFixed(1) + "%";
  document.getElementById("rpaPct").innerText = data.rpa_pct.toFixed(1) + "%";
  document.getElementById("apiCount").innerText = data.api_count;
  document.getElementById("rpaCount").innerText = data.rpa_count;
  document.getElementById("approvedCount").innerText = data.approved;
  document.getElementById("overriddenCount").innerText = data.overridden;

  let ctx = document.getElementById("usageChart").getContext("2d");
  if (!usageChart) {
    usageChart = new Chart(ctx, {
      type: "doughnut",
      data: { labels: ["API", "RPA"], datasets: [{ data: [data.api_count, data.rpa_count] }] }
    });
  } else {
    usageChart.data.datasets[0].data = [data.api_count, data.rpa_count];
    usageChart.update();
  }
}

// === Trend Metrics ===
async function loadTrends() {
  let res = await fetch(`/metrics/trends?agent=${trendAgent}&days=${trendDays}`);
  let data = await res.json();

  let labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
  let successRates = data.map(d => d.success_rate);
  let apiCounts = data.map(d => d.api_count);
  let rpaCounts = data.map(d => d.rpa_count);
  let approvedCounts = data.map(d => d.approved_count);
  let overriddenCounts = data.map(d => d.overridden_count);

  // Success rate chart
  if (!successChart) {
    successChart = new Chart(document.getElementById("successChart").getContext("2d"), {
      type: "line",
      data: { labels, datasets: [{ label: "Success Rate (%)", data: successRates, borderWidth: 2, fill: false }] },
      options: { responsive: true, scales: { y: { min: 0, max: 100 } } }
    });
  } else {
    successChart.data.labels = labels;
    successChart.data.datasets[0].data = successRates;
    successChart.update();
  }

  // API vs RPA usage
  if (!apiRpaChart) {
    apiRpaChart = new Chart(document.getElementById("apiRpaChart").getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "API Usage", data: apiCounts, borderWidth: 2 },
          { label: "RPA Usage", data: rpaCounts, borderWidth: 2 }
        ]
      }
    });
  } else {
    apiRpaChart.data.labels = labels;
    apiRpaChart.data.datasets[0].data = apiCounts;
    apiRpaChart.data.datasets[1].data = rpaCounts;
    apiRpaChart.update();
  }

  // Approvals vs Overrides
  if (!approvalChart) {
    approvalChart = new Chart(document.getElementById("approvalChart").getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "Approved", data: approvedCounts, borderWidth: 2 },
          { label: "Overridden", data: overriddenCounts, borderWidth: 2 }
        ]
      }
    });
  } else {
    approvalChart.data.labels = labels;
    approvalChart.data.datasets[0].data = approvedCounts;
    approvalChart.data.datasets[1].data = overriddenCounts;
    approvalChart.update();
  }
}

// Apply filters for trends
function applyTrendFilters(e) {
  e.preventDefault();
  trendAgent = document.getElementById("trendAgent").value || "All";
  trendDays = document.getElementById("trendDays").value || 1;
  loadTrends();
}

// === Export Metrics ===
function exportMetricsCSV() {
  let url = `/metrics/export?agent=${trendAgent}&days=${trendDays}`;
  window.open(url, "_blank");
}
function exportMetricsPNG(chartId) {
  let canvas = document.getElementById(chartId);
  let link = document.createElement("a");
  link.download = chartId + ".png";
  link.href = canvas.toDataURL("image/png");
  link.click();
}

// === Auto Refresh ===
loadDecisions();
setInterval(loadDecisions, 5000);
loadPolicy();
loadHistory();
loadMetrics();
setInterval(loadMetrics, 10000);
loadTrends();
setInterval(loadTrends, 30000);
