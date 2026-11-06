// Close the collapsed mobile menu after following an in-page link.
document.addEventListener("DOMContentLoaded", function () {
  var menu = document.getElementById("main-nav");
  if (!menu || !window.bootstrap) {
    return;
  }

  menu.querySelectorAll("a.nav-link, a.btn").forEach(function (link) {
    link.addEventListener("click", function () {
      if (menu.classList.contains("show")) {
        window.bootstrap.Collapse.getOrCreateInstance(menu).hide();
      }
    });
  });
});
