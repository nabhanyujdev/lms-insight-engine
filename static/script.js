const API = "";
const charts = {};
let currentPage = 1;
let totalStudents = 0;
let studentsLoaded = false;
let clusterLoaded = false;
let searchTimer;
let isAuthenticated = false;

function showPage(id, btn) {
  if (!isAuthenticated) return;
  document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  document.getElementById("page-" + id).classList.add("active");
  btn.classList.add("active");
  if (id === "students" && !studentsLoaded) loadStudents(1);
  if (id === "clusters" && !clusterLoaded) loadClusters();
}

function setAuthState(authenticated, username = "") {
  isAuthenticated = authenticated;
  document.getElementById("auth-layer").hidden = authenticated;
  document.getElementById("app-shell").hidden = !authenticated;
  document.getElementById("sidebar-user").textContent = username || "admin";
}

async function bootstrapApp() {
  const res = await fetch(API + "/api/session");
  const data = await res.json();
  setAuthState(data.authenticated, data.username);
  if (data.authenticated) {
    loadDashboard();
  }
}

async function submitLogin() {
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value.trim();
  const errorEl = document.getElementById("auth-error");
  errorEl.textContent = "";

  const res = await fetch(API + "/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  const data = await res.json();

  if (!res.ok) {
    errorEl.textContent = data.error || "Login failed";
    return;
  }

  studentsLoaded = false;
  clusterLoaded = false;
  setAuthState(true, data.username);
  loadDashboard();
}

async function logout() {
  await fetch(API + "/api/logout", { method: "POST" });
  studentsLoaded = false;
  clusterLoaded = false;
  currentPage = 1;
  document.getElementById("auth-error").textContent = "";
  document.getElementById("login-username").value = "";
  document.getElementById("login-password").value = "";
  setAuthState(false, "");
}

function scoreColor(score) {
  if (score >= 65) return "#2f6a52";
  if (score >= 45) return "#d6962d";
  return "#bf4d5d";
}

function segmentClass(level) {
  if (level === "Inactive") return "segment-low";
  if (level === "Sparsely Involved") return "segment-mid";
  return "segment-high";
}

function riskClass(probability) {
  return probability >= 50 ? "risk-high" : "risk-low";
}

function mixBar(label, value) {
  return `
    <div class="mix-line">
      <span>${label}</span>
      <div class="mix-bar"><i style="width:${value}%"></i></div>
    </div>
  `;
}

function factorMarkup(factors) {
  if (!factors || !factors.length) {
    return "<strong>No major risk flags triggered.</strong>";
  }
  return factors.join(" | ");
}

function renderBar(id, labels, data, colors, label, tooltipDetails) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label,
        data,
        backgroundColor: colors,
        borderRadius: 12,
        borderSkipped: false
      }]
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(24, 51, 42, 0.94)",
          titleColor: "#fffdf8",
          bodyColor: "#f4efe7",
          cornerRadius: 14,
          padding: 12,
          displayColors: false,
          callbacks: {
            afterBody(items) {
              if (!tooltipDetails) return [];
              return tooltipDetails(items[0]);
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#6f7c74", font: { size: 11, weight: "700" } }
        },
        y: {
          grid: { color: "rgba(31,42,36,0.08)" },
          ticks: { color: "#6f7c74", font: { size: 11 } }
        }
      }
    }
  });
}

function renderHBar(id, labels, data, colors, tooltipDetails) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderRadius: 10,
        borderSkipped: false
      }]
    },
    options: {
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(24, 51, 42, 0.94)",
          titleColor: "#fffdf8",
          bodyColor: "#f4efe7",
          cornerRadius: 14,
          padding: 12,
          displayColors: false,
          callbacks: {
            label(context) {
              return `Importance: ${context.formattedValue}%`;
            },
            afterBody(items) {
              if (!tooltipDetails) return [];
              return tooltipDetails(items[0]);
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(31,42,36,0.08)" },
          ticks: { color: "#6f7c74", font: { size: 11 } },
          title: {
            display: true,
            text: "Normalized raw-feature importance (%)",
            color: "#6f7c74",
            font: { size: 11, weight: "700" }
          }
        },
        y: {
          grid: { display: false },
          ticks: { color: "#45534b", font: { size: 11, weight: "700" } }
        }
      }
    }
  });
}

