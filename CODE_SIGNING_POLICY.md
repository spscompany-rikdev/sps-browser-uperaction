# Code signing policy

Free code signing for the Windows files of SPS Browser is provided by [SignPath.io](https://about.signpath.io/), with a certificate from the [SignPath Foundation](https://signpath.org/).

*(This text becomes true once SignPath has accepted the project. Until then Windows files are not signed - see "Status" below.)*

## What is signed

* Only files built from the source code in this repository (<https://github.com/spscompany-rikdev/sps-browser-uperaction>) by the public GitHub Actions workflow `.github/workflows/build.yml`.
* The Windows installer (`SPS_Browser_Setup_*.exe`) and the program files inside it (`SPS_Browser.exe`, `SPS_Browser_Core.exe`).
* Nothing else. No third-party programs are signed with this certificate. Product name and version are set in the files' metadata by the build.

## How a release is signed

1. A change reaches the `main` branch only by a commit of an Author, or by a pull request that a Reviewer has checked.
2. A new version is built by GitHub Actions from a tag (for example `v40.2.0`). The build logs are public.
3. The unsigned installer is sent from that build to SignPath. The signing request shows the GitHub repository, commit and workflow that produced it.
4. An Approver checks that the request belongs to a release they started and approves it **by hand**. Each release needs its own approval.
5. The signed files are published on the [GitHub Releases page](https://github.com/spscompany-rikdev/sps-browser-uperaction/releases) together with SHA-256 checksums.

## Team roles

| Role | What they do | Who |
|---|---|---|
| Authors (committers) | Write and merge code | [YOUR NAME](https://github.com/spscompany-rikdev) |
| Reviewers | Review every change that is not from an Author | [YOUR NAME](https://github.com/spscompany-rikdev) and any contributor a Reviewer later adds |
| Approvers | Approve each signing request by hand | [YOUR NAME](https://github.com/spscompany-rikdev) |

All team members use multi-factor authentication for GitHub and for SignPath.

## Privacy

SPS Browser has no user accounts and no usage analytics. It does not send personal information to any server run by the project. It makes network requests only for what the user asks for or switches on (for example web pages, search suggestions, update checks and block-list updates). All of them are listed in the [privacy policy](PRIVACY_POLICY.md), which is also shown during installation. The program does not install anything outside its own folder except the usual shortcuts and an uninstaller, and it can be removed from Windows "Apps & features".

## Status

Windows files published before this policy took effect are not signed. Windows may therefore show a "Windows protected your PC" screen for them; see the README for what to do and how to check the SHA-256 checksum.

Updated: <!-- DATE -->
