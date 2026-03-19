/* dashboard.js — A10 polish. Vanilla JS, zero deps. */
'use strict';

(function () {

  /* ── Expand/collapse truncated cells on click ── */
  document.querySelectorAll('.cell-clamp').forEach(function (el) {
    el.addEventListener('click', function () {
      if (el.style.webkitLineClamp === 'none') {
        el.style.webkitLineClamp = '';
        el.style.overflow = '';
        el.style.maxWidth = '';
      } else {
        el.style.webkitLineClamp = 'none';
        el.style.overflow = 'visible';
        el.style.maxWidth = 'none';
      }
    });
    el.setAttribute('title', el.getAttribute('title') || 'Click to expand');
  });

  /* ── Highlight search query matches in cell-clamp text ── */
  var q = (new URLSearchParams(window.location.search).get('q') || '').trim();
  if (q) {
    var re;
    try {
      re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
    } catch (e) { re = null; }
    if (re) {
      document.querySelectorAll('.cell-clamp').forEach(function (el) {
        var text = el.textContent;
        if (re.test(text)) {
          el.innerHTML = text.replace(re, '<mark>$1</mark>');
        }
        re.lastIndex = 0;
      });
    }
  }

  /* ── Auto-submit filter form on select/checkbox change ── */
  var ff = document.querySelector('.filter-bar');
  if (ff) {
    ff.querySelectorAll('select').forEach(function (s) {
      s.addEventListener('change', function () { ff.submit(); });
    });
  }

  /* ── "/" shortcut → focus search input ── */
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      var inp = document.querySelector('.search-form input[type="text"]');
      if (inp) { e.preventDefault(); inp.focus(); inp.select(); }
    }
  });

  /* ── Escape → blur search input ── */
  document.querySelectorAll('.search-form input[type="text"]').forEach(function (inp) {
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { inp.blur(); }
    });
  });

  /* ── Animate summary card values on load ── */
  document.querySelectorAll('.summary-value').forEach(function (el) {
    var raw = parseInt(el.textContent, 10);
    if (isNaN(raw) || raw === 0) return;
    var start = 0;
    var duration = 400;
    var startTime = null;
    var originalText = el.textContent.trim();
    // only animate purely numeric values
    if (!/^\d+$/.test(originalText)) return;
    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(eased * raw);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = originalText;
    }
    requestAnimationFrame(step);
  });

  /* ── Rate bar width animation ── */
  document.querySelectorAll('.rate-fill').forEach(function (fill) {
    var target = fill.style.width;
    fill.style.width = '0%';
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        fill.style.transition = 'width .5s cubic-bezier(.4,0,.2,1)';
        fill.style.width = target;
      });
    });
  });

  /* ── Copy task_id on click ── */
  document.querySelectorAll('code[title]').forEach(function (el) {
    var full = el.getAttribute('title');
    if (!full || full.length < 32) return; // likely a task_id
    el.style.cursor = 'copy';
    el.addEventListener('click', function () {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(full).then(function () {
          var orig = el.textContent;
          el.textContent = 'copied!';
          setTimeout(function () { el.textContent = orig; }, 1200);
        });
      }
    });
  });

})();