function renderDoughnut(id, labels, data, colors, tooltipDetails) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type: "pie",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderColor: "#fff9f1",
        borderWidth: 4
      }]
    },
    options: {
      plugins: {
        tooltip: {
          backgroundColor: "rgba(24, 51, 42, 0.94)",
          titleColor: "#fffdf8",
          bodyColor: "#f4efe7",
          cornerRadius: 14,
          padding: 12,
          displayColors: false,
          callbacks: {
            label(context) {
              return `Students: ${context.formattedValue}`;
            },
            afterBody(items) {
              if (!tooltipDetails) return [];
              return tooltipDetails(items[0]);
            }
          }
        },
        legend: {
          position: "bottom",
          labels: { color: "#45534b", font: { size: 12, weight: "700" }, padding: 18 }
        }
      }
    }
  });
}

function updateSignal(idPrefix, value) {
  document.getElementById(`${idPrefix}-fill`).style.width = `${value}%`;
  document.getElementById(`${idPrefix}-val`).textContent = `${value}%`;
}

function niceName(key) {
  return {
    login_frequency: "Login Frequency",
    time_spent_modules: "Time Spent Modules",
    participation_forums: "Participation Forums",
    quiz_performance_average: "Quiz Performance Average",
    assignment_submissions: "Assignment Submissions",
    resource_access_frequency: "Resource Access Frequency",
    session_duration_average: "Session Duration Average"
  }[key] || key;
}

async function loadDashboard() {
  const data = await fetch(API + "/api/dashboard").then((response) => response.json());
  document.getElementById("kpi-total").textContent = data.total_students;
  document.getElementById("kpi-risk").textContent = data.at_risk;
  document.getElementById("kpi-risk-pct").textContent = `${((data.at_risk / data.total_students) * 100).toFixed(1)}% of students currently fall in the derived risk band.`;
  document.getElementById("kpi-eng").textContent = `${data.avg_engagement}%`;
  document.getElementById("kpi-device").textContent = data.top_device;

  updateSignal("avg-activity", data.avg_activity);
  updateSignal("avg-participation", data.avg_participation);
  updateSignal("avg-performance", data.avg_performance);
  document.getElementById("hero-note").textContent =
    `Average activity is ${data.avg_activity}%, participation is ${data.avg_participation}%, and performance is ${data.avg_performance}%.`;

  renderBar(
    "engChart",
    Object.keys(data.engagement_level_dist),
    Object.values(data.engagement_level_dist),
    ["#bf4d5d", "#d6962d", "#2f6a52"],
    "Students",
    (item) => {
      const share = ((item.raw / data.total_students) * 100).toFixed(1);
      return [`Share of cohort: ${share}%`];
    }
  );

  renderDoughnut(
    "riskPieChart",
    ["Safe", "At Risk"],
    [data.total_students - data.at_risk, data.at_risk],
    ["#2f6a52", "#bf4d5d"],
    (item) => {
      const share = ((item.raw / data.total_students) * 100).toFixed(1);
      return [`Share of cohort: ${share}%`];
    }
  );

  const fiSorted = Object.entries(data.raw_feature_importance).sort((a, b) => b[1] - a[1]);
  renderHBar(
    "fiChart",
    fiSorted.map((entry) => niceName(entry[0])),
    fiSorted.map((entry) => entry[1]),
    fiSorted.map((entry, index) => ["#2f6a52", "#2a8c82", "#d6962d", "#d96f45", "#bf4d5d", "#537964", "#9c6a12"][index]),
    (item) => [`This normalized view shows only the raw LMS input features used in the project.`]
  );

  const top = await fetch(API + "/api/top_at_risk").then((response) => response.json());
  document.getElementById("top-risk-list").innerHTML = top.map((student) => `
    <div class="risk-row">
      <div>
        <div class="risk-id">${student.student_id}</div>
        <div class="risk-meta">${student.course_id} · ${student.engagement_level}</div>
      </div>
      <div class="risk-prob-bar">
        <div class="mini-bar-bg"><div class="mini-bar-fill" style="width:${student.risk_probability}%"></div></div>
      </div>
      <div class="risk-prob">${student.risk_probability}%</div>
    </div>
  `).join("");
}

