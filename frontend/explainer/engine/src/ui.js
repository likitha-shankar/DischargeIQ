/**
 * File: frontend/explainer/engine/src/ui.js
 * Component: Anatomy Explainer — UI Controller
 * Description: Drives all non-3D HTML UI: gesture hint, play bar (play/pause,
 *   progress indicator, panel counter), caption text, safety lines, title bar,
 *   footer, and the text-only fallback panel.
 *
 *   Panels advance automatically on play. Each panel duration is derived from
 *   caption length (roughly 0.7 words/sec speaking pace) with a 4s minimum.
 *   The play bar progress indicator tracks elapsed time within the current panel.
 *
 * Dependencies: none (pure DOM)
 * Consumed by: src/main.js
 */

/** Minimum panel display time in seconds regardless of caption length. */
const MIN_PANEL_DURATION_S = 4;

/** Estimated reading pace (words per second) to derive panel duration. */
const WORDS_PER_SECOND = 2.5;

class UIController {
  /**
   * Initialise the UI controller and wire event listeners.
   *
   * @param {function(number): void} onPanelChange - Called with panel index when
   *   the active panel changes (via auto-advance or future swipe navigation).
   */
  constructor(onPanelChange) {
    this._onPanelChange = onPanelChange;
    this._panels = [];
    this._currentIndex = 0;
    this._isPlaying = false;
    this._elapsed = 0;
    this._panelDuration = MIN_PANEL_DURATION_S;

    this._els = {
      title: document.getElementById('explainer-title'),
      subtitle: document.getElementById('explainer-subtitle'),
      caption: document.getElementById('caption-text'),
      playPause: document.getElementById('play-pause-btn'),
      progressFill: document.getElementById('progress-fill'),
      panelCounter: document.getElementById('panel-counter'),
      safetySection: document.getElementById('safety-lines'),
      safetyContent: document.getElementById('safety-lines-content'),
      footer: document.getElementById('grounding-footer'),
      gestureHint: document.getElementById('gesture-hint'),
      loadingOverlay: document.getElementById('loading-overlay'),
      textFallback: document.getElementById('text-fallback'),
      fallbackTitle: document.getElementById('fallback-title'),
      fallbackBody: document.getElementById('fallback-body'),
    };

    this._els.playPause.addEventListener('click', () => this._togglePlayPause());
    this._bindGestureHintDismiss();
  }

  /**
   * Populate the UI with data from the explainer config.
   *
   * Call after config is loaded but before showing any panels. Sets the title,
   * subtitle, footer text, and safety lines. Does NOT start auto-play; call
   * play() explicitly once the 3D model (or fallback) is ready.
   *
   * @param {object} config - Full explainer config object from config.js.
   * @returns {void}
   */
  applyConfig(config) {
    this._els.title.textContent = config.title || 'Anatomy Explainer';
    this._els.subtitle.textContent = config.subtitle || '';
    if (config.footer) this._els.footer.textContent = config.footer;
    this._panels = config.panels || [];
    this._renderSafetyLines(config.safety_lines || []);
    if (this._panels.length > 0) {
      this._showPanel(0);
    }
  }

  /**
   * Render the verbatim hospital safety lines into the safety section.
   *
   * Each line is shown as a blockquote with a serif treatment and visual
   * separation. The section is hidden when there are no lines.
   *
   * @param {string[]} lines - Exact verbatim quotes from the discharge document.
   * @returns {void}
   */
  _renderSafetyLines(lines) {
    if (lines.length === 0) {
      this._els.safetySection.style.display = 'none';
      return;
    }
    this._els.safetyContent.innerHTML = lines
      .map((l) => `<blockquote>${_escapeHtml(l)}</blockquote>`)
      .join('');
    this._els.safetySection.style.display = 'block';
  }

  /**
   * Update caption text and panel counter for the given panel index.
   *
   * Also computes the auto-advance duration from caption word count.
   *
   * @param {number} index - Zero-based panel index.
   * @returns {void}
   */
  _showPanel(index) {
    this._currentIndex = index;
    const panel = this._panels[index];
    if (!panel) return;

    const caption = panel.caption || '';
    this._els.caption.textContent = caption;
    this._els.panelCounter.textContent = `${index + 1} / ${this._panels.length}`;

    const wordCount = caption.split(/\s+/).filter(Boolean).length;
    this._panelDuration = Math.max(
      MIN_PANEL_DURATION_S,
      wordCount / WORDS_PER_SECOND,
    );
    this._elapsed = 0;
    this._updateProgressBar(0);
    this._onPanelChange(index);
  }

