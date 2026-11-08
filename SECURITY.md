# Security policy

## Supported versions

legalgraph is published from the `main` branch, and the website legalgraph.org is built from it.
Only `main` receives fixes.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately instead:

- through GitHub: **Security → Report a vulnerability** on this repository, or
- by email to [contact@aimix.io](mailto:contact@aimix.io), with "legalgraph security" in the subject.

Describe what you found, how to reproduce it, and what it affects. We confirm receipt within a few
working days, keep you informed while we fix it, and credit you when the fix is published, unless
you would rather stay anonymous.

## In scope

- The `legalgraph` command-line tool and its dependencies (`src/`, `pyproject.toml`, `uv.lock`).
- The website's code (`site/`), including the scripts that run in visitors' browsers.
- The GitHub Actions workflows (`.github/workflows/`).
- Anything that would let an altered law text pass `legalgraph sources verify`: the graph's value
  rests on the check that every quote matches the official original.

A wrong quote, citation or interpretation is not a security problem. Please report it as a normal
[issue](https://github.com/legalgraph-org/legalgraph/issues).

## Verifying commits

Maintainers sign their commits and tags with SSH keys held on hardware security keys, and GitHub
marks them **Verified**. The public keys are in [allowed_signers](allowed_signers) and on each
maintainer's GitHub account (`https://api.github.com/users/<login>/ssh_signing_keys`); compare the
two before trusting either. To check signatures yourself, without GitHub:

```sh
git -c gpg.ssh.allowedSignersFile=allowed_signers log --show-signature
git -c gpg.ssh.allowedSignersFile=allowed_signers verify-commit <commit>
```

| Maintainer | Key | Fingerprint |
|---|---|---|
| elasticgh | elasticgh-bio | `SHA256:GcqSpLcrUmf2I2KZGM3CxuivEIKxjS9DrTv3AFTbTaE` |
| elasticgh | elasticgh-5c-main | `SHA256:mD5lKkUg0b1eUuPwjSpFZ0lvyWnfG5/FX92w93Y/ae0` |
| elasticgh | elasticgh-5c-backup | `SHA256:rfG5ca1QB7+0zGtlwZY8cOHdnsgB08eR26ZNxZzbVLw` |

A changed `allowed_signers` is reviewed like any other change: a key added there proves nothing
until it also appears on that maintainer's GitHub account.