function debounceLoad() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadStudents(1), 350);
}

async function loadStudents(page) {
  studentsLoaded = true;
  currentPage = page;
  const search = document.getElementById("search-input").value;
  const risk = document.getElementById("risk-filter").value;
  const level = document.getElementById("level-filter").value;
  const tbody = document.getElementById("student-table-body");
  tbody.innerHTML = `<tr><td colspan="6" style="padding:36px 0;color:var(--muted)"><div class="loader"></div></td></tr>`;

  const res = await fetch(`${API}/api/students?page=${page}&per_page=15&search=${encodeURIComponent(search)}&risk=${risk}&level=${level}`).then((response) => response.json());
  totalStudents = res.total;

  tbody.innerHTML = res.students.map((student) => `
    <tr>
      <td><div class="cell-strong">${student.student_id}</div></td>
      <td><div class="cell-strong">${student.course_id}</div></td>
      <td>
        <div class="signal-mix">
          ${mixBar("Activity", student.activity_score)}
          ${mixBar("Participation", student.participation_score)}
          ${mixBar("Performance", student.performance_score)}
        </div>
      </td>
      <td>
        <div class="engagement-cell">${student.engagement_score}%</div>
        <div class="engagement-caption">Final engagement</div>
      </td>
      <td><span class="pill ${segmentClass(student.final_segment)}">${student.final_segment}</span></td>
      <td><span class="risk-badge ${riskClass(student.risk_probability)}">${student.risk_probability}% predicted risk</span></td>
    </tr>
  `).join("") || `<tr><td colspan="6" style="padding:28px 0;color:var(--muted)">No students found</td></tr>`;

  const start = totalStudents === 0 ? 0 : (page - 1) * 15 + 1;
  const end = Math.min(page * 15, totalStudents);
  document.getElementById("pag-info").textContent = `Showing ${start}-${end} of ${totalStudents} students`;
  document.getElementById("btn-prev").disabled = page <= 1;
  document.getElementById("btn-next").disabled = end >= totalStudents;
}

function changePage(delta) {
  loadStudents(currentPage + delta);
}

async function loadClusters() {
  clusterLoaded = true;
  const data = await fetch(API + "/api/clusters").then((response) => response.json());
  document.getElementById("pca-variance-label").textContent =
    `PC1 explains ${data.variance_explained[0]}% and PC2 explains ${data.variance_explained[1]}% of the variance in the three derived engagement features.`;

  const colorMap = {
    "Inactive": "#bf4d5d",
    "Sparsely Involved": "#d6962d",
    "Actively Involved": "#2f6a52"
  };

  const groups = {};
  data.points.forEach((point) => {
    if (!groups[point.segment_label]) groups[point.segment_label] = [];
    groups[point.segment_label].push(point);
  });

  const datasets = Object.entries(groups).map(([label, values]) => ({
    label,
    data: values.map((point) => ({ x: point.x, y: point.y })),
    rawPoints: values,
    backgroundColor: colorMap[label] + "cc",
    borderColor: colorMap[label],
    borderWidth: 1.5,
    pointRadius: 5,
    pointHoverRadius: 8
  }));

  if (charts.scatterChart) charts.scatterChart.destroy();
  charts.scatterChart = new Chart(document.getElementById("scatterChart"), {
    type: "scatter",
    data: { datasets },
    options: {
      plugins: {
        tooltip: {
          backgroundColor: "rgba(24, 51, 42, 0.94)",
          titleColor: "#fffdf8",
          bodyColor: "#f4efe7",
          cornerRadius: 14,
          padding: 12,
          callbacks: {
            title(items) {
              const point = items[0].dataset.rawPoints[items[0].dataIndex];
              return `${point.student_id} · ${point.course_id}`;
            },
            label(context) {
              const point = context.dataset.rawPoints[context.dataIndex];
              return [
                `Final segment: ${point.segment_label}`,
                `Engagement score: ${point.engagement_score}%`,
                `PC1: ${point.x}, PC2: ${point.y}`
              ];
            }
          }
        },
        legend: {
          position: "top",
          labels: { color: "#45534b", font: { size: 12, weight: "700" }, padding: 22, usePointStyle: true }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(31,42,36,0.08)" },
          ticks: { color: "#6f7c74" },
          title: { display: true, text: "Principal Component 1", color: "#6f7c74", font: { weight: "700" } }
        },
        y: {
          grid: { color: "rgba(31,42,36,0.08)" },
          ticks: { color: "#6f7c74" },
          title: { display: true, text: "Principal Component 2", color: "#6f7c74", font: { weight: "700" } }
        }
      }
    }
  });
}

