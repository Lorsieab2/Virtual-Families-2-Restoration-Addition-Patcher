# Local Release Signing

Release executables are signed with the local-development Code Signing
certificate in the current user's certificate store. Run:

```bat
work\sign_release_build.bat "path\to\Virtual Families 2 - Additive Mobile Furniture Pack.exe"
```

The certificate is self-signed (`Lorsieab2 VF2 Local Development`) and trusted
on this Windows user profile. It establishes a verifiable local publisher but
does not create Microsoft Smart App Control reputation or third-party antivirus
allowlisting. A publicly trusted commercial code-signing certificate and its
associated reputation would be required for that.

## Current Prerequisite Check

On 2026-07-02, signing B62 and B63 failed with `SignTool Error: No certificates
were found that met all the given criteria.` Treat the thumbprint in
`work\sign_release_build.bat` as an environment prerequisite, not a guaranteed
local capability.
