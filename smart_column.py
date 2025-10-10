#!/usr/bin/env python3
# smart_column.py
# A "column -s" replacement that preserves emojis and OSC 8 hyperlinks,
# aligns by *display width*, and ignores ANSI escapes for width calculations.
#
# Usage examples:
#   cat data.tsv | smart_column.py -s $'\t' -t
#   cat data.csv | smart_column.py -s ',' -t --header
#   cmd | smart_column.py -s '|' -t --right '3,5'     # right-align columns 3 and 5 (1-based)
#   cmd | smart_column.py -s $'\t' -t --num-right     # right-align cells that look numeric
#
# Notes:
# - Keeps all ANSI color codes and OSC 8 hyperlinks in the output, but strips them for width calc.
# - For maximum emoji accuracy, this script tries to import 'wcwidth'. If unavailable,
#   it falls back to a solid heuristic using unicodedata (combining + East Asian width + emoji tweaks).
#
# MIT License

import sys
import os
import signal
import re
import argparse
import unicodedata

# --- ANSI / OSC 8 handling ---
# CSI (color etc.): ESC [ ... cmd
CSI_RE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
# OSC 8 hyperlinks: ESC ] 8 ; params ; URI ST   ... TEXT ...   ESC ] 8 ; ; ST
# We need to *remove* the open/close sequences for width calc but leave TEXT intact.
OSC8_OPEN_RE = re.compile(r'\x1b\]8;[^\\]*\\')
OSC8_CLOSE_RE = re.compile(r'\x1b\]8;;\\')

def strip_control_for_width(s: str) -> str:
    # Remove only the control sequences, not the link text
    s = OSC8_OPEN_RE.sub('', s)
    s = OSC8_CLOSE_RE.sub('', s)
    s = CSI_RE.sub('', s)
    return s

# --- wcwidth / wcswidth ---
def _fallback_wcwidth(char: str) -> int:
    # Combining marks (including ZWJ) have zero width
    if unicodedata.combining(char):
        return 0
    # Zero width joiner (U+200D)
    if ord(char) == 0x200D:
        return 0
    # Variation selectors (U+FE00..U+FE0F) => zero width
    if 0xFE00 <= ord(char) <= 0xFE0F:
        return 0
    # Treat non-spacing marks as zero width
    cat = unicodedata.category(char)
    if cat in ('Mn', 'Me', 'Cf'):
        # NB: consider most format chars zero-width. OSC/CSI were already stripped.
        return 0
    # East Asian Width: F/W => 2; A/N/H/Na => 1 (terminals often treat Ambiguous as 1)
    eaw = unicodedata.east_asian_width(char)
    if eaw in ('F', 'W'):
        return 2
    # Common emoji base characters generally render as width 2.
    # A lightweight heuristic: characters in the Emoji_Presentation block tend to be wide.
    # Without the emoji property, we approximate via a few ranges.
    o = ord(char)
    if (
        0x1F300 <= o <= 0x1F5FF or   # Misc Symbols and Pictographs
        0x1F600 <= o <= 0x1F64F or   # Emoticons
        0x1F680 <= o <= 0x1F6FF or   # Transport and Map
        0x1F900 <= o <= 0x1F9FF or   # Supplemental Symbols and Pictographs
        0x1FA70 <= o <= 0x1FAFF or   # Symbols and Pictographs Extended-A
        0x2600  <= o <= 0x26FF  or   # Misc symbols
        0x2700  <= o <= 0x27BF       # Dingbats
    ):
        return 2
    # Default
    return 1

try:
    # Use wcwidth if available
    from wcwidth import wcswidth as _lib_wcswidth, wcwidth as _lib_wcwidth
    def wcswidth(s: str) -> int:
        return _lib_wcswidth(s)
    def wcwidth(c: str) -> int:
        return _lib_wcwidth(c)
    _USING_LIB_WCWIDTH = True
except Exception:
    def wcwidth(c: str) -> int:
        return _fallback_wcwidth(c)
    def wcswidth(s: str) -> int:
        width = 0
        for ch in s:
            w = wcwidth(ch)
            if w < 0:
                return -1
            width += w
        return width
    _USING_LIB_WCWIDTH = False

# Numeric detection
NUM_RE = re.compile(r'^[ \t]*[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?[ \t]*$')

def looks_numeric(s: str) -> bool:
    return bool(NUM_RE.match(s))

