(async () => {
  const { printImage } = await chrome.storage.session.get("printImage");
  const i = document.getElementById("i"); i.src = printImage || ""; await i.decode().catch(() => {});
  document.getElementById("p").onclick = () => print();
  setTimeout(() => print(), 300);
})();
