const D = { trackers: true, params: true, privacy: true, memorySaver: false, memoryMinutes: 30 };
(async () => {
  const s = await chrome.storage.sync.get(D);
  for (const k of Object.keys(D)) {
    const el = document.getElementById(k);
    if (el.type === "checkbox") { el.checked = s[k]; el.onchange = () => chrome.storage.sync.set({ [k]: el.checked }); }
    else { el.value = s[k]; el.onchange = () => chrome.storage.sync.set({ [k]: Math.max(5, +el.value || 30) }); }
  }
})();
