# Healthomics Custom Delta (Fork Strategy)

This repository (`peterbb148/awslabs-mcp`) tracks upstream `awslabs/mcp` and carries a custom Healthomics feature delta that is not yet merged upstream.

## Source of Truth Layers

1. Upstream base: `awslabs/mcp` `main`
2. Custom layer: Healthomics store and Lambda/API integration features maintained in this fork
3. Bugfix layer: small issue-specific fixes on top of the custom layer

## Baseline Tag

A baseline tag is used to anchor future bugfix work to a known-good custom state:

- Tag: `healthomics-custom-baseline-2026-02-17`
- Purpose: stable base for issue branches after upstream sync

## Branching Rules

1. Do not start bugfix work directly from `main` after upstream sync if custom layer is not present.
2. Start bugfix branches from the current custom baseline tag (or its successor).
3. Keep bugfix PRs minimal and issue-scoped; avoid mixing upstream sync + custom feature reintroduction + bugfix in one PR.
4. If upstream sync is needed, do it as a dedicated PR first.
5. If custom feature reapplication is needed, do it as a dedicated PR second.
6. Apply bugfixes as a third, small PR.

## Practical Workflow

1. Sync fork with upstream in a dedicated branch/PR.
2. Reapply or merge custom Healthomics layer in a dedicated branch/PR.
3. Tag resulting commit as next `healthomics-custom-baseline-*`.
4. Create issue branches from that tag for bugfixes.

This process keeps diffs reviewable and reduces version-mesh regressions.
