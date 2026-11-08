const $ = (id) => document.getElementById(id);
(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  let host = ""; try { host = new URL(tab.url).hostname; } catch (e) {}
  $("site").textContent = host || "(no web page)";
  const s = await chrome.storage.sync.get({ paused: [] });
  $("pause").checked = s.paused.includes(host); $("pause").disabled = !host;
  $("pause").onchange = () => chrome.runtime.sendMessage({ type: "pause", host, on: $("pause").checked }).then(() => chrome.tabs.reload(tab.id));
  for (const [id, tool] of [["area", "area"], ["reader", "reader"], ["dark", "dark"]])
    $(id).onclick = async () => { const r = await chrome.runtime.sendMessage({ type: "tool", tool }); if (r && r.ok) window.close(); else $("stat").textContent = (r && r.error) || "Failed"; };
  $("opts").onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
  try { const n = await chrome.declarativeNetRequest.getMatchedRules({ tabId: tab.id }); $("stat").textContent = "Blocked on this page: " + n.rulesMatchedInfo.length; } catch (e) { $("stat").textContent = ""; }
})();
