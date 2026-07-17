// CRMIAA — Login page interactions.
// Toggles password visibility and auto-dismisses flash messages.

(function () {
    "use strict";

    // Show / hide password.
    var toggle = document.getElementById("togglePassword");
    var password = document.getElementById("password");

    if (toggle && password) {
        toggle.addEventListener("click", function () {
            var isHidden = password.type === "password";
            password.type = isHidden ? "text" : "password";
            toggle.textContent = isHidden ? "Hide" : "Show";
            toggle.setAttribute(
                "aria-label",
                isHidden ? "Hide password" : "Show password"
            );
            password.focus();
        });
    }

    // Auto-dismiss flash messages after a few seconds.
    var flashes = document.querySelectorAll(".flash");
    flashes.forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = "opacity 0.4s ease";
            flash.style.opacity = "0";
            setTimeout(function () {
                flash.remove();
            }, 400);
        }, 5000);
    });
})();
