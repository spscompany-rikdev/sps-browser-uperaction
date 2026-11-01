// Drag a square on the page, then print only that part (the page is captured as a picture, cropped, and printed).
(() => {
  if (window.__spsArea) return; window.__spsArea = true;
  const ov = document.createElement("div");
  ov.style.cssText = "position:fixed;inset:0;z-index:2147483647;cursor:crosshair;background:rgba(0,0,0,.25);font:14px system-ui";
  const tip = document.createElement("div");
  tip.textContent = "Drag to select the area to print - Esc to cancel";
  tip.style.cssText = "position:fixed;top:12px;left:50%;transform:translateX(-50%);background:#111;color:#fff;padding:8px 14px;border-radius:8px";
  const box = document.createElement("div");
  box.style.cssText = "position:fixed;border:2px dashed #4da3ff;background:rgba(77,163,255,.15);display:none";
  ov.append(tip, box); document.documentElement.appendChild(ov);
  let x0 = 0, y0 = 0, drag = false;
  const done = () => { ov.remove(); window.__spsArea = false; removeEventListener("keydown", key, true); };
  const key = (e) => { if (e.key === "Escape") done(); };
  addEventListener("keydown", key, true);
  const rect = (e) => ({ x: Math.min(x0, e.clientX), y: Math.min(y0, e.clientY), w: Math.abs(e.clientX - x0), h: Math.abs(e.clientY - y0) });
  ov.addEventListener("mousedown", (e) => { drag = true; x0 = e.clientX; y0 = e.clientY; box.style.display = "block"; e.preventDefault(); });
  ov.addEventListener("mousemove", (e) => { if (!drag) return; const r = rect(e); Object.assign(box.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px" }); });
  ov.addEventListener("mouseup", async (e) => {
    drag = false; const r = rect(e);
    if (r.w < 8 || r.h < 8) return done();
    ov.style.display = "none"; await new Promise(res => setTimeout(res, 120));          // hide our own overlay before the screenshot
    const { url } = await chrome.runtime.sendMessage({ type: "capture" });
    done();
    const img = new Image(); img.src = url; await img.decode();
    const k = img.naturalWidth / innerWidth, c = document.createElement("canvas");
    c.width = Math.round(r.w * k); c.height = Math.round(r.h * k);
    c.getContext("2d").drawImage(img, r.x * k, r.y * k, r.w * k, r.h * k, 0, 0, c.width, c.height);
    chrome.runtime.sendMessage({ type: "print-image", url: c.toDataURL("image/png") });
  });
})();
