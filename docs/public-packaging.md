# Public packaging verification

Version 0.4.0 uses `criad-com` for the public family org. The OpenUSD source
input uses its upstream repository at the existing revision. All dependency
revisions, native recipes and build patches are unchanged.

## OpenUSD source comparison

On 2026-09-12, the pinned commit was fetched from the deployment Gitea mirror
into an isolated bare repository sharing the existing upstream clone's objects.
The upstream clone's remote is `https://github.com/PixarAnimationStudios/OpenUSD.git`;
the pinned commit is an ancestor of its `origin/dev` at
`0ace5b88702edbfe00dd031369f38ff526cb07b8`.

| Comparison | Result |
|---|---|
| Upstream pinned commit | `47154dc7b5e28df623745495a7a508b69535ba24` |
| Mirror FETCH_HEAD | `47154dc7b5e28df623745495a7a508b69535ba24` |
| Upstream and mirror tree | `42262f741dd876c666295635bdd68a59a4b4bd3f` |
| `git diff --stat <upstream-pin> FETCH_HEAD` | Empty: 0 changed files |
| `git diff --exit-code <upstream-pin> FETCH_HEAD` | Exit 0 |

There are **no local patches in the mirror at the pin**. The public input is
therefore `github:PixarAnimationStudios/OpenUSD?rev=47154dc7b5e28df623745495a7a508b69535ba24`.
The Gitea URL belongs only in an external deployment registry. This comparison
uses the local upstream clone's history; it does not claim a fresh public fetch.

The hub separately ships four existing build patches under `patches/`:
the generic Work parallel-loop fix, monolithic custom-Work target visibility,
HdEmbree's custom-Work include guard, and the MSVC empty-export fix. These
remain unchanged and do not alter the verbatim `openusd-src` package.

## Licence and deployment

The starting tree had no root LICENSE file. Version 0.4.0 adds the complete
MIT packaging licence. The IfcOpenShell notice and copied OpenUSD CMake files
are unchanged. The README Licence section records the dependency terms.

The committed registry is now a public template. Set `AECO_NIX_REGISTRY` to
an external deployment copy to select Gitea and local caches; see the README.
The term sweep includes the committed registry and allows the exact public
org slug and root licence copyright line, with no whole-file address exception.

## Validation

Measured on 2026-09-12 with the supplied Python environment. The single Nix
attempt used the external deployment registry and the implementation at
`c5db75f`; only documentation changed after it.

| Acceptance | Result |
|---|---|
| Source `check.py` | **3 checks, 0 failed** |
| Hub conventions linter | Clean |
| pytest | **55 passed, 1 skipped**, 11 subtests passed |
| Term sweep | **0 findings**, including the public registry |
| Old public-org references | **0** across all tracked text files, including registry owners |
| Third-party notices, CMake copies and build patches | **25/25 files byte-identical** to the starting tree |
| Dependency commit pins | All unchanged |
| OpenUSD mirror diff | **0 changed files**, identical commit and tree |
| Nix flake check | **NOT PROVEN**: one attempt, interrupted after **48.91 s**, exit 1 |

The Nix command was:

```sh
env -u PYTHONPATH "$PYTHON" tools/nix-local.py flake check \
  --offline -L --max-jobs 4 --cores 6
```

Input resolution succeeded and all **10** aarch64-darwin check derivations
evaluated. Missing build dependencies then triggered source-fetch builders.
Despite `--offline`, these builders contacted public download servers; the
attempt was stopped when that appeared because those endpoints were outside
the allowed network scope. No second attempt was made. This run does not prove
the checks built or passed, nor that the public inputs can be fetched fresh.
The historical native build measurements remain in
[native verification](native-verification.md).

## Deviations

- This generic processing hub retains its own conventions linter; it does
  not carry the family schema skeleton or a `usdaeco-toolchain` dependency pin.
- The requested root licence was absent, rather than Apache-2.0, in the starting
  tree. No third-party licence was replaced.
- The explicit release target is 0.4.0; the starting tree recorded its latest
  changes under Unreleased without a package-level semantic version.
- The optional `aeco-core` consumer test remains skipped because that sibling
  checkout is absent. No native execution or public input fetch is claimed
  from this release's interrupted Nix attempt.
- Merging and creating the `v0.4.0` tag on main are reviewer actions.
