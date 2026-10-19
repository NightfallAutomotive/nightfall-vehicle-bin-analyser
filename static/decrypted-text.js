/*
 * DecryptedText, from React Bits (reactbits.dev).
 * Plain-JavaScript port of the React component. Options match its props;
 * the text comes from the element itself, and one level of inline child
 * elements (like <span>) keeps its own styling.
 *
 * @example
 * new DecryptedText(document.getElementById("page-title"), {
 *    animateOn : "inViewHover",
 *    sequential : true,
 *    hoverRadius : 100
 * });
 */
var DecryptedText;

(function () {
	var FADE_FLOOR = 0.16;
	var FADE_PEAK = 0.62;
	var FADE_LEAD = 6;
	var SETTLE = "color 0.7s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.6s cubic-bezier(0.22, 1, 0.36, 1)";

	var DEFAULTS = {
		speed : 50,
		maxIterations : 10,
		sequential : false,
		revealDirection : "start",
		useOriginalCharsOnly : false,
		characters : "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()_+",
		className : "",
		encryptedClassName : "",
		animateOn : "hover",
		clickMode : "once",
		effect : "scramble",
		scrambleColor : "",
		loop : false,
		loopDelay : 2000,
		hoverRadius : 0
	};

	var glyphWidths = {};
	var measureContext = null;

	function isSpace(sChar) {
		return /\s/.test(sChar);
	}

	function prefersReducedMotion() {
		return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
	}

	function readFont(el) {
		var oStyle = window.getComputedStyle(el);
		return {
			font : oStyle.fontStyle + " " + oStyle.fontWeight + " " + oStyle.fontSize + " " + oStyle.fontFamily,
			spacing : parseFloat(oStyle.letterSpacing) || 0
		};
	}

	function advance(sFont, sGlyph) {
		var oWidths = glyphWidths[sFont] || (glyphWidths[sFont] = {});

		if (oWidths[sGlyph] === undefined) {
			measureContext = measureContext || document.createElement("canvas").getContext("2d");
			if (!measureContext) return 0;
			measureContext.font = sFont;
			oWidths[sGlyph] = measureContext.measureText(sGlyph).width;
		}

		return oWidths[sGlyph];
	}

	function flipFrames(nAngle, nOpacity) {
		return [
			{ transform : "perspective(4em) translateZ(-0.42em) rotateX(" + nAngle + "deg) translateZ(0.42em)", opacity : nOpacity },
			{ transform : "perspective(4em) translateZ(-0.42em) rotateX(0deg) translateZ(0.42em)", opacity : 1 }
		];
	}

	function fill(nLength, fn) {
		var aOut = [];
		for (var i = 0; i < nLength; i++) aOut.push(fn(i));
		return aOut;
	}

	/**
	 * @constructor
	 * @param {HTMLElement} el element whose text is animated
	 * @param {Object} vOption see DEFAULTS
	 */
	DecryptedText = function (el, vOption) {
		var o = {};
		var k;

		for (k in DEFAULTS) o[k] = DEFAULTS[k];
		for (k in vOption) o[k] = vOption[k];

		this._o = o;
		this._el = el;
		this._step = Math.max(16, o.speed);
		this._local = (o.animateOn === "hover" || o.animateOn === "inViewHover") && o.hoverRadius > 0;
		this._run = null;
		this._timer = 0;
		this._hold = 0;
		this._pending = null;
		this._visible = true;
		this._played = false;
		this._pointer = null;
		this._warm = false;
		this._font = null;
		this._centers = [];

		this._build();

		var aChars = this._chars;
		var aLetters = aChars.filter(function (c) { return !isSpace(c); });
		var aSource = o.useOriginalCharsOnly ? aLetters.filter(function (c, i) { return aLetters.indexOf(c) === i; }) : Array.from(o.characters);
		this._pool = aSource.length ? aSource : aLetters;

		var bHidden = o.animateOn === "click" || ((o.animateOn === "view" || o.animateOn === "inViewHover") && !prefersReducedMotion());
		this._target = !bHidden;
		this._mask = aChars.map(function (c) { return !bHidden || isSpace(c); });
		this._heat = fill(aChars.length, function () { return 0; });
		this._frame = null;

		this._paint();
		this._bind();
	};

	// Split the element into one cell per character, keeping inline child elements
	DecryptedText.prototype._build = function () {
		var el = this._el;
		var aChars = [];
		var aCells = [];
		var aSegments = [];
		var elSR = document.createElement("span");
		var elVisual = document.createElement("span");

		Array.prototype.forEach.call(el.childNodes, function (node) {
			if (node.nodeType === 3) {
				aSegments.push({ text : node.textContent, wrap : null });
			} else if (node.nodeType === 1) {
				aSegments.push({ text : node.textContent, wrap : node.cloneNode(false) });
			}
		});

		aSegments.forEach(function (oSegment) {
			var elTarget = oSegment.wrap || elVisual;
			var elWord = null;

			if (oSegment.wrap) elVisual.appendChild(oSegment.wrap);

			Array.from(oSegment.text).forEach(function (sChar) {
				var nIndex = aChars.length;
				aChars.push(sChar);

				if (isSpace(sChar)) {
					elTarget.appendChild(document.createTextNode(sChar));
					elWord = null;
					aCells.push(null);
					return;
				}

				if (!elWord) {
					elWord = document.createElement("span");
					elWord.style.whiteSpace = "nowrap";
					elTarget.appendChild(elWord);
				}

				var elCell = document.createElement("span");
				var elGhost = document.createElement("span");
				var elGlyph = document.createElement("span");

				elCell.style.position = "relative";
				elCell.style.display = "inline-block";
				elGhost.textContent = sChar;
				elGlyph.style.position = "absolute";
				elGlyph.style.top = "0";
				elGlyph.style.left = "50%";
				elGlyph.style.transform = "translateX(-50%)";
				elGlyph.hidden = true;
				elCell.appendChild(elGhost);
				elCell.appendChild(elGlyph);
				elWord.appendChild(elCell);
				aCells[nIndex] = { cell : elCell, ghost : elGhost, glyph : elGlyph };
			});
		});

		elSR.textContent = aChars.join("");
		elSR.style.cssText = "position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0";
		elVisual.setAttribute("aria-hidden", "true");

		el.textContent = "";
		el.appendChild(elSR);
		el.appendChild(elVisual);

		this._chars = aChars;
		this._cells = aCells;
	};

	DecryptedText.prototype._bind = function () {
		var self = this;
		var o = this._o;
		var el = this._el;
		var bHoverable = o.animateOn === "hover" || o.animateOn === "inViewHover";
		var bViewTrigger = o.animateOn === "view" || o.animateOn === "inViewHover";

		if (bHoverable) {
			el.addEventListener("mouseenter", function (e) { self._onEnter(e); });
			el.addEventListener("mousemove", function (e) { if (self._local) self._trackPointer(e); });
			el.addEventListener("mouseleave", function () { self._onLeave(); });
		} else if (o.animateOn === "click") {
			el.addEventListener("click", function () {
				if (o.clickMode === "toggle") {
					self._startRun(!self._target);
				} else if (!self._target) {
					self._startRun(true);
				}
			});
		}

		if (typeof ResizeObserver != "undefined") {
			new ResizeObserver(function () {
				var oMetrics = readFont(el);
				delete glyphWidths[oMetrics.font];
				self._font = oMetrics;
				self._paint(true);
			}).observe(el);
		}

		if ((bViewTrigger || o.loop) && typeof IntersectionObserver != "undefined") {
			var oObserver = new IntersectionObserver(function (aEntries) {
				var bVisible = aEntries.some(function (oEntry) { return oEntry.isIntersecting; });
				self._visible = bVisible;
				if (!bVisible) return;
				if (bViewTrigger && !self._played) {
					self._played = true;
					self._startRun(true);
				}
				var fnResume = self._pending;
				self._pending = null;
				if (fnResume) fnResume();
				if (!o.loop) oObserver.disconnect();
			}, { threshold : 0.1 });
			oObserver.observe(el);
		}
	};

	DecryptedText.prototype._revealOrder = function () {
		var o = this._o;
		var aChars = this._chars;
		var aOrder = [];

		aChars.forEach(function (c, i) { if (!isSpace(c)) aOrder.push(i); });
		if (o.revealDirection === "end") return aOrder.reverse();
		if (o.revealDirection === "center") {
			var nMiddle = Math.floor(aChars.length / 2);
			return aOrder.sort(function (a, b) { return Math.abs(a - nMiddle) - Math.abs(b - nMiddle); });
		}
		if (o.revealDirection === "random") {
			for (var i = aOrder.length - 1; i > 0; i--) {
				var j = Math.floor(Math.random() * (i + 1));
				var t = aOrder[i]; aOrder[i] = aOrder[j]; aOrder[j] = t;
			}
		}
		return aOrder;
	};

	// Squeeze a scrambled glyph that is wider than the real letter, so the line never shifts
	DecryptedText.prototype._fit = function (nIndex, sGlyph) {
		if (!this._font) this._font = readFont(this._el);
		var oMetrics = this._font;
		var nRoom = advance(oMetrics.font, this._chars[nIndex]) + oMetrics.spacing;
		var nNeed = advance(oMetrics.font, sGlyph) + oMetrics.spacing;
		return nNeed > nRoom + 0.01 ? Math.round(Math.max(0.05, nRoom / nNeed) * 1000) / 1000 : 1;
	};

	/**
	 * Work out the next frame and write it to the DOM
	 *
	 * @private
	 * @param {Boolean} [bRefitOnly] keep the current glyphs, only re-measure them
	 */
	DecryptedText.prototype._paint = function (bRefitOnly) {
		var self = this;
		var o = this._o;
		var aChars = this._chars;
		var aMask = this._mask;
		var aHeat = this._heat;
		var oRun = this._run;
		var aPool = this._pool;
		var oPrevious = this._frame;
		var oRanks = null;
		var nRamp = oRun && oRun.forward && !o.sequential ? Math.min(1, oRun.iteration / Math.max(1, o.maxIterations)) : 0;
		var oNext = { shown : [], revealed : [], tint : [], dim : [], squeeze : [] };

		if (bRefitOnly && oPrevious) {
			oNext = oPrevious;
			oNext.squeeze = oNext.shown.map(function (g, i) { return oNext.revealed[i] ? 1 : self._fit(i, g); });
		} else {
			if (oRun && oRun.forward && o.sequential) {
				oRanks = {};
				oRun.queue.forEach(function (nIndex, nRank) { if (nIndex !== null) oRanks[nIndex] = nRank; });
			}

			aChars.forEach(function (sChar, i) {
				var bBlank = isSpace(sChar);
				var nHot = bBlank ? 0 : aHeat[i] || 0;
				var bHidden = !bBlank && !aMask[i];
				var bScrambled = bHidden || (nHot > 0 && Math.random() < nHot * 2);
				var sGlyph = bScrambled ? aPool[Math.floor(Math.random() * aPool.length)] : sChar;

				oNext.revealed.push(!bScrambled);
				oNext.shown.push(sGlyph);
				oNext.squeeze.push(bScrambled ? self._fit(i, sGlyph) : 1);

				if (!bScrambled) {
					oNext.tint.push(0);
					oNext.dim.push(1);
				} else if (!bHidden) {
					var nLevel = Math.min(1, nHot * 1.5);
					oNext.tint.push(nLevel);
					oNext.dim.push(1 - (1 - FADE_FLOOR) * nLevel);
				} else {
					var nRank = oRanks ? oRanks[i] : undefined;
					var nLift = nRank === undefined ? nRamp : Math.max(0, 1 - nRank / FADE_LEAD);
					oNext.tint.push(1);
					oNext.dim.push(FADE_FLOOR + (FADE_PEAK - FADE_FLOOR) * nLift);
				}
			});
		}

		this._frame = oNext;
		this._render(oPrevious, oNext);
	};

	DecryptedText.prototype._render = function (oPrevious, oFrame) {
		var o = this._o;
		var nStep = this._step;
		var bTinted = !!o.scrambleColor;
		var bFading = o.effect === "fade";
		var bFlipping = o.effect === "flip" && !prefersReducedMotion();
		var bSettles = bTinted || bFading;

		this._cells.forEach(function (oCell, i) {
			if (!oCell) return;

			var bRevealed = oFrame.revealed[i];
			var oStyle = oCell.cell.style;

			oCell.cell.className = bRevealed ? o.className : o.encryptedClassName;
			oCell.ghost.style.visibility = bRevealed ? "" : "hidden";
			oCell.glyph.hidden = bRevealed;

			if (!bRevealed) {
				var nSqueeze = oFrame.squeeze[i];
				oCell.glyph.textContent = oFrame.shown[i];
				oCell.glyph.style.transform = nSqueeze < 1 ? "translateX(-50%) scaleX(" + nSqueeze + ")" : "translateX(-50%)";
			}

			if (bSettles) oStyle.transition = bRevealed ? SETTLE : "color 0.12s linear, opacity " + nStep + "ms linear";

			if (bTinted && !bRevealed) {
				var nAmount = Math.round(oFrame.tint[i] * 100);
				oStyle.color = nAmount >= 100 ? o.scrambleColor : "color-mix(in srgb, " + o.scrambleColor + " " + nAmount + "%, currentColor)";
			} else {
				oStyle.color = "";
			}

			if (bFading) oStyle.opacity = bRevealed ? 1 : oFrame.dim[i];

			if (bFlipping && oPrevious && typeof oCell.cell.animate == "function") {
				if (!bRevealed) {
					oCell.cell.animate(flipFrames(58 + Math.random() * 26, 0.3), {
						duration : Math.min(nStep * 0.92, 240),
						easing : "cubic-bezier(0.3, 0.7, 0.4, 1)"
					});
				} else if (oPrevious.revealed[i] === false) {
					oCell.cell.animate(flipFrames(90, 0), {
						duration : Math.min(Math.max(nStep * 7, 360), 760),
						easing : "cubic-bezier(0.34, 1.45, 0.64, 1)"
					});
				}
			}
		});
	};

	DecryptedText.prototype._stopTicker = function () {
		clearInterval(this._timer);
		this._timer = 0;
	};

	DecryptedText.prototype._ensureTicker = function () {
		var self = this;
		if (this._timer) return;
		this._timer = setInterval(function () { self._tick(); }, this._step);
	};

	DecryptedText.prototype._stopRun = function () {
		this._run = null;
		clearTimeout(this._hold);
		this._hold = 0;
		this._pending = null;
	};

	DecryptedText.prototype._schedule = function (fnTask, nDelay) {
		var self = this;
		clearTimeout(this._hold);
		this._hold = setTimeout(function () {
			self._hold = 0;
			if (self._visible) fnTask();
			else self._pending = fnTask;
		}, nDelay);
	};

	DecryptedText.prototype._startRun = function (bForward, oOptions) {
		var o = this._o;
		var aChars = this._chars;
		oOptions = oOptions || {};

		this._stopRun();
		this._target = bForward;
		if (oOptions.from) this._mask = oOptions.from;

		if (prefersReducedMotion()) {
			this._mask = aChars.map(function (c) { return bForward || isSpace(c); });
			this._paint();
			return;
		}

		var aMask = this._mask;
		var aOrder = bForward ? this._revealOrder() : this._revealOrder().reverse();
		var aQueue = o.sequential ? aOrder.filter(function (i) { return aMask[i] !== bForward; }) : [];

		this._run = {
			forward : bForward,
			cycle : !!oOptions.cycle,
			iteration : 0,
			queue : fill(oOptions.lead || 0, function () { return null; }).concat(aQueue)
		};
		this._paint();
		this._ensureTicker();
	};

	DecryptedText.prototype._finishRun = function (oRun) {
		var self = this;
		var o = this._o;

		if (!o.loop) return;
		if (oRun.forward) {
			this._schedule(function () { self._startRun(false, { cycle : true }); }, Math.max(0, o.loopDelay));
		} else if (oRun.cycle) {
			this._startRun(true, { cycle : true, lead : o.sequential ? Math.max(2, Math.round(320 / this._step)) : 0 });
		}
	};

	// Heat letters near the pointer so they scramble, and let them cool down after it leaves
	DecryptedText.prototype._warmUp = function () {
		var self = this;
		var o = this._o;
		var aHeat = this._heat;
		var oPointer = this._pointer;
		var oBox = oPointer ? this._el.getBoundingClientRect() : null;
		var nCool = 1 / Math.max(1, o.maxIterations);
		var bActive = false;

		this._chars.forEach(function (sChar, i) {
			if (isSpace(sChar)) return;
			var nTarget = 0;
			var oCenter = self._centers[i];
			if (oBox && oCenter && oPointer) {
				var nDistance = Math.hypot(oBox.left + oCenter.x - oPointer.x, oBox.top + oCenter.y - oPointer.y) / Math.max(1, o.hoverRadius);
				if (nDistance < 1) nTarget = 1 - nDistance * nDistance * (3 - 2 * nDistance);
			}
			var nValue = Math.max((aHeat[i] || 0) - nCool, nTarget);
			aHeat[i] = nValue > 0.001 ? nValue : 0;
			if (aHeat[i] > 0) bActive = true;
		});

		this._warm = bActive;
	};

	DecryptedText.prototype._tick = function () {
		var o = this._o;
		var aChars = this._chars;
		var oRun = this._run;

		if (oRun) {
			oRun.iteration += 1;
			var aMask = this._mask;
			var bDone;

			if (o.sequential) {
				var nIndex = oRun.queue.shift();
				if (nIndex !== undefined && nIndex !== null) {
					aMask = aMask.slice();
					aMask[nIndex] = oRun.forward;
				}
				bDone = oRun.queue.length === 0;
			} else if (oRun.forward) {
				bDone = oRun.iteration >= o.maxIterations;
				if (bDone) aMask = aChars.map(function () { return true; });
			} else {
				var aVisible = [];
				aMask.forEach(function (bShown, i) { if (bShown && !isSpace(aChars[i])) aVisible.push(i); });
				var nLetters = aChars.filter(function (c) { return !isSpace(c); }).length;
				var nHide = Math.max(1, Math.ceil(nLetters / Math.max(1, o.maxIterations)));
				aMask = aMask.slice();
				for (var i = 0; i < nHide && aVisible.length; i++) {
					aMask[aVisible.splice(Math.floor(Math.random() * aVisible.length), 1)[0]] = false;
				}
				bDone = aVisible.length === 0 || oRun.iteration >= o.maxIterations;
				if (bDone) aMask = aChars.map(function (c) { return isSpace(c); });
			}

			this._mask = aMask;
			if (bDone) {
				this._run = null;
				this._finishRun(oRun);
			}
		}

		if (this._local) this._warmUp();
		else this._warm = false;

		this._paint();
		if (!this._run && !this._warm) this._stopTicker();
	};

	DecryptedText.prototype._measure = function () {
		var oBox = this._el.getBoundingClientRect();
		this._centers = this._cells.map(function (oCell) {
			if (!oCell) return null;
			var oRect = oCell.cell.getBoundingClientRect();
			return { x : oRect.left - oBox.left + oRect.width / 2, y : oRect.top - oBox.top + oRect.height / 2 };
		});
	};

	DecryptedText.prototype._trackPointer = function (e) {
		if (prefersReducedMotion()) return;
		if (!this._pointer) this._measure();
		this._pointer = { x : e.clientX, y : e.clientY };
		this._ensureTicker();
	};

	DecryptedText.prototype._onEnter = function (e) {
		if (this._local) {
			this._trackPointer(e);
			return;
		}
		if (this._run) return;
		this._startRun(true, { from : this._chars.map(isSpace) });
	};

	DecryptedText.prototype._onLeave = function () {
		var self = this;
		var o = this._o;

		if (this._local) {
			this._pointer = null;
			return;
		}
		this._stopRun();
		this._target = true;
		this._mask = this._chars.map(function () { return true; });
		this._paint();
		if (o.loop && o.animateOn === "inViewHover") {
			this._schedule(function () { self._startRun(false, { cycle : true }); }, Math.max(0, o.loopDelay));
		}
	};
})();
