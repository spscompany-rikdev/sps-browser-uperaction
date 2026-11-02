# SPS VPN - how to get a server (free or cheap)

A VPN needs a server somewhere. SPS VPN does not sell or run servers. Options:

1. **A provider's free plan that gives WireGuard files** - check the provider's website whether the free plan lets you download a WireGuard `.conf` (for example Proton VPN's account pages). Plans and limits change; confirm on their site.
2. **Your own server (full control, privacy-friendly)** - a small cloud VPS (some providers have an always-free tier, availability varies) with WireGuard installed (`wireguard-install` style scripts exist). Download the client `.conf`.
3. **Tor** - built in, free, anonymous, slower (browser mode only).
4. **Existing proxy you trust** (SOCKS5/HTTP) - browser mode only.

Never use random "free proxy list" servers: the operator can read and change your traffic.

## Use it
- Browser only: SPS Browser -> 🛡 VPN -> `+ WireGuard file…` -> select -> Connect (browser restarts once).
- Whole computer: install WireGuard (Windows: wireguard.com/install; Linux: `sudo apt install wireguard-tools`), then in the VPN window select the WireGuard server -> "Protect WHOLE computer" and approve the administrator prompt. Undo with "Stop whole-computer VPN".
- Check at any "what is my IP" site that the address changed.

## Protecting the WHOLE computer (step by step)
1. Open SPS VPN -> **Install WireGuard (needed once)** (Windows installer is bundled; its WireGuard LLC signature is verified first).
2. Get a WireGuard `.conf` (SPS has no servers and never shares one account between users):
   - Proton VPN free plan: account.protonvpn.com -> Downloads -> WireGuard configuration -> choose a free server -> Create -> Download.
   - Your own server (PiVPN / wg-easy on a cheap VPS), or Mullvad / IVPN / any provider that offers WireGuard files.
3. **+ WireGuard file...** or **+ Paste config**, select it, press **Protect WHOLE computer**, approve the administrator prompt.
4. Undo with **Stop whole-computer VPN**.
