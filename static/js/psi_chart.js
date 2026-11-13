/* PSI per feature (Phase 6 of the Methodology). The data is the JSON embedded in #psi-data, the same
 * report that the table shows. Bars are colored by status and two lines mark the thresholds. */
document.addEventListener("DOMContentLoaded", function () {
  var element = document.getElementById("psi-data");
  var canvas = document.getElementById("psi-chart");
  if (!element || !canvas || !window.Chart) {
    return;
  }
  var data = JSON.parse(element.textContent);
  var names = Object.keys(data.psi);
  var colors = { stable: "#198754", watch: "#ffc107", alert: "#dc3545" };
  var line = function (label, value, color) {
    return { type: "line", label: label, data: names.map(function () { return value; }), borderColor: color,
             borderDash: [6, 4], pointRadius: 0, borderWidth: 1 };
  };
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: names,
      datasets: [
        { label: "PSI" + (data.simulated ? " (SIMULATED batch)" : ""), data: names.map(function (n) { return data.psi[n].value; }),
          backgroundColor: names.map(function (n) { return colors[data.psi[n].status]; }) },
        line("Watch from " + data.thresholds.stable, data.thresholds.stable, "#b58900"),
        line("Alert above " + data.thresholds.alert, data.thresholds.alert, "#dc3545")
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, title: { display: true, text: "PSI" } } },
      plugins: { legend: { position: "bottom" } }
    }
  });
});
