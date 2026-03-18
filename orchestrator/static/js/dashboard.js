/* dashboard.js — A9 progressive enhancement. Vanilla JS only. */
'use strict';

// Expand/collapse truncated cells on click
document.querySelectorAll('.cell-clamp').forEach(function (el) {
  el.addEventListener('click', function () {
    if (el.style.webkitLineClamp === 'none') {
      el.style.webkitLineClamp = '';
      el.style.overflow = '';
    } else {
      el.style.webkitLineClamp = 'none';
      el.style.overflow = 'visible';
    }
  });
  el.title = 'Click to expand';
});

// Highlight search matches
(function () {
  var q = (new URLSearchParams(window.location.search).get('q') || '').trim();
  if (!q) return;
  var re;
  try { re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi'); }
  catch (e) { return; }
  document.querySelectorAll('.cell-clamp').forEach(function (el) {
    el.innerHTML = el.textContent.replace(re, '<mark>$1</mark>');
  });
})();

// Auto-submit filter form on select change
var ff = document.querySelector('.filter-bar');
if (ff) {
  ff.querySelectorAll('select').forEach(function (s) {
    s.addEventListener('change', function () { ff.submit(); });
  });
}

// "/" shortcut focuses search input
document.addEventListener('keydown', function (e) {
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
    var inp = document.querySelector('.search-form input[type="text"]');
    if (inp) { e.preventDefault(); inp.focus(); }
  }
});
