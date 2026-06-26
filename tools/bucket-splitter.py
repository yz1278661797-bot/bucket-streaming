#!/usr/bin/env python3
"""
Bucket Splitter — Analyze and split LLM skill files for Bucket Streaming.

Usage:
    python bucket-splitter.py /path/to/skill          # Analyze only
    python bucket-splitter.py /path/to/skill --merge  # Analyze + merge into buckets
    python bucket-splitter.py /path/to/skill --merge --force  # Skip confirmation
"""

import os
import re
import sys
import argparse
from collections import defaultdict

TOKEN_RATIO = 1.8   # chars per token (mixed Chinese/English)
SOFT_LIMIT = 18000   # recommended max tokens per bucket
HARD_LIMIT = 25000   # hard max (needs offset reads)

BUCKET_HEADER = """<!-- Bucket Streaming v1.0 -->
<!-- File: {filename} -->
<!-- SELF-CHECK: If you see this line without upstream bucket output, STOP and request upstream. -->

"""


def count_tokens(text):
    return len(text) / TOKEN_RATIO


def analyze_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    chars = len(content)
    tokens = count_tokens(content)
    return {
        'path': filepath,
        'name': os.path.basename(filepath),
        'chars': chars,
        'tokens': int(tokens),
        'lines': len(lines),
        'content': content,
        'lines_list': lines,
    }


def find_section_boundaries(filepath):
    """Find markdown section headers as natural split candidates."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    boundaries = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('### ') or stripped.startswith('## '):
            boundaries.append({
                'line': i + 1,
                'header': stripped,
                'level': 3 if stripped.startswith('### ') else 2,
            })
    return boundaries


def suggest_split(file_info, boundaries):
    """Suggest a split point that creates two balanced chunks."""
    total_lines = file_info['lines']
    target_mid = total_lines // 2

    best = None
    best_dist = float('inf')
    for b in boundaries:
        dist = abs(b['line'] - target_mid)
        if dist < best_dist:
            best_dist = dist
            best = b

    if best is None:
        return None

    before_chars = len(''.join(file_info['lines_list'][:best['line']]))
    after_chars = len(''.join(file_info['lines_list'][best['line']:]))
    before_tokens = int(before_chars / TOKEN_RATIO)
    after_tokens = int(after_chars / TOKEN_RATIO)

    return {
        'line': best['line'],
        'header': best['header'],
        'before_tokens': before_tokens,
        'after_tokens': after_tokens,
        'before_chars': before_chars,
        'after_chars': after_chars,
    }


def scan_skill_directory(skill_dir):
    """Find all markdown files in a skill directory."""
    md_files = []
    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'buckets']
        for f in files:
            if f.endswith('.md') or f.endswith('.yaml'):
                md_files.append(os.path.join(root, f))
    return sorted(md_files)


def write_bucket(output_dir, filename, sections):
    """Write a bucket file with header and merged sections."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)

    parts = [BUCKET_HEADER.format(filename=filename)]
    for label, content in sections:
        parts.append(f"<!-- === {label} === -->\n\n")
        parts.append(content)
        if not content.endswith('\n'):
            parts.append('\n')
        parts.append('\n')

    result = ''.join(parts)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(result)
    return path, len(result)


def interactive_merge(skill_dir, results, oversized_splits):
    """Interactive mode: user decides bucket groupings."""
    print("\n" + "=" * 60)
    print("Interactive Merge")
    print("=" * 60)
    print("\nEnter bucket definitions. Format: bucket_id: file1 file2 ...")
    print("Use 'file.md:L1-L500' for split ranges. Example:")
    print("  A: module_01.md module_02.md")
    print("  B1: module_03.md:L1-L800")
    print("  B2: module_03.md:L801-L1600")
    print("  C: template.md judge_a.md judge_b.md")
    print("\nAvailable files:")
    for fp, info in sorted(results.items()):
        rel = os.path.relpath(fp, skill_dir)
        print(f"  {rel:<50} ~{info['tokens']:>6} tokens  ({info['lines']} lines)")

    if oversized_splits:
        print("\nSuggested splits for oversized files:")
        for fp, split in oversized_splits.items():
            rel = os.path.relpath(fp, skill_dir)
            print(f"  {rel}:")
            print(f"    Part 1: L1-L{split['line']} ~{split['before_tokens']} tokens")
            print(f"    Part 2: L{split['line']}-end ~{split['after_tokens']} tokens")
            print(f"    Split at: {split['header']}")

    print("\nEnter definitions (empty line to finish):")
    buckets = {}
    while True:
        try:
            line = input().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        if ':' not in line:
            print("  Format: bucket_id: file1 file2 ...")
            continue
        bucket_id, _, files_str = line.partition(':')
        bucket_id = bucket_id.strip()
        file_specs = [f.strip() for f in files_str.split() if f.strip()]
        if bucket_id and file_specs:
            buckets[bucket_id] = file_specs

    return buckets


