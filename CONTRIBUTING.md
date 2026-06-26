# Contributing

Thanks for your interest in Bucket Streaming.

## How to Contribute

1. **Open an issue first.** Describe what you want to change or add before writing code. This saves time on both sides.
2. **Keep it focused.** One PR = one logical change. Bug fixes, features, and docs changes go in separate PRs.
3. **Follow the SPEC.** All changes must align with [SPEC.md](SPEC.md). If you want to change the protocol itself, open a discussion issue with the tag "spec-change".

## Development

```bash
git clone https://github.com/yz1278661797-bot/bucket-streaming.git
cd bucket-streaming

# Test the splitter on the example
python tools/bucket-splitter.py example-data-analysis
python tools/bucket-splitter.py example-data-analysis --merge --force
```

## What We're Looking For

- `bucket-splitter.py` improvements (especially better auto-merge heuristics)
- Additional example skills (demonstrating different flow topologies)
- Language ports of the splitter tool
- Documentation improvements and translations
- Real-world case studies using Bucket Streaming

## Code Style

- Python: keep it readable. No external dependencies.
- Markdown: wrap at 100 characters where practical.
- Commit messages: imperative mood, short first line (e.g., `Add interactive mode to splitter`).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
