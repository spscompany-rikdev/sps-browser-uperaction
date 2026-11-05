/* SPS Browser - Easy access helper (injected on demand, controls the page's own <video>/<audio>/<img>). */
window.__spsEasy = (function () {
  function pick() {
    var ms = [].slice.call(document.querySelectorAll('video,audio'));
    return ms.filter(function (x) { return !x.paused && !x.ended; })[0] ||
           ms.filter(function (x) { return x.readyState > 0 && x.duration > 0; })[0];
  }
  function probe() {
    try {
      var m = pick(), ct = document.contentType || '';
      var r = { url: location.href, title: document.title, isImg: ct.indexOf('image/') == 0, imgs: document.images.length };
      if (m) {
        var md = null; try { md = navigator.mediaSession && navigator.mediaSession.metadata; } catch (e) {}
        r.media = { kind: m.tagName.toLowerCase(), paused: m.paused, muted: m.muted, vol: m.volume, rate: m.playbackRate, loop: m.loop,
          t: m.currentTime, d: isFinite(m.duration) ? m.duration : 0, pip: !!document.pictureInPictureElement,
          title: (md && md.title) || '', artist: (md && md.artist) || '' };
      }
      return JSON.stringify(r);
    } catch (e) { return '{}'; }
  }
  function ctl(a, v) {
    var m = pick(); if (!m) return;
    var b;
    switch (a) {
      case 'toggle': if (m.paused) m.play(); else m.pause(); break;
      case 'seekrel': m.currentTime = Math.max(0, Math.min(m.duration || 1e9, m.currentTime + v)); break;
      case 'seekfrac': if (m.duration) m.currentTime = m.duration * v; break;
      case 'rate': m.playbackRate = v; break;
      case 'vol': m.volume = v; m.muted = false; break;
      case 'mute': m.muted = !m.muted; break;
      case 'loop': m.loop = !m.loop; break;
      case 'pip': if (document.pictureInPictureElement) document.exitPictureInPicture(); else if (m.requestPictureInPicture) m.requestPictureInPicture(); break;
      case 'fs': var e = (m.closest && m.closest('#movie_player,.html5-video-player')) || m;
        if (document.fullscreenElement) document.exitFullscreen(); else (e.requestFullscreen || e.webkitRequestFullscreen || function () {}).call(e); break;
      case 'next': b = document.querySelector('.ytp-next-button,.next-button,[aria-label="Next"]'); if (b) b.click(); else m.currentTime = m.duration || m.currentTime; break;
      case 'prev': b = document.querySelector('.ytp-prev-button,.previous-button,[aria-label="Previous"]');
        if (b && b.offsetParent !== null && !b.disabled) b.click(); else m.currentTime = 0; break;
    }
  }
  function img(a, v) {
    var i = document.images[0]; if (!i) return;
    var S = window.__sps = window.__sps || { rot: 0, fx: 1, b: 100, c: 100, s: 100, g: 0 };
    switch (a) {
      case 'rot': S.rot = (S.rot + 90) % 360; break;
      case 'flip': S.fx = -S.fx; break;
      case 'b': S.b = v; break; case 'c': S.c = v; break; case 's': S.s = v; break;
      case 'gray': S.g = S.g ? 0 : 100; break;
      case 'reset': S.rot = 0; S.fx = 1; S.b = 100; S.c = 100; S.s = 100; S.g = 0; break;
    }
    i.style.transition = 'transform .25s ease,filter .2s';
    i.style.transform = 'rotate(' + S.rot + 'deg) scaleX(' + S.fx + ')';
    i.style.filter = 'brightness(' + S.b + '%) contrast(' + S.c + '%) saturate(' + S.s + '%) grayscale(' + S.g + '%)';
  }
  function gallery() {
    var o = document.getElementById('__sps_gal'); if (o) { o.remove(); return; }
    var seen = {}, L = [].slice.call(document.images).filter(function (i) {
      var k = i.currentSrc || i.src; return i.naturalWidth >= 80 && i.naturalHeight >= 80 && !seen[k] && (seen[k] = 1); });
    o = document.createElement('div'); o.id = '__sps_gal';
    o.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:rgba(15,15,20,.94);overflow:auto;padding:16px;font:14px system-ui;color:#fff;animation:spsg .22s ease';
    var st = document.createElement('style'); st.textContent = '@keyframes spsg{from{opacity:0;transform:scale(.98)}to{opacity:1;transform:none}}'; o.appendChild(st);
    var h = document.createElement('div'); h.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;font-size:17px;font-weight:600';
    h.textContent = 'Images on this page (' + L.length + ')';
    var x = document.createElement('button'); x.textContent = 'Close'; x.style.cssText = 'border:0;border-radius:18px;padding:8px 16px;font-weight:600';
    x.onclick = function () { o.remove(); }; h.appendChild(x); o.appendChild(h);
    var g = document.createElement('div'); g.style.cssText = 'display:grid;grid-template-columns:repeat(2,1fr);gap:10px';
    L.forEach(function (i) { var im = document.createElement('img'); im.src = i.currentSrc || i.src;
      im.style.cssText = 'width:100%;height:130px;object-fit:cover;border-radius:12px;background:#222'; im.onclick = function () { location.href = im.src; }; g.appendChild(im); });
    o.appendChild(g); document.documentElement.appendChild(o);
  }
  return { probe: probe, ctl: ctl, img: img, gallery: gallery };
})();
