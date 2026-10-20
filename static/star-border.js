/*
 * StarBorder: a star that travels around an element's border with a
 * fading trail. Plain-JavaScript version of the React <StarBorder>
 * component; options match its props.
 *
 * `duration` is seconds per lap and `trailLength` the share of the border
 * the trail covers. With hover "lap" the star runs one quick lap when the
 * pointer arrives; clickPulse sends a ring out on click. With reduced motion
 * the star rests in place.
 *
 * @example
 * new StarBorder(document.getElementById("report-button"), {
 *    color : "#ffffff",
 *    duration : 4,
 *    trailLength : 0.3,
 *    radius : 12,
 *    hover : "lap",
 *    clickPulse : true
 * });
 */
var StarBorder;

(function () {
	var DEFAULTS = {
		color : "#ffffff",
		trailColor : "#ffffff",
		duration : 4,
		direction : "clockwise",
		stars : 1,
		trailLength : 0.3,
		thickness : 1,
		radius : 12,
		glow : 0.6,
		hover : "lap",
		sparkle : false,
		clickPulse : false,
		theme : "dark"
	};

	var SVG_NS = "http://www.w3.org/2000/svg";
	// Each trail is drawn as this many pieces, faint at the tail, bright at the head
	var TRAIL_PIECES = 14;
	// A hover lap runs this many times faster than normal
	var LAP_SPEED = 4;

	function prefersReducedMotion() {
		return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
	}

	function svg(sTag, oAttributes) {
		var el = document.createElementNS(SVG_NS, sTag);
		for (var k in oAttributes) el.setAttribute(k, oAttributes[k]);
		return el;
	}

	/**
	 * @constructor
	 * @param {HTMLElement} el element to put the border around
	 * @param {Object} vOption see DEFAULTS
	 */
	StarBorder = function (el, vOption) {
		var o = {};
		var k;

		for (k in DEFAULTS) o[k] = DEFAULTS[k];
		for (k in vOption) o[k] = vOption[k];

		this._o = o;
		this._el = el;
		this._pieces = [];
		this._heads = [];
		this._position = 0;
		this._lapBoost = 0;

		el.classList.add("star-border", "star-border--" + o.theme);
		el.style.setProperty("--sb-color", o.color);
		el.style.setProperty("--sb-radius", o.radius + "px");
		el.style.setProperty("--sb-thickness", o.thickness + "px");
		el.style.setProperty("--sb-glow", (o.glow * 10).toFixed(1) + "px");

		this._build();
		this._bind();
		this._draw();
		if (!prefersReducedMotion()) this._start();
	};

	StarBorder.prototype._build = function () {
		var o = this._o;
		var elSvg = svg("svg", { "class" : "sb-layer", "aria-hidden" : "true", focusable : "false" });
		var nPiece = o.trailLength / TRAIL_PIECES;

		for (var s = 0; s < Math.max(1, o.stars); s++) {
			for (var i = 0; i < TRAIL_PIECES; i++) {
				// pathLength 1 lets lengths and offsets be shares of the border
				var elPiece = svg("rect", {
					pathLength : 1,
					fill : "none",
					stroke : i === TRAIL_PIECES - 1 ? o.color : o.trailColor,
					"stroke-width" : o.thickness,
					"stroke-linecap" : "butt",
					"stroke-dasharray" : nPiece + " " + (1 - nPiece),
					opacity : Math.pow((i + 1) / TRAIL_PIECES, 2).toFixed(3)
				});
				elSvg.appendChild(elPiece);
				this._pieces.push({ el : elPiece, star : s, index : i });
			}
			var elHead = svg("circle", { r : o.thickness + 1, fill : o.color, "class" : "sb-star" });
			elSvg.appendChild(elHead);
			this._heads.push(elHead);
		}

		this._svg = elSvg;
		this._el.insertBefore(elSvg, this._el.firstChild);
		this._fit();
	};

	// Size the outline to the element, inset by half the stroke so it isn't clipped
	StarBorder.prototype._fit = function () {
		var o = this._o;
		var nWidth = this._el.offsetWidth;
		var nHeight = this._el.offsetHeight;
		var nInset = o.thickness / 2;
		var nRadius = Math.min(o.radius, nHeight / 2, nWidth / 2);

		this._svg.setAttribute("viewBox", "0 0 " + nWidth + " " + nHeight);
		this._shape = { x : nInset, y : nInset, w : nWidth - 2 * nInset, h : nHeight - 2 * nInset, r : Math.max(0, nRadius - nInset) };
		this._pieces.forEach(function (oPiece) {
			var s = this._shape;
			oPiece.el.setAttribute("x", s.x);
			oPiece.el.setAttribute("y", s.y);
			oPiece.el.setAttribute("width", s.w);
			oPiece.el.setAttribute("height", s.h);
			oPiece.el.setAttribute("rx", s.r);
		}, this);
		this._perimeter = this._pieces.length ? this._pieces[0].el.getTotalLength() : 0;
	};

	// Point at share t (0-1) of the way round, starting top left, going clockwise
	StarBorder.prototype._pointAt = function (t) {
		var el = this._pieces[0].el;
		var nLength = el.getTotalLength();
		var p = el.getPointAtLength(((t % 1) + 1) % 1 * nLength);
		return p;
	};

	StarBorder.prototype._draw = function () {
		var o = this._o;
		var nSign = o.direction === "counterclockwise" ? -1 : 1;
		var nPiece = o.trailLength / TRAIL_PIECES;
		var nStars = Math.max(1, o.stars);

		this._pieces.forEach(function (oPiece) {
			var nHead = this._position + oPiece.star / nStars;
			// Piece i sits (TRAIL_PIECES - 1 - i) pieces behind the head
			var nStart = nHead - (TRAIL_PIECES - oPiece.index) * nPiece * nSign;
			if (nSign < 0) nStart -= nPiece;
			oPiece.el.setAttribute("stroke-dashoffset", (-nStart).toFixed(5));
		}, this);

		this._heads.forEach(function (elHead, s) {
			var p = this._pointAt(this._position + s / nStars);
			elHead.setAttribute("cx", p.x.toFixed(2));
			elHead.setAttribute("cy", p.y.toFixed(2));
		}, this);
	};

	StarBorder.prototype._start = function () {
		var self = this;
		var o = this._o;
		var nSign = o.direction === "counterclockwise" ? -1 : 1;
		var nLast = null;

		function frame(nNow) {
			requestAnimationFrame(frame);
			if (nLast === null) nLast = nNow;
			var nStep = (nNow - nLast) / 1000 / Math.max(0.1, o.duration);
			nLast = nNow;
			// Pausing in a hidden tab can give one huge step; skip it
			if (nStep > 0.25) return;

			var nSpeed = 1;
			if (self._lapBoost > 0) {
				nSpeed = LAP_SPEED;
				self._lapBoost -= nStep * LAP_SPEED;
			}
			self._position += nStep * nSpeed * nSign;
			self._draw();
		}
		requestAnimationFrame(frame);
	};

	StarBorder.prototype._bind = function () {
		var self = this;
		var o = this._o;
		var el = this._el;

		if (typeof ResizeObserver != "undefined") {
			new ResizeObserver(function () {
				self._fit();
				self._draw();
			}).observe(el);
		}

		if (o.hover === "lap" && !prefersReducedMotion()) {
			el.addEventListener("pointerenter", function () {
				if (self._lapBoost <= 0) self._lapBoost = 1;
			});
		}

		if (o.clickPulse) {
			el.addEventListener("click", function () {
				el.classList.remove("is-pulsing");
				// Restart the pulse animation if it's already running
				void el.offsetWidth;
				el.classList.add("is-pulsing");
			});
			el.addEventListener("animationend", function (e) {
				if (e.animationName === "sb-pulse") el.classList.remove("is-pulsing");
			});
		}
	};
})();
