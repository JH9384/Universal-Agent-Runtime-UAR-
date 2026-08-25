# Security Policy

## Supported code

Security fixes are targeted at the current `main` branch and the most recent release line that is still explicitly maintained by the repository.

## Reporting a vulnerability

Please do not disclose exploitable vulnerability details in a public issue or pull request.

If GitHub private vulnerability reporting is enabled for this repository, use **Security → Report a vulnerability**. If that option is unavailable, contact the repository maintainer privately through the maintainer's GitHub profile before public disclosure and provide a minimal description sufficient to establish a private reporting channel.

A useful report includes:

- affected commit, version, or tag;
- affected component and execution path;
- reproduction steps or a minimal proof of concept;
- expected versus observed behavior;
- security impact and prerequisites;
- any proposed mitigation, if known.

## Sensitive material

Do not commit credentials, API keys, private keys, signing keys, production tokens, unredacted operational data, or other secrets to the repository, including examples and test fixtures.

If a secret is committed, treat it as compromised: revoke or rotate it first, then remove it from the active repository state. History rewriting should be considered separately because it affects provenance and collaborators.

## Supply-chain and workflow security

Repository automation should follow least privilege. Workflows should declare explicit permissions, scope OIDC to jobs that actually require it, and pin third-party Actions to reviewed immutable commit SHAs where practical.

Release and signing claims must be tied to an identifiable source commit and reproducible inputs. Unsigned historical tags should not be represented as having guarantees they did not originally carry.