async function runPredict() {
  const payload = {
    login_frequency: document.getElementById("p-login").value,
    time_spent_modules: document.getElementById("p-time").value,
    participation_forums: document.getElementById("p-forum").value,
    quiz_performance_average: document.getElementById("p-quiz").value,
    assignment_submissions: document.getElementById("p-assign").value,
    resource_access_frequency: document.getElementById("p-resource").value,
    session_duration_average: document.getElementById("p-session").value
  };

  document.getElementById("result-panel").innerHTML = `
    <article class="card result-card" style="place-items:center">
      <div class="loader"></div>
      <div style="color:var(--muted)">Running score and risk analysis...</div>
    </article>`;

  const res = await fetch(API + "/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then((response) => response.json());

  if (res.error) {
    document.getElementById("result-panel").innerHTML = `
      <article class="card result-card">
        <div class="card-title">Prediction error</div>
        <div class="tip-box">${res.error}</div>
      </article>`;
    return;
  }

  const prob = res.avg_risk_probability;
  const color = prob >= 65 ? "#bf4d5d" : prob >= 40 ? "#d6962d" : "#2f6a52";
  const title = prob >= 65 ? "High intervention priority" : prob >= 40 ? "Moderate intervention priority" : "Low intervention priority";

  document.getElementById("result-panel").innerHTML = `
    <article class="card result-card">
      <div class="gauge-wrap">
        <div class="gauge-ring" style="--g-color:${color};--g-pct:${prob}%">
          <div class="gauge-inner">
            <div>
              <div class="gauge-value" style="color:${color}">${prob}%</div>
              <div class="gauge-caption">Average risk</div>
            </div>
          </div>
        </div>
        <div>
          <div class="result-title" style="color:${color}">${title}</div>
          <p class="result-copy">This prediction combines the model outputs with the weighted engagement and risk-scoring logic.</p>
          <div style="margin-top:14px">
            <span class="pill ${segmentClass(res.engagement_level)}">${res.engagement_level}</span>
          </div>
        </div>
      </div>

      <div class="result-grid">
        <div class="result-stat">
          <span>Activity score</span>
          <strong>${res.activity_score}%</strong>
        </div>
        <div class="result-stat">
          <span>Participation score</span>
          <strong>${res.participation_score}%</strong>
        </div>
        <div class="result-stat">
          <span>Performance score</span>
          <strong>${res.performance_score}%</strong>
        </div>
        <div class="result-stat">
          <span>Engagement score</span>
          <strong>${res.engagement_score}%</strong>
          <div class="result-detail">0.35 x Activity + 0.20 x Participation + 0.45 x Performance</div>
        </div>
        <div class="result-stat">
          <span>Derived risk score</span>
          <strong>${res.risk_score}%</strong>
          <div class="result-detail">(100 - Engagement Score) + penalties if triggered</div>
        </div>
        <div class="result-stat">
          <span>Model comparison</span>
          <strong>RF ${res.rf_risk_probability}% V/s LR ${res.lr_risk_probability}%</strong>
          <div class="result-detail">RF = Random Forest, LR = Logistic Regression</div>
        </div>
      </div>

      <div class="info-panel">
        <h4>Risk factors and penalties</h4>
        <p>${factorMarkup(res.risk_factors)}</p>
        <ul>
          <li>+8 if assignment submissions fall below the lower threshold</li>
          <li>+6 if quiz performance falls below the lower threshold</li>
          <li>+4 if resource access frequency falls below the lower threshold</li>
        </ul>
      </div>

      <div class="tip-box"><strong>TIP: 💡</strong> ${res.recommendation}</div>
    </article>`;
}

document.getElementById("login-password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitLogin();
});

document.getElementById("login-username").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitLogin();
});

bootstrapApp();