  /**
   * Toggle play/pause state and update the button icon.
   *
   * @returns {void}
   */
  _togglePlayPause() {
    this._isPlaying ? this.pause() : this.play();
  }

  /**
   * Advance the progress bar and handle auto-advance to next panel.
   *
   * Called from the Viewer's update callback (via main.js) with each frame's
   * delta time. No-ops when paused or when there are no panels.
   *
   * @param {number} delta - Elapsed seconds since last frame.
   * @returns {void}
   */
  tick(delta) {
    if (!this._isPlaying || this._panels.length === 0) return;
    this._elapsed += delta;
    const progress = Math.min(this._elapsed / this._panelDuration, 1);
    this._updateProgressBar(progress);
    if (progress >= 1) this._advance();
  }

  /**
   * Advance to the next panel, or stop at the end.
   *
   * @returns {void}
   */
  _advance() {
    const next = this._currentIndex + 1;
    if (next < this._panels.length) {
      this._showPanel(next);
    } else {
      this.pause();
      this._updateProgressBar(1);
    }
  }

  /**
   * Set the progress fill bar width (0–1 fraction).
   *
   * @param {number} fraction - Value between 0 and 1 inclusive.
   * @returns {void}
   */
  _updateProgressBar(fraction) {
    this._els.progressFill.style.width = `${Math.round(fraction * 100)}%`;
  }

  /**
   * Start auto-advance. Updates play-button icon.
   *
   * @returns {void}
   */
  play() {
    this._isPlaying = true;
    this._els.playPause.textContent = '⏸';
    this._els.playPause.setAttribute('aria-label', 'Pause');
  }

  /**
   * Pause auto-advance. Updates play-button icon.
   *
   * @returns {void}
   */
  pause() {
    this._isPlaying = false;
    this._els.playPause.textContent = '▶';
    this._els.playPause.setAttribute('aria-label', 'Play');
  }

  /**
   * Dismiss the loading spinner overlay.
   *
   * Call after the 3D model (or text fallback) is ready for interaction.
   *
   * @returns {void}
   */
  hideLoading() {
    this._els.loadingOverlay.classList.add('hidden');
  }

  /**
   * Show the text-only fallback panel and hide the 3D canvas.
   *
   * Called when the engine determines no verified model is available.
   * The fallback panel renders the same caption content as plain text
   * so the patient still receives their information.
   *
   * @param {string} title - Heading for the fallback panel.
   * @param {string} body - Plain-language explanation text.
   * @returns {void}
   */
  showTextFallback(title, body) {
    this._els.fallbackTitle.textContent = title || 'Anatomy View Unavailable';
    this._els.fallbackBody.textContent = body;
    this._els.textFallback.style.display = 'block';
  }

  /**
   * Dismiss the "drag to rotate" gesture hint immediately.
   *
   * @returns {void}
   */
  dismissGestureHint() {
    this._els.gestureHint.classList.add('hidden');
  }

  /**
   * Register a one-time pointermove listener that dismisses the gesture hint.
   *
   * The hint fades out via CSS transition on first interaction; after that the
   * listener is removed so it does not run every frame.
   *
   * @returns {void}
   */
  _bindGestureHintDismiss() {
    const dismiss = () => {
      this.dismissGestureHint();
      window.removeEventListener('pointermove', dismiss);
    };
    window.addEventListener('pointermove', dismiss, { once: true });
  }

  /**
   * Return the panel at the given index, or null.
   *
   * @param {number} index
   * @returns {object|null}
   */
  getPanel(index) {
    return this._panels[index] ?? null;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Escape user-provided text for safe HTML insertion.
 *
 * Safety lines come verbatim from a discharge document and may contain
 * characters that would break innerHTML assignment without escaping.
 *
 * @param {string} str - Raw string.
 * @returns {string} - HTML-safe string.
 */
function _escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export { UIController };
