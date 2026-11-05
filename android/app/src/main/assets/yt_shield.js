(function () {
  if (window.__spsYtShield) return;
  window.__spsYtShield = true;

  // 1) Cosmetic: ad containers never show (also the ad thumbnail / skip box of the video player).
  var css = [
    'ytd-ad-slot-renderer', 'ytd-in-feed-ad-layout-renderer', 'ytd-display-ad-renderer', 'ytd-promoted-sparkles-web-renderer',
    'ytd-promoted-video-renderer', 'ytd-banner-promo-renderer', 'ytd-statement-banner-renderer', 'ytd-companion-slot-renderer',
    'ytd-action-companion-ad-renderer', 'ytd-player-legacy-desktop-watch-ads-renderer', 'ytm-promoted-sparkles-web-renderer',
    'ytm-promoted-video-renderer', 'ytm-companion-ad-renderer', 'ytm-companion-slot', 'ad-slot-renderer', '#masthead-ad', '#player-ads',
    '.ytp-ad-module', '.ytp-ad-overlay-container', '.ytp-ad-image-overlay', '.ytp-ad-text-overlay', '.video-ads',
    '.ytp-ad-player-overlay', '.ytp-ad-player-overlay-layout', '.ytp-ad-skip-button-slot', '.ytp-suggested-action-badge'
  ].join(',') + '{display:none !important}' +
  '.html5-video-player.ad-showing .html5-video-container,.html5-video-player.ad-showing video{opacity:0 !important}';
  function addCss() {
    if (document.getElementById('sps-yt-shield-css')) return;
    var s = document.createElement('style'); s.id = 'sps-yt-shield-css'; s.textContent = css;
    var host = document.head || document.documentElement;
    if (!host) return false;
    host.appendChild(s);
    return true;
  }
  if (!addCss()) {                       // <head> does not exist yet at document start: retry a few times, no page-wide observer
    var tries = 0;
    (function retry() { if (!addCss() && ++tries < 40) setTimeout(retry, 25); })();
  }
  document.addEventListener('DOMContentLoaded', addCss);

  // 2) The real fix (like Brave's scriptlets): the ad schedule is removed from YouTube's own data before the player reads it.
  var KEYS = ['adPlacements', 'playerAds', 'adSlots', 'adBreakHeartbeatParams'];
  function prune(o) {
    if (!o || typeof o !== 'object') return o;
    try {
      for (var i = 0; i < KEYS.length; i++) { if (KEYS[i] in o) delete o[KEYS[i]]; }
      var pr = o.playerResponse;
      if (pr && typeof pr === 'object') { for (var j = 0; j < KEYS.length; j++) { if (KEYS[j] in pr) delete pr[KEYS[j]]; } }
    } catch (e) { }
    return o;
  }

  var origParse = JSON.parse;
  JSON.parse = function () {
    var r = origParse.apply(this, arguments);
    if (r && typeof r === 'object' && (r.adPlacements || r.playerAds || r.adSlots || r.playerResponse)) prune(r);
    return r;
  };

  if (window.Response && Response.prototype && Response.prototype.json) {
    var origJson = Response.prototype.json;
    Response.prototype.json = function () {
      var url = this.url || '';
      var p = origJson.apply(this, arguments);
      if (url.indexOf('/youtubei/v1/') === -1) return p;
      return p.then(prune);
    };
  }

  var initial;
  try {
    Object.defineProperty(window, 'ytInitialPlayerResponse', {
      configurable: true,
      get: function () { return initial; },
      set: function (v) { initial = prune(v); }
    });
  } catch (e) { }

  // 3) Safety net for anything that still slips through: cheap check twice a second, only does work while an ad is on screen.
  var savedMuted = null;
  setInterval(function () {
    try {
      var p = document.querySelector('.html5-video-player.ad-showing');
      var v = document.querySelector('video.html5-main-video') || document.querySelector('video');
      if (!p) {
        if (savedMuted !== null && v) { v.muted = savedMuted; savedMuted = null; }
        return;
      }
      if (v) {
        if (savedMuted === null) savedMuted = v.muted;
        v.muted = true;
        if (isFinite(v.duration) && v.duration > 0) v.currentTime = v.duration;
        v.playbackRate = 16;
      }
      var b = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button, button.ytp-ad-skip-button-container');
      if (b) b.click();
    } catch (e) { }
  }, 500);
})();