def auto_merge(skill_dir, results, oversized_splits):
    """Auto-group files into buckets based on size and sequential order."""
    buckets = {}
    bucket_id_char = ord('A')
    current_bucket = []
    current_tokens = 0

    # First, handle oversized files — split them and add as separate buckets
    handled_paths = set(oversized_splits.keys()) if oversized_splits else set()

    for fp, split in (oversized_splits or {}).items():
        rel = os.path.relpath(fp, skill_dir)
        base_name = os.path.splitext(os.path.basename(fp))[0]
        b1_id = f"{chr(bucket_id_char)}1"
        b2_id = f"{chr(bucket_id_char)}2"
        bucket_id_char += 1

        # Split the file
        with open(fp, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        part1 = ''.join(lines[:split['line']])
        part2 = ''.join(lines[split['line']:])

        buckets[b1_id] = [(fp, rel, part1, f"{base_name} (L1-L{split['line']})")]
        buckets[b2_id] = [(fp, rel, part2, f"{base_name} (L{split['line']}-end)")]

    # Now group remaining files into buckets by size
    remaining = [(fp, info) for fp, info in sorted(results.items())
                 if fp not in handled_paths]

    for fp, info in remaining:
        rel = os.path.relpath(fp, skill_dir)
        content = info['content']

        if current_tokens + info['tokens'] > SOFT_LIMIT and current_bucket:
            # Flush current bucket
            bid = chr(bucket_id_char)
            bucket_id_char += 1
            buckets[bid] = current_bucket
            current_bucket = []
            current_tokens = 0

        current_bucket.append((fp, rel, content, info['name']))
        current_tokens += info['tokens']

    # Flush last bucket
    if current_bucket:
        bid = chr(bucket_id_char)
        buckets[bid] = current_bucket

    return buckets


def do_merge(skill_dir, results, oversized_splits, force=False):
    """Execute the merge: write bucket files to buckets/ directory."""
    if not force:
        buckets = interactive_merge(skill_dir, results, oversized_splits)
        if not buckets:
            print("\nNo buckets defined. Merge aborted.")
            return
    else:
        buckets = auto_merge(skill_dir, results, oversized_splits)
        if not buckets:
            print("\nCannot auto-merge. Try interactive mode (remove --force).")
            return

    output_dir = os.path.join(skill_dir, 'buckets')
    print(f"\nWriting {len(buckets)} buckets to {output_dir}/ ...\n")

    for bucket_id, sections in sorted(buckets.items()):
        # sections is list of (fp, rel_path, content, label)
        section_pairs = [(label, content) for _, _, content, label in sections]
        filename = f"bucket-{bucket_id}.md"
        path, chars = write_bucket(output_dir, filename, section_pairs)
        tokens = int(chars / TOKEN_RATIO)
        flag = ' ⚠️ >20K' if tokens > 20000 else ''
        flag = ' 🔴 >25K' if tokens > HARD_LIMIT else flag
        print(f"  {filename:<30} {chars:>8} chars  ~{tokens:>6} tokens{flag}")

    print(f"\nDone. {len(buckets)} bucket files written.")
    print("Next: copy the scheduler from TEMPLATE.md into your SKILL.md")


def main():
    parser = argparse.ArgumentParser(
        description='Bucket Splitter — analyze and merge LLM skill files for Bucket Streaming'
    )
    parser.add_argument('skill_dir', help='Path to skill directory')
    parser.add_argument('--merge', action='store_true', help='Merge files into bucket files')
    parser.add_argument('--force', action='store_true', help='Skip confirmation (auto-merge)')
    args = parser.parse_args()

    skill_dir = os.path.abspath(args.skill_dir)

    print("=" * 60)
    print("Bucket Splitter v1.1")
    print(f"Skill: {skill_dir}")
    print("=" * 60)

    # Scan and analyze
    files = scan_skill_directory(skill_dir)
    print(f"\nFound {len(files)} source files.\n")

    results = {}
    total_tokens = 0
    for fp in files:
        info = analyze_file(fp)
        results[fp] = info
        total_tokens += info['tokens']
        rel_path = os.path.relpath(fp, skill_dir)
        flag = ' ⚠️ >20K' if info['tokens'] > 20000 else ''
        flag = ' 🔴 >25K' if info['tokens'] > HARD_LIMIT else flag
        print(f"  {rel_path:<45} {info['chars']:>8} chars  ~{info['tokens']:>6} tokens{flag}")

    print(f"\n  {'TOTAL':<45} {total_tokens:>8} tokens")

    # Find oversized files and suggest splits
    oversized = {fp: info for fp, info in results.items()
                 if info['tokens'] > SOFT_LIMIT}
    oversized_splits = {}

    if oversized:
        print("\n" + "=" * 60)
        print("Split Suggestions")
        print("=" * 60)

        for fp, info in oversized.items():
            rel = os.path.relpath(fp, skill_dir)
            boundaries = find_section_boundaries(fp)
            split = suggest_split(info, boundaries)

            if split:
                oversized_splits[fp] = split
                print(f"\n  {rel} ({info['tokens']} tokens → must split)")
                print(f"    Split at line {split['line']}: {split['header']}")
                print(f"    → Part 1: ~{split['before_tokens']} tokens")
                print(f"    → Part 2: ~{split['after_tokens']} tokens")
            else:
                print(f"\n  {rel} ({info['tokens']} tokens)")
                print(f"    ⚠️ No natural split point found. Manual split required.")
                print(f"    Section boundaries found: {len(boundaries)}")

    # Run merge if requested
    if args.merge:
        do_merge(skill_dir, results, oversized_splits, force=args.force)

    print(f"\nFull protocol: https://github.com/yz1278661797-bot/bucket-streaming/blob/main/SPEC.md")


if __name__ == '__main__':
    main()