def parse_args():
    ap = argparse.ArgumentParser(description="ANSI/OSC8/emoji-aware column formatter")
    ap.add_argument('-s', '--separator', required=True, help="Input field separator (single character or escape, e.g. $'\\t')")
    ap.add_argument('-t', '--table', action='store_true', help="Format as a table (align columns)")
    ap.add_argument('--header', action='store_true', help="Treat first row as header and draw a separator rule")
    ap.add_argument('--right', default='', help="Comma-separated 1-based column indices to right-align (e.g. '3,5')")
    ap.add_argument('--num-right', action='store_true', help="Right-align cells that look numeric")
    ap.add_argument('--pad', type=int, default=2, help="Spaces between columns (default: 2)")
    ap.add_argument('--no-trim', action='store_true', help="Do not trim outer whitespace on fields")
    ap.add_argument('--collapse', action='store_true', help="Collapse repeated separators (treat as regex +)")
    ap.add_argument('--debug-width', action='store_true', help="Print computed widths to stderr for debugging")
    return ap.parse_args()

def decode_separator(raw: str) -> str:
    # Allow bash-style $'\t' or escaped sequences like '\t'
    if raw.startswith("$'") and raw.endswith("'"):
        body = raw[2:-1]
    else:
        body = raw
    return bytes(body, 'utf-8').decode('unicode_escape')

def split_line(line: str, sep: str, collapse: bool) -> list[str]:
    if collapse:
        # Treat separator as a literal char and split on 1+ occurrences
        pattern = re.escape(sep) + r'+'
        return re.split(pattern, line.rstrip('\n'))
    else:
        return line.rstrip('\n').split(sep)

def compute_col_widths(rows: list[list[str]]) -> list[int]:
    if not rows:
        return []
    ncol = max(len(r) for r in rows)
    widths = [0] * ncol
    for r in rows:
        for i, cell in enumerate(r):
            visible = strip_control_for_width(cell)
            w = wcswidth(visible)
            if w < 0:
                w = len(visible)  # fallback, should rarely happen
            if w > widths[i]:
                widths[i] = w
    return widths

def format_rows(rows, widths, pad, right_cols, num_right, header):
    out_lines = []
    for ridx, r in enumerate(rows):
        cells = []
        for i in range(len(widths)):
            cell = r[i] if i < len(r) else ''
            visible = strip_control_for_width(cell)
            w = wcswidth(visible)
            if w < 0:
                w = len(visible)
            space = widths[i] - w
            align_right = (i in right_cols) or (num_right and looks_numeric(visible))
            if align_right:
                cells.append(' ' * space + cell)
            else:
                cells.append(cell + ' ' * space)
        line = (' ' * pad).join(cells)
        out_lines.append(line)
        if header and ridx == 0:
            # draw a rule based on widths and pad
            rule_cells = ['-' * w for w in widths]
            out_lines.append((' ' * pad).join(rule_cells))
    return out_lines

def main():
    # Avoid "Exception ignored in ... BrokenPipeError" when downstream closes the pipe
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:
        pass
    args = parse_args()
    sep = decode_separator(args.separator)
    right_cols = set()
    if args.right.strip():
        for tok in args.right.split(','):
            tok = tok.strip()
            if tok.isdigit():
                idx = int(tok) - 1
                if idx >= 0:
                    right_cols.add(idx)
    rows = []
    for line in sys.stdin:
        parts = split_line(line, sep, args.collapse)
        if not args.no_trim:
            parts = [p.strip() for p in parts]
        rows.append(parts)
    if not args.table:
        # Just re-join
        try:
            for r in rows:
                print((' ' * args.pad).join(r))
        except BrokenPipeError:
            try:
                sys.stdout.close()
            except Exception:
                pass
            os._exit(0)
        return
    widths = compute_col_widths(rows)
    if args.debug_width:
        print(f"# Using {'wcwidth' if _USING_LIB_WCWIDTH else 'fallback'}; widths={widths}", file=sys.stderr)
    try:
        for line in format_rows(rows, widths, args.pad, right_cols, args.num_right, args.header):
            print(line)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)

def _sigint_handler(signum, frame):
    """Handle SIGINT (Ctrl-C) with immediate clean exit."""
    # Suppress any partial output issues by forcing immediate exit
    print("", file=sys.stderr)
    os._exit(130)  # Standard Unix exit code for SIGINT, immediate exit


if __name__ == '__main__':
    # Install signal handler for clean Ctrl-C behavior
    signal.signal(signal.SIGINT, _sigint_handler)
    try:
        main()
    except KeyboardInterrupt:
        # Fallback: clean exit on Ctrl-C without stack trace
        print("", file=sys.stderr)
        os._exit(130)  # Standard Unix exit code for SIGINT, immediate exit
