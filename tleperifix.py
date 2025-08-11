#!/usr/bin/env python3
import re
from pathlib import Path

PAT_ANGLE4 = re.compile(r"^-?\d{1,3}\.\d{4}$")

def normalize_line(line: str) -> str:
    line = line.replace("\u00A0", " ")
    line = re.sub(r"[ \t\r\f\v]+", " ", line)
    return re.sub(r"\s+", " ", line).strip()

def split_tokens_allow_extra_last(line: str, expected_first=8):
    toks = normalize_line(line).split()
    if len(toks) < expected_first + 1:
        return toks
    if len(toks) == expected_first + 1:
        return toks
    first_part = toks[:expected_first]
    last_part = "".join(toks[expected_first:])
    return first_part + [last_part]

def compute_checksum_from_rule(line: str) -> int:
    # Sum all digits + 1 per '-' in columns 1-68 (0-based: 0-67), modulo 10
    total = 0
    for ch in line[:68]:
        if ch.isdigit():
            total += int(ch)
        elif ch == '-':
            total += 1
    return total % 10

def fix_negative_argument_perigee_in_file(tle_path: Path):
    lines = tle_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 2:
        return False

    # Find line1 and line2
    line1_idx, line2_idx = None, None
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i+1].startswith("2 "):
            line1_idx, line2_idx = i, i+1
            break
    if line2_idx is None:
        return False

    line2 = lines[line2_idx]
    if len(line2) < 69:
        # Pad line2 if too short (not ideal, but avoid crash)
        line2 = line2.ljust(69)

    # Extract argument of perigee substring (cols 35-42, zero-based 34:42)
    arg_perigee_str = line2[34:42].strip()
    try:
        arg_perigee_val = float(arg_perigee_str)
    except ValueError:
        return False

    if arg_perigee_val >= 0:
        return False

    # Calculate positive complement
    fixed_arg_perigee_val = 360 + arg_perigee_val
    fixed_arg_str = f"{fixed_arg_perigee_val:8.4f}"  # width 8, 4 decimals

    # Replace argument of perigee field in line2 (cols 35-42)
    line2 = line2[:34] + fixed_arg_str + line2[42:]

    # Fix revolution number if arg < -100
    rev_str = line2[63:68]  # cols 64-68
    checksum_char = line2[68]

    if arg_perigee_val < -100:
        # Insert '0' between rev number and checksum:
        # rev_str is 5 chars, e.g. '  108'
        # We add '0' before checksum: new rev_str length is 5, so
        # we insert '0' before checksum and shift checksum to col 69
        # So we build rev number as: rev_str + '0' then checksum at pos 69

        # But we only have one char for checksum at 69th pos, so line length will be 70 now
        # So we need to shift rev_str to left one position and add '0' before checksum

        # Let's do it carefully:
        # Remove trailing spaces from rev_str:
        rev_num_clean = rev_str.strip()
        # Append '0' to rev num:
        rev_num_fixed = rev_num_clean + '0'
        # Pad left with spaces to length 5:
        rev_num_fixed = rev_num_fixed.rjust(5)

        # Rebuild line2 with new rev num and checksum at last char (pos 69):
        line2 = line2[:63] + rev_num_fixed + checksum_char

        # Length should still be 69 chars (63 + 5 + 1)
    else:
        # Leave rev_str as is
        pass

    # Now recalc checksum and replace last char
    new_checksum = compute_checksum_from_rule(line2)
    line2 = line2[:68] + str(new_checksum)

    # Update lines and write fixed file if changed
    lines[line2_idx] = line2
    fixed_path = tle_path.with_name(tle_path.name.replace(".tle.txt", ".tle.fix.txt"))
    fixed_text = "\n".join(lines) + "\n"
    if tle_path.read_text() != fixed_text:
        fixed_path.write_text(fixed_text)
        print(f"Fixed negative argument of perigee in {tle_path}")
        return True
    return False


# Usage example scanning a directory
BASE_DIR = Path("/ships22/sds/goes/digitized/TLE")

for tle_file in BASE_DIR.rglob("*.tle.fix.txt"):
    fix_negative_argument_perigee_in_file(tle_file)
