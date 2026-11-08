// SPS Shield - background service worker (Manifest V3). Everything runs locally; nothing is sent anywhere.
const DEFAULTS = { trackers: true, params: true, privacy: true, memorySaver: false, memoryMinutes: 30, paused: [] };

async function getSettings() { return { ...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS)) }; }

function hostOf(url) { try { return new URL(url).hostname; } catch (e) { return ""; } }

// ---- rule sets on/off + per-site pause (dynamic allow rules) ----
async function applySettings() {
  const s = await getSettings();
  await chrome.declarativeNetRequest.updateEnabledRulesets({
    enableRulesetIds: [s.trackers ? "trackers" : null, s.params ? "params" : null].filter(Boolean),
    disableRulesetIds: [s.trackers ? null : "trackers", s.params ? null : "params"].filter(Boolean),
  });
  const old = await chrome.declarativeNetRequest.getDynamicRules();
  const add = (s.paused || []).slice(0, 4000).map((h, i) => ({
    id: i + 1, priority: 100, action: { type: "allowAllRequests" },
    condition: { requestDomains: [h], resourceTypes: ["main_frame", "sub_frame"] } }));
  await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: old.map(r => r.id), addRules: add });
  if (chrome.privacy && chrome.privacy.network) {
    try {
      // WebRTC must not reveal the real IP address; Chrome's other privacy switches are set when "privacy" is on.
      if (s.privacy) {
        await chrome.privacy.network.webRTCIPHandlingPolicy.set({ value: "default_public_interface_only" });
        await chrome.privacy.services.alternateErrorPagesEnabled.set({ value: false });
        await chrome.privacy.services.safeBrowsingEnabled.set({ value: true });      // always keep protection against dangerous sites
        await chrome.privacy.websites.hyperlinkAuditingEnabled.set({ value: false });
        await chrome.privacy.websites.referrersEnabled.set({ value: true });
        await chrome.privacy.websites.thirdPartyCookiesAllowed.set({ value: false });
      } else {
        await chrome.privacy.network.webRTCIPHandlingPolicy.clear({});
        await chrome.privacy.services.alternateErrorPagesEnabled.clear({});
        await chrome.privacy.websites.hyperlinkAuditingEnabled.clear({});
        await chrome.privacy.websites.thirdPartyCookiesAllowed.clear({});
      }
    } catch (e) { /* another extension or policy controls it - ignore */ }
  }
  chrome.alarms.clear("memory");
  if (s.memorySaver) chrome.alarms.create("memory", { periodInMinutes: 5 });
}

chrome.runtime.onInstalled.addListener(applySettings);
chrome.runtime.onStartup.addListener(applySettings);
chrome.storage.onChanged.addListener((c, area) => { if (area === "sync") applySettings(); });

// ---- memory saver: discard tabs unused for N minutes (never the active, audible or pinned ones) ----
chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name !== "memory") return;
  const s = await getSettings();
  const limit = Date.now() - s.memoryMinutes * 60000;
  for (const t of await chrome.tabs.query({ active: false, audible: false, pinned: false, discarded: false })) {
    if ((t.lastAccessed || Date.now()) < limit && /^https?:/.test(t.url || "")) { try { await chrome.tabs.discard(t.id); } catch (e) {} }
  }
});

// ---- tools injected on demand ----
async function runTool(tabId, file) {
  await chrome.scripting.executeScript({ target: { tabId }, files: [file] });
}
async function toggleDark(tabId) {
  const tab = await chrome.tabs.get(tabId);
  const key = "dark:" + hostOf(tab.url);
  const cur = (await chrome.storage.local.get(key))[key];
  if (cur) { await chrome.scripting.removeCSS({ target: { tabId }, files: ["content/dark.css"] }).catch(() => {}); await chrome.storage.local.remove(key); }
  else { await chrome.scripting.insertCSS({ target: { tabId }, files: ["content/dark.css"] }); await chrome.storage.local.set({ [key]: 1 }); }
}
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {          // remember dark mode per site
  if (info.status !== "loading" || !/^https?:/.test(tab.url || "")) return;
  const key = "dark:" + hostOf(tab.url);
  if ((await chrome.storage.local.get(key))[key]) chrome.scripting.insertCSS({ target: { tabId }, files: ["content/dark.css"] }).catch(() => {});
});

chrome.commands.onCommand.addListener(async (cmd) => {
  if (cmd !== "area-print") return;
  const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (t && /^https?:/.test(t.url || "")) runTool(t.id, "content/area_print.js");
});

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    if (msg.type === "tool") {
      const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!t || !/^https?:/.test(t.url || "")) return reply({ ok: false, error: "Open a normal web page first." });
      if (msg.tool === "area") await runTool(t.id, "content/area_print.js");
      else if (msg.tool === "reader") await runTool(t.id, "content/reader.js");
      else if (msg.tool === "dark") await toggleDark(t.id);
      return reply({ ok: true });
    }
    if (msg.type === "capture") {                         // area print asks for a screenshot of the visible tab
      const url = await chrome.tabs.captureVisibleTab(sender.tab.windowId, { format: "png" });
      return reply({ url });
    }
    if (msg.type === "print-image") {
      await chrome.storage.session.set({ printImage: msg.url });
      await chrome.tabs.create({ url: chrome.runtime.getURL("options/print.html") });
      return reply({ ok: true });
    }
    if (msg.type === "pause") {
      const s = await getSettings(); const set = new Set(s.paused);
      msg.on ? set.add(msg.host) : set.delete(msg.host);
      await chrome.storage.sync.set({ paused: [...set] });
      return reply({ ok: true });
    }
  })().catch(e => reply({ ok: false, error: String(e) }));
  return true;
});
