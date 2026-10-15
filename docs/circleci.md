# CircleCI pilot for the Raiz fork

The pilot adds Linux/Python 3.12 checks to this active fork. The [CircleCI project](https://app.circleci.com/settings/project/circleci/Kft4WUkquJMEhmT93kCpcX/17080df8-a7d0-40fa-a35a-353ed9db9f1c) is connected through the GitHub App with one **All pushes** trigger and VCS status updates enabled. Every GitHub Actions workflow stays enabled; this is not a complete replacement of the existing multi-platform CI or its release and analysis integrations. A successful cloud run is required before changing required checks.

| Existing CI check | CircleCI job | Scope |
| --- | --- | --- |
| Lock drift, Ruff, format, Bandit, labels and CodeRabbit manifests | `quality` | Same commands, including the pinned Bandit pre-commit hook |
| Types with and without the optional Neo4j driver | `quality` | Same extras and both `ty` passes |
| Base-install unit suite | `unit-base` | Full non-integration suite on the test/dev dependencies only |
| Full-extra unit suite | `unit-full` | Full non-integration suite with treesitter-full, semantic, milvus, test and Neo4j extras |
| Integration suite and coverage | `integration` | Machine executor with a local Docker daemon; the existing fixtures own Memgraph, Neo4j and other test containers |
| Standalone binary smoke | `packaging-and-go` | PyInstaller build and CLI version check |
| Wheel smoke with unlocked dependencies | `packaging-and-go` | Wheel installed with pip into a fresh environment; smoke runs outside the source checkout |
| Go frontend | `packaging-and-go` | Go 1.26.6 from `go.mod`, checksum-verified download, explicit build and existing tests |

The Python 3.13 and macOS/Windows unit matrix remains on GitHub Actions, as do its Codecov uploads. SonarCloud analysis and its zero-issue gate, PR-title checks, security scans, AI reviews, label synchronization, version bumps, PyPI/GHCR publication, binary releases and documentation build/deploy also stay there. Their tokens and GitHub permissions are not copied to CircleCI. The upstream SonarCloud project and badges are not CircleCI results for this fork.

## Runtime and resources

Docker jobs use `cimg/base:2026.10-24.04`, which includes Git/SSH/curl for checkout. Every job installs Python 3.12.14 through `uv==0.12.6` and uses `uv sync --frozen`. Commands after extras are installed use `uv run --no-sync`, preserving the selected dependency set. Wheel installation deliberately resolves production dependencies independently of `uv.lock`, matching the existing fresh-resolution smoke check.

Quality and base unit tests use Docker Medium (2 CPUs, 4 GB). Full unit tests and packaging use Docker Large (4 CPUs, 8 GB); both unit jobs run two workers. Integration uses machine Large gen1 (4 CPUs, 15 GB) for Python plus the graph containers, without Docker Layer Caching or remote Docker. The machine image alias `ubuntu-2404:current` can change; the Python and Go toolchains remain explicitly pinned.

All test/packaging jobs provision the language tools present on the existing GitHub Ubuntu runner: JDK 17, .NET SDK 8.0.426 and 10.0.402, Node 22.23.3/npm, Rust 1.99.0, Go 1.26.6, PHP 8.3/Xdebug/PHPUnit and native C/C++/CMake. JDK and PHP come from Ubuntu's signed repositories; Go, Node, rustup 1.29.1 and .NET downloads are checked against their publishers' SHA-256/SHA-512 digests. SDK 8 provides the Roslyn target runtime; SDK 10 supports the solution format used by the tests. The Java and Roslyn helpers are explicitly compiled before pytest, so an unavailable compiler/build cannot silently turn their tests into skips. This adds installation time to every cold test job but preserves the existing Linux language coverage.

JUnit still needs inspection for the suite's explicit platform/optional-dependency and unavailable live-provider skips. The base-install job intentionally lacks optional grammars/backends. Dart, Scala, native Lua, `tsc` and `dotnet-trace` are not installed by the GitHub workflow or confirmed in its standard runner inventory; this pilot does not add those optional tools. Public NuGet, crates.io, npm and model downloads remain network dependencies.

Only the existing public `microsoft/unixcoder-base` model cache is retained. Model prefetch has retries and a wall-clock timeout; no API token is required. There is no environment, dependency, Docker-layer or build cache. Test JUnit and integration coverage are diagnostic results, not a published release artifact.

Installs, checks, tests and packaging have wall-clock limits. CircleCI plan job limits still apply to their total duration. Full extras include large model/runtime dependencies, so first-run duration and credits must be measured rather than extrapolated from the PC or other repositories. Keep the current GitHub checks until the pilot proves coverage and acceptable resource use.

## Project activation

1. Keep configuration, checkout and event sources on `raiz-brasil/code-graph-rag` and `.circleci/config.yml` in the existing GitHub App pipeline.
2. Keep the existing **All pushes** trigger, without an additional PR trigger for the same commits. Verify branch pushes for pull requests and `main` produce the expected statuses.
3. In Project Settings → Advanced, enable **Auto-cancel redundant workflows**.
4. Run the PR branch and `main`, inspect all five job results and JUnit skips, and record actual credit/memory use. Preserve the GitHub matrix and authenticated integrations until each boundary is explicitly migrated.

The CircleCI checkout tests branch HEAD; GitHub `pull_request` normally checks a synthetic merge with its base. Resolve that difference before cutover. Fork pull requests do not execute through this GitHub App integration and need a separate validation path. Observe the actual `ci/circleci: ...` status names before configuring branch protection; do not require a new status until it has run successfully.

## Secrets

The CircleCI jobs need no project secrets or contexts. The source, grammars, model and language toolchain downloads are public; the checkout integration needs only access to this repository. Do not copy application/provider credentials or operational tokens into these jobs.

Existing GitHub-only names include `CODECOV_TOKEN`, `SONAR_TOKEN`, `SCORECARD_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `VERSION_BUMP_SSH_KEY`, `HIGHLIGHTS_API_TOKEN`, `HIGHLIGHTS_API_URL`, `HIGHLIGHTS_RESOLVE` and the workflow-scoped `GITHUB_TOKEN`. Some upstream integrations may not be provisioned for this fork; retaining their workflows does not imply those credentials or external projects are configured.

Validate with `circleci config validate .circleci/config.yml`. The pilot does not publish packages, push version changes, upload remote analysis, expose a graph database or contact Raiz production services.
