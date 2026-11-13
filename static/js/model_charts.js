/* Charts of the /credit/models/ tabs (Chart.js).
 *
 * The data is the JSON embedded in #models-data (the same metrics that the tables show).
 * The code runs on DOMContentLoaded because Bootstrap's bundle is loaded at the end of the page.
 * Charts are drawn the first time their tab is shown, because a canvas inside a hidden tab has no size.
 * The tab ids are the model names and "comparison"; the URL fragment (#xgboost) selects the tab.
 */
function initModelTabs() {
  var dataElement = document.getElementById("models-data");
  if (!dataElement || !window.Chart || !window.bootstrap) {
    return;
  }
  var data = JSON.parse(dataElement.textContent);
  var COLORS = { logistic_regression: "#4c78a8", random_forest: "#59a14f", xgboost: "#e15759" };
  var built = {};

  function points(curve) {
    return curve.fpr.map(function (x, i) { return { x: x, y: curve.tpr[i] }; });
  }

  function rocOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      scales: {
        x: { type: "linear", min: 0, max: 1, title: { display: true, text: "False positive rate" } },
        y: { type: "linear", min: 0, max: 1, title: { display: true, text: "True positive rate" } }
      },
      plugins: { legend: { position: "bottom" } }
    };
  }

  function rocDataset(label, curve, color) {
    return { label: label, data: points(curve), borderColor: color, backgroundColor: color,
             showLine: true, pointRadius: 0, borderWidth: 2, tension: 0 };
  }

  var diagonal = {
    label: "Random classifier", data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], borderColor: "#999",
    borderDash: [6, 4], showLine: true, pointRadius: 0, borderWidth: 1
  };

  function buildModel(name) {
    var metrics = data.metrics[name];
    var roc = document.getElementById("roc-chart-" + name);
    if (roc) {
      new Chart(roc, {
        type: "scatter",
        data: { datasets: [rocDataset(metrics.display_name + " (AUC " + metrics.test.roc_auc.toFixed(3) + ")",
                                       metrics.roc_curve, COLORS[name]), diagonal] },
        options: rocOptions()
      });
    }
    var importance = document.getElementById("importance-chart-" + name);
    if (importance) {
      var items = metrics.feature_importance.slice().sort(function (a, b) { return b.importance - a.importance; });
      new Chart(importance, {
        type: "bar",
        data: {
          labels: items.map(function (item) { return item.feature; }),
          datasets: [{ label: "Share of importance", data: items.map(function (item) { return item.importance; }),
                       backgroundColor: COLORS[name] }]
        },
        options: {
          indexAxis: "y", responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { title: { display: true, text: "Share of the total importance" } } }
        }
      });
    }
  }

  function buildComparison() {
    var names = Object.keys(data.metrics);
    var roc = document.getElementById("roc-comparison");
    if (roc) {
      new Chart(roc, {
        type: "scatter",
        data: {
          datasets: names.map(function (name) {
            var m = data.metrics[name];
            return rocDataset(m.display_name + " (AUC " + m.test.roc_auc.toFixed(3) + ")", m.roc_curve, COLORS[name]);
          }).concat([diagonal])
        },
        options: rocOptions()
      });
    }
    var cv = document.getElementById("cv-metrics-chart");
    if (cv) {
      var metricNames = ["roc_auc", "recall", "precision", "f1"];
      var labels = { roc_auc: "ROC AUC", recall: "Recall", precision: "Precision", f1: "F1" };
      new Chart(cv, {
        type: "bar",
        data: {
          labels: metricNames.map(function (metric) { return labels[metric]; }),
          datasets: names.map(function (name) {
            var m = data.metrics[name];
            return { label: m.display_name, backgroundColor: COLORS[name],
                     data: metricNames.map(function (metric) { return m.cv[metric][0]; }),
                     std: metricNames.map(function (metric) { return m.cv[metric][1]; }) };
          })
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: { y: { min: 0, max: 1, title: { display: true, text: "Mean over 5 folds" } } },
          plugins: {
            tooltip: {
              callbacks: {
                label: function (context) {
                  var std = context.dataset.std[context.dataIndex];
                  return context.dataset.label + ": " + context.parsed.y.toFixed(3) + " \u00b1 " + std.toFixed(3);
                }
              }
            }
          }
        }
      });
    }
  }

  function build(paneId) {
    if (built[paneId]) {
      return;
    }
    built[paneId] = true;
    if (paneId === "comparison") {
      buildComparison();
    } else if (data.metrics[paneId]) {
      buildModel(paneId);
    }
  }

  function showTab(id) {
    var trigger = document.querySelector('#model-tabs [data-bs-target="#' + id + '"]');
    if (trigger) {
      bootstrap.Tab.getOrCreateInstance(trigger).show();
    }
  }

  document.querySelectorAll('#model-tabs [data-bs-toggle="tab"]').forEach(function (trigger) {
    trigger.addEventListener("shown.bs.tab", function (event) {
      var id = event.target.getAttribute("data-bs-target").slice(1);
      history.replaceState(null, "", "#" + id);
      build(id);
    });
  });

  // Links inside the page (comparison table, "Model Comparison" button) and the navbar menu (#xgboost).
  document.querySelectorAll("[data-tab-link]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      showTab(link.getAttribute("data-tab-link"));
    });
  });
  window.addEventListener("hashchange", function () {
    if (location.hash.length > 1) {
      showTab(location.hash.slice(1));
    }
  });

  var start = location.hash.length > 1 ? location.hash.slice(1) : data.active;
  var hasTab = document.querySelector('#model-tabs [data-bs-target="#' + start + '"]');
  if (hasTab && start !== data.active) {
    showTab(start);
  } else {
    build(data.active);
  }
}

// Bootstrap's bundle is loaded after this page content, so wait until every script has run.
document.addEventListener("DOMContentLoaded", initModelTabs);
