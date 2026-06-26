# Changelog

## [1.1] - 2026-06-27

### Added
- `--merge` mode in `bucket-splitter.py` (interactive + `--force` auto-merge)
- `CONTRIBUTING.md`

### Changed
- `bucket-splitter.py` now writes self-check headers on merge

## [1.0] - 2026-06-27

### Added
- Initial specification (SPEC.md v1.0)
- Bucket lifecycle table with prefetch/release rules
- State tracking protocol (`<bs-state>` tag)
- Jump-back matrix for user-initiated rollbacks
- Bucket self-check header mechanism
- `bucket-splitter.py` analysis tool
- `example-data-analysis/` minimal 4-step pipeline
- `TEMPLATE.md` copy-paste-ready scheduler
