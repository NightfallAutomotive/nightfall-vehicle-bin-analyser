/*
 * Light/dark switch (as on Nightfall Tools, RemapData and Statement Bridge): follows the device until
 * clicked. The choice lasts until the tab is closed; it isn't saved, because this page stores nothing.
 * Needs <button id="theme"> holding a .sun and a .moon icon, and <meta name="theme-color">.
 */
(function () {
	var root = document.documentElement;
	var sysLight = matchMedia("(prefers-color-scheme: light)");
	var themeMeta = document.querySelector('meta[name="theme-color"]');
	var button = document.getElementById("theme");
	if (!button) return;

	var mode = function () { return root.getAttribute("data-theme") || (sysLight.matches ? "light" : "dark"); };

	function showMode() {
		var m = mode();
		root.setAttribute("data-mode", m);
		button.setAttribute("aria-label", m === "light" ? "Switch to dark mode" : "Switch to light mode");
		if (themeMeta) themeMeta.setAttribute("content", m === "light" ? "#e5e9f0" : "#20242d");
	}

	button.addEventListener("click", function () {
		var next = mode() === "light" ? "dark" : "light";
		var apply = function () { root.setAttribute("data-theme", next); showMode(); };
		// with Reduce Motion (or without view transitions) the colours just ease across
		if (matchMedia("(prefers-reduced-motion: reduce)").matches || !document.startViewTransition) {
			root.classList.add("theming");
			setTimeout(function () { root.classList.remove("theming"); }, 400);
			apply();
			return;
		}
		// the new mode spreads out in a circle from the button, to the far corner of the screen
		var r = button.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
		var far = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
		document.startViewTransition(apply).ready.then(function () {
			root.animate({ clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + far + "px at " + x + "px " + y + "px)"] },
				{ duration: 900, easing: "cubic-bezier(.23, 1, .32, 1)", pseudoElement: "::view-transition-new(root)" });
		}).catch(function () {});
	});

	if (sysLight.addEventListener) sysLight.addEventListener("change", showMode);
	showMode();
})();
