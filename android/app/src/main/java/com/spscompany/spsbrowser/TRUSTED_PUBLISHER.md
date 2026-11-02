# Making SPS Browser a "trusted publisher" - the honest way (free)

Windows shows *"Unknown publisher"* / SmartScreen warnings for every program that has no **real digital signature**.
A signature is only valuable because a certificate authority checked WHO you are and the signature cannot be forged.

> **SPS Browser will NOT create or install a fake / self-made signature or certificate.**
> Doing that is the same trick malware uses, it would not make Windows trust the program on anybody else's PC
> (a self-made certificate is only trusted on the PC where it was installed), and installing a root certificate
> silently would weaken the security of every user. It is deliberately not part of this build.

## The free route: SignPath Foundation (for open-source projects)
SPS Browser is GPL-3.0 open source, so it qualifies for **free** real code signing from the SignPath Foundation
(https://signpath.org/foundation - check the current conditions on their site):

1. Put the source code in a **public GitHub repository** with the `LICENSE.txt` (GPL-3.0) included.
2. Build the release with **GitHub Actions** (they sign only builds made by a public CI, so users can trust them).
3. Apply at SignPath Foundation, fill in the project form (name, repo, licence, who maintains it).
4. After approval, add their GitHub Action to the workflow - it signs `SPS_Browser.exe`, `SPS_Browser_Core.exe`
   and the installer. The publisher shown to users will be "SignPath Foundation".

## Other legitimate options
| Option | Cost | Notes |
|---|---|---|
| Microsoft Store (MSIX package) | small one-time developer fee | Microsoft signs the package; no SmartScreen warning |
| winget (`winget install SPS.Browser`) | free | installs from a manifest with a hash; users trust the Microsoft source |
| Azure Trusted Signing | low monthly fee | real certificate for individuals/companies |
| Normal OV/EV certificate | ~US$100-400 / year | `BUILD.bat` signs automatically if you set `SPS_SIGN_PFX` and `SPS_SIGN_PASS` |

## While you have no certificate (reduces warnings, does not remove them)
* Publish on GitHub Releases only, always the same file name; SmartScreen reputation grows with downloads.
* Upload each release to https://www.virustotal.com and keep the link in the release notes.
* Submit the installer to Microsoft as a false positive: https://www.microsoft.com/wdsi/filesubmission
* Tell users: *More info -> Run anyway* appears because the file is new, and publish the SHA-256 hash
  (`certutil -hashfile SPS_Browser_Setup_v36.0.exe SHA256`).
