"""Compare two slopscope runs: measure.json before and after, and optionally their screenshots.

    python3 compare.py BEFORE.json AFTER.json [--shots-before DIR --shots-after DIR] [--out compare.md]

Prints a Markdown table. Checks that got worse come first; a check that newly
fails is marked REGRESSION. With screenshots, reports the changed area of each
<viewport>-<theme>.png pair (or a size change). Exit code 1 when a check regressed.
"""
import argparse
import json
import pathlib
import sys

from PIL import Image, ImageChops


def load(path):
    data = json.loads(pathlib.Path(path).read_text())
    return {c['id']: c for c in data['checks']}


def compare(before, after):
    rows = []
    for check_id in sorted(set(before) | set(after)):
        b, a = before.get(check_id), after.get(check_id)
        if not b or not a or a['status'] == 'info':
            continue
        nb, na = len(b['findings']), len(a['findings'])
        if b['status'] == 'pass' and a['status'] == 'fail':
            verdict = 'REGRESSION'
        elif na > nb:
            verdict = 'worse'
        elif na < nb:
            verdict = 'better'
        else:
            verdict = 'same'
        rows.append((check_id, b['status'], nb, a['status'], na, verdict))
    order = {'REGRESSION': 0, 'worse': 1, 'same': 2, 'better': 3}
    rows.sort(key=lambda r: (order[r[5]], r[0]))
    return rows


def compare_shots(before_dir, after_dir):
    rows = []
    for b in sorted(pathlib.Path(before_dir).glob('*.png')):
        a = pathlib.Path(after_dir) / b.name
        if not a.exists():
            rows.append((b.name, 'missing after'))
            continue
        ib, ia = Image.open(b).convert('RGB'), Image.open(a).convert('RGB')
        if ib.size != ia.size:
            rows.append((b.name, f'size {ib.size[0]}x{ib.size[1]} -> {ia.size[0]}x{ia.size[1]}'))
            continue
        box = ImageChops.difference(ib, ia).getbbox()
        rows.append((b.name, 'identical' if not box else f'changed in x {box[0]}-{box[2]}, y {box[1]}-{box[3]}'))
    return rows


def markdown(rows, shots=None):
    lines = ['| Check | Before | After | Result |', '|---|---|---|---|']
    lines += [f'| {r[0]} | {r[1]} ({r[2]}) | {r[3]} ({r[4]}) | {r[5]} |' for r in rows]
    if shots:
        lines += ['', '| Screenshot | Difference |', '|---|---|'] + [f'| {n} | {d} |' for n, d in shots]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('before'); parser.add_argument('after')
    parser.add_argument('--shots-before'); parser.add_argument('--shots-after')
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    rows = compare(load(args.before), load(args.after))
    shots = compare_shots(args.shots_before, args.shots_after) if args.shots_before and args.shots_after else None
    text = markdown(rows, shots)
    if args.out:
        pathlib.Path(args.out).write_text(text)
    print(text, end='')
    return 1 if any(r[5] == 'REGRESSION' for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
