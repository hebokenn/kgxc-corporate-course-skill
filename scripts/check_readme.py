#!/usr/bin/env python3
"""Require the README version history to be its final top-level section."""
import argparse
from pathlib import Path
import re
import sys
from typing import NamedTuple


class ReadmeStructureError(ValueError):
    pass


class Heading(NamedTuple):
    level: int
    title: str
    line: int


def headings(text):
    """Read ATX/Setext headings, ignoring fenced/indented code and comments."""
    fence = None
    comment = False
    previous = None
    for number, raw in enumerate(text.splitlines(), 1):
        if fence:
            char, size = fence
            if re.fullmatch(r' {0,3}' + re.escape(char) + '{' + str(size) + r',}[ \t]*', raw):
                fence = None
            continue

        line = ''
        remainder = raw
        while remainder:
            if comment:
                end = remainder.find('-->')
                if end < 0:
                    break
                remainder = remainder[end + 3:]
                comment = False
            else:
                start = remainder.find('<!--')
                if start < 0:
                    line += remainder
                    break
                line += remainder[:start]
                remainder = remainder[start + 4:]
                comment = True

        opening = re.match(r' {0,3}(`{3,}|~{3,})(.*)$', line)
        if opening:
            fence = (opening[1][0], len(opening[1]))
            previous = None
            continue
        if not line.strip() or line.startswith(('    ', '\t')):
            previous = None
            continue
        atx = re.match(r' {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)$', line)
        if atx:
            title = re.sub(r'[ \t]+#+[ \t]*$', '', atx[2] or '').strip()
            yield Heading(len(atx[1]), title, number)
            previous = None
            continue
        setext = re.fullmatch(r' {0,3}(=+|-+)[ \t]*', line)
        if setext and previous:
            title, start = previous
            yield Heading(1 if setext[1][0] == '=' else 2, title, start)
            previous = None
            continue
        if re.match(r' {0,3}(?:>|[-+*][ \t]|\d+[.)][ \t]|\|)', line):
            previous = None
        else:
            previous = (line.strip(), number)


def check_readme(path):
    path = Path(path)
    found = list(headings(path.read_text(encoding='utf-8-sig')))
    history = [h for h in found if h.level == 2 and h.title.strip('*_`') == '版本更新']
    if not history:
        raise ReadmeStructureError('缺少二级章节“## 版本更新”；请将版本记录放在主页介绍之后。')
    if len(history) != 1:
        lines = '、'.join(str(h.line) for h in history)
        raise ReadmeStructureError(f'“版本更新”二级章节重复（第 {lines} 行）；主页只能保留一个版本更新章节。')
    final = history[0]
    later = next((h for h in found if h.line > final.line and h.level <= 2), None)
    if later:
        raise ReadmeStructureError(
            f'版本更新必须放在主页最后：第 {final.line} 行的“版本更新”之后，'
            f'第 {later.line} 行还有章节“{later.title}”。请将该章节移到“版本更新”之前。'
        )
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readme', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'README.md')
    args = parser.parse_args()
    try:
        final = check_readme(args.readme)
    except (ReadmeStructureError, OSError, UnicodeError) as error:
        print(f'{args.readme}: {error}', file=sys.stderr)
        return 1
    print(f'README 检查通过：“版本更新”位于最后（第 {final.line} 行）。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
