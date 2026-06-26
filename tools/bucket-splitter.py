#!/usr/bin/env python3
"""
Bucket Splitter — Analyze and split LLM skill files for Bucket Streaming.

Usage:
    python bucket-splitter.py /path/to/skill          # Analyze only
    python bucket-splitter.py /path/to/skill --merge  # Analyze + merge into buckets
"""

import os
import re
import sys
import argparse
from collections import defaultdict

TOKEN_RATIO = 1.8  # chars per token (mixed Chinese/English)
SOFT_LIMIT = 18000  # recommended max tokens per bucket
HARD_LIMIT = 25000  # hard max (needs offset reads)


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

    # Check if split produces acceptable sizes
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
        # Skip buckets directory and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'buckets']
        for f in files:
            if f.endswith('.md') or f.endswith('.yaml'):
                md_files.append(os.path.join(root, f))
    return sorted(md_files)


def main():
    parser = argparse.ArgumentParser(
        description='Bucket Splitter — analyze and merge LLM skill files for Bucket Streaming'
    )
    parser.add_argument('skill_dir', help='Path to skill directory')
    parser.add_argument('--merge', action='store_true', help='Also merge files into buckets')
    parser.add_argument('--flow', default='config/flow.yaml', help='Path to flow definition (relative to skill dir)')
    args = parser.parse_args()

    skill_dir = os.path.abspath(args.skill_dir)

    print("=" * 60)
    print("Bucket Splitter v1.0")
    print(f"Skill: {skill_dir}")
    print("=" * 60)

    # Scan files
    files = scan_skill_directory(skill_dir)
    print(f"\nFound {len(files)} source files.\n")

    # Analyze
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

    # Check oversized files
    oversized = {fp: info for fp, info in results.items()
                 if info['tokens'] > SOFT_LIMIT}

    if oversized:
        print("\n" + "=" * 60)
        print("Split Suggestions")
        print("=" * 60)

        for fp, info in oversized.items():
            rel = os.path.relpath(fp, skill_dir)
            boundaries = find_section_boundaries(fp)
            split = suggest_split(info, boundaries)

            if split:
                print(f"\n  {rel} ({info['tokens']} tokens → must split)")
                print(f"    Suggested split at line {split['line']}:")
                print(f"    {split['header']}")
                print(f"    → Before: ~{split['before_tokens']} tokens")
                print(f"    → After:  ~{split['after_tokens']} tokens")
            else:
                print(f"\n  {rel} ({info['tokens']} tokens)")
                print(f"    ⚠️ No natural split point found. Manual split required.")
                print(f"    Section boundaries found: {len(boundaries)}")

    # Suggest bucket groupings
    print("\n" + "=" * 60)
    print("Bucket Grouping (manual review recommended)")
    print("=" * 60)
    print("""
  Guidelines:
  - Each bucket: 3-8 consecutive flow steps, <18K tokens
  - Split at semantic boundaries (phase transitions, user interaction points)
  - Merge related templates/judges into the bucket where they're used
  - Keep flow.yaml and global rules as Resident Layer (not a bucket)
""")

    if args.merge:
        print("\n" + "=" * 60)
        print("Merge mode not yet implemented.")
        print("Create bucket files manually following the suggestions above.")
        print("=" * 60)

    print(f"\nFull protocol: https://github.com/xxx/bucket-streaming/blob/main/SPEC.md")


if __name__ == '__main__':
    main()
