# Security policy

## Reporting a problem

If you find a security problem in SPS Browser, please open a **private** report: on GitHub go to the *Security* tab of this repository and choose *Report a vulnerability*. If that is not available, open an issue that says "security" without exploit details and we will arrange a private way to talk.

Please include: the version (Menu ⋮ → About), Windows version, and the steps to reproduce.

## What to expect

* We aim to answer within 7 days.
* Fixes are released as a new version on the GitHub Releases page.

## Supported versions

Only the newest release is supported. Please update before reporting.

## Verifying a download

Every release lists SHA-256 checksums (`SHA256SUMS.txt`). On Windows:

```
certutil -hashfile <file name> SHA256
```

Compare the result with the value in `SHA256SUMS.txt`.
