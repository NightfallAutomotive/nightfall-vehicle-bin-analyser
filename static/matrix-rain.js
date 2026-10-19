/*
 * Matrix-style rain of hex digits behind the page.
 * Decoration only: draws on a fixed canvas, pauses while the tab is hidden,
 * and shows a single still frame when the viewer prefers reduced motion.
 *
 * @example
 * new MatrixRain(document.getElementById("matrix-rain"));
 */
var MatrixRain;

(function () {
	var GLYPHS = "0123456789ABCDEF";
	var FONT_SIZE = 16;
	var FRAME_MS = 55;
	var TRAIL_FADE = 0.09;
	var HEAD_COLOR = "#88c0d0";
	var TRAIL_COLOR = "#a3be8c";

	function prefersReducedMotion() {
		return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
	}

	function randomGlyph() {
		return GLYPHS.charAt(Math.floor(Math.random() * GLYPHS.length));
	}

	/**
	 * @constructor
	 * @param {HTMLCanvasElement} elCanvas fixed, full-viewport canvas
	 */
	MatrixRain = function (elCanvas) {
		var self = this;

		this._canvas = elCanvas;
		this._ctx = elCanvas.getContext("2d");
		this._drops = [];
		this._timer = 0;
		this._last = 0;

		if (!this._ctx) return;

		this._resize();
		window.addEventListener("resize", function () { self._resize(); });
		document.addEventListener("visibilitychange", function () {
			if (document.hidden) self._stop();
			else self._start();
		});

		if (prefersReducedMotion()) this._still();
		else this._start();
	};

	MatrixRain.prototype._resize = function () {
		var nRatio = Math.min(window.devicePixelRatio || 1, 2);
		var nWidth = window.innerWidth;
		var nHeight = window.innerHeight;
		var nColumns = Math.ceil(nWidth / FONT_SIZE);
		var nRows = Math.ceil(nHeight / FONT_SIZE);

		this._canvas.width = Math.round(nWidth * nRatio);
		this._canvas.height = Math.round(nHeight * nRatio);
		this._ctx.setTransform(nRatio, 0, 0, nRatio, 0, 0);
		this._ctx.font = "600 " + FONT_SIZE + "px ui-monospace, \"SFMono-Regular\", Menlo, Consolas, monospace";
		this._ctx.textBaseline = "top";
		this._width = nWidth;
		this._height = nHeight;
		this._rows = nRows;

		// Keep existing columns where they are, and start new ones at a random height
		while (this._drops.length < nColumns) {
			this._drops.push({ y : -Math.floor(Math.random() * nRows), speed : 0.5 + Math.random() * 0.7 });
		}
		this._drops.length = nColumns;

		if (prefersReducedMotion()) this._still();
	};

	MatrixRain.prototype._start = function () {
		var self = this;
		if (this._timer || prefersReducedMotion()) return;

		function frame(nNow) {
			self._timer = requestAnimationFrame(frame);
			if (nNow - self._last < FRAME_MS) return;
			self._last = nNow;
			self._step();
		}

		this._timer = requestAnimationFrame(frame);
	};

	MatrixRain.prototype._stop = function () {
		cancelAnimationFrame(this._timer);
		this._timer = 0;
	};

	// Fade what is already drawn towards transparent, so the page background shows through
	MatrixRain.prototype._fade = function (nAmount) {
		var ctx = this._ctx;
		ctx.globalCompositeOperation = "destination-out";
		ctx.fillStyle = "rgba(0, 0, 0, " + nAmount + ")";
		ctx.fillRect(0, 0, this._width, this._height);
		ctx.globalCompositeOperation = "source-over";
	};

	MatrixRain.prototype._step = function () {
		var ctx = this._ctx;
		var nRows = this._rows;

		this._fade(TRAIL_FADE);

		this._drops.forEach(function (oDrop, i) {
			var nRow = Math.floor(oDrop.y);
			if (nRow >= 0) {
				var nX = i * FONT_SIZE;
				var nY = nRow * FONT_SIZE;

				// Clear both cells first so new glyphs never smear over fading ones,
				// then repaint the cell above as trail and the bright head below it
				ctx.clearRect(nX, nY - FONT_SIZE, FONT_SIZE, FONT_SIZE * 2);
				ctx.fillStyle = TRAIL_COLOR;
				ctx.fillText(randomGlyph(), nX, nY - FONT_SIZE);
				ctx.fillStyle = HEAD_COLOR;
				ctx.fillText(randomGlyph(), nX, nY);
			}

			oDrop.y += oDrop.speed;
			if (nRow > nRows && Math.random() > 0.975) {
				oDrop.y = -Math.floor(Math.random() * 20);
				oDrop.speed = 0.5 + Math.random() * 0.7;
			}
		});
	};

	// Reduced motion: one frame of scattered columns, no animation
	MatrixRain.prototype._still = function () {
		var ctx = this._ctx;
		var nRows = this._rows;

		ctx.clearRect(0, 0, this._width, this._height);
		this._drops.forEach(function (oDrop, i) {
			var nHead = Math.floor(Math.random() * nRows * 1.4);
			var nLength = 6 + Math.floor(Math.random() * 14);
			for (var k = 0; k < nLength; k++) {
				var nRow = nHead - k;
				if (nRow < 0 || nRow > nRows) continue;
				ctx.globalAlpha = Math.max(0.05, 1 - k / nLength);
				ctx.fillStyle = k === 0 ? HEAD_COLOR : TRAIL_COLOR;
				ctx.fillText(randomGlyph(), i * FONT_SIZE, nRow * FONT_SIZE);
			}
		});
		ctx.globalAlpha = 1;
	};
})();
