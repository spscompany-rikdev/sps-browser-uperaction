// Reader mode: show the main text of the page in a clean, readable view (press Esc or the Close button to leave).
(() => {
  if (document.getElementById("sps-reader")) { document.getElementById("sps-reader").remove(); return; }
  const root = document.querySelector("article") || document.querySelector("main") || document.body;
  const parts = [...root.querySelectorAll("h1,h2,h3,p,li,blockquote,pre,img")].filter(n => n.tagName === "IMG" ? n.width > 200 : n.innerText && n.innerText.trim().length > 1);
  const host = document.createElement("div"); host.id = "sps-reader";
  host.style.cssText = "position:fixed;inset:0;z-index:2147483647;overflow:auto;background:#faf7f0;color:#222";
  const sh = host.attachShadow({ mode: "open" });
  const st = document.createElement("style");
  st.textContent = "article{max-width:44rem;margin:0 auto;padding:3rem 1.2rem;font:20px/1.7 Georgia,serif}img{max-width:100%;height:auto}button{position:fixed;top:12px;right:12px;font:14px system-ui;padding:6px 12px}pre{white-space:pre-wrap}";
  const art = document.createElement("article"), b = document.createElement("button");
  b.textContent = "Close"; b.onclick = () => host.remove();
  const h = document.createElement("h1"); h.textContent = document.title; art.append(h);
  for (const n of parts) {
    if (n.tagName === "IMG") { const i = document.createElement("img"); i.src = n.currentSrc || n.src; art.append(i); }
    else { const e = document.createElement(n.tagName.toLowerCase()); e.textContent = n.innerText.trim(); art.append(e); }   // textContent only: never copies page scripts
  }
  sh.append(st, b, art); document.documentElement.appendChild(host);
  addEventListener("keydown", function k(e) { if (e.key === "Escape") { host.remove(); removeEventListener("keydown", k, true); } }, true);
})();
