#!/usr/bin/env python3
import os
import re
from pathlib import Path


# =========================
# Patterns for field checks
# =========================
PAT_LINE1_SATCLASS = re.compile(r"^\d{5}[A-Z]$")
PAT_INTLDES = re.compile(r"^\d{5}[A-Z0-9]{0,3}$")
PAT_EPOCH = re.compile(r"^\d{5}\.\d{8}$")
PAT_NDOT1 = re.compile(r"^[ +-]?\d?\.\d{8}$")
PAT_EXP7 = re.compile(r"^[+\-]?\d{5}[+\-]\d$")
PAT_EPHEMERIS = re.compile(r"^\d$")
PAT_ELEMSET = re.compile(r"^\d{1,5}$")
PAT_LINE2_SAT = re.compile(r"^\d{5}$")
PAT_ANGLE4 = re.compile(r"^-?\d{1,3}\.\d{4}$")
PAT_ECC7 = re.compile(r"^\d{7}$")
PAT_MEANMOTION = re.compile(r"^\d{1,2}\.\d{8}$")
PAT_REV = re.compile(r"^\d{1,5}$")

# =========================
# Utility functions
# =========================
def normalize_line(line: str) -> str:
    line = line.replace("\u00A0", " ")
    line = re.sub(r"[ \t\r\f\v]+", " ", line)
    return re.sub(r"\s+", " ", line).strip()

def compute_checksum_from_rule(line: str) -> int:
    body = line[:-1]
    total = sum(int(ch) for ch in body if ch.isdigit())
    total += body.count('-')
    return total % 10

def split_tokens_allow_extra_last(line: str, expected_first=8):
    toks = normalize_line(line).split()
    if len(toks) < expected_first + 1:
        return toks
    if len(toks) == expected_first + 1:
        return toks
    first_part = toks[:expected_first]
    last_part = "".join(toks[expected_first:])
    return first_part + [last_part]

# =========================
# Line validators
# =========================
def validate_line1(raw_line: str):
    errors = []
    toks = split_tokens_allow_extra_last(raw_line, expected_first=8)
    if len(toks) < 9:
        return [f"Line 1: expected >=9 tokens, got {len(toks)}: {toks}"]

    if toks[0] != '1':
        errors.append(f"Line 1: expected leading '1', got '{toks[0]}'")
    if not PAT_LINE1_SATCLASS.match(toks[1]):
        errors.append(f"Line 1: sat/class invalid: '{toks[1]}'")
    if not PAT_INTLDES.match(toks[2]):
        errors.append(f"Line 1: international designator invalid: '{toks[2]}'")
    if not PAT_EPOCH.match(toks[3]):
        errors.append(f"Line 1: epoch invalid: '{toks[3]}'")
    if not PAT_NDOT1.match(toks[4]):
        errors.append(f"Line 1: first derivative invalid: '{toks[4]}'")
    if not PAT_EXP7.match(toks[5]):
        errors.append(f"Line 1: second derivative invalid: '{toks[5]}'")
    if not PAT_EXP7.match(toks[6]):
        errors.append(f"Line 1: BSTAR invalid: '{toks[6]}'")
    if not PAT_EPHEMERIS.match(toks[7]):
        errors.append(f"Line 1: ephemeris type invalid: '{toks[7]}'")

    last_token = toks[8]
    elem_no = last_token[:-1] or "0"
    checksum_char = last_token[-1]
    if not PAT_ELEMSET.match(elem_no):
        errors.append(f"Line 1: element set invalid: '{elem_no}'")
    if not checksum_char.isdigit():
        errors.append(f"Line 1: checksum char invalid: '{checksum_char}'")
    else:
        expected = compute_checksum_from_rule(raw_line)
        if int(checksum_char) != expected:
            errors.append(f"Line 1: checksum mismatch: found {checksum_char}, expected {expected}")
    return errors

def validate_line2(raw_line: str):
    errors = []
    toks = split_tokens_allow_extra_last(raw_line, expected_first=8)
    if len(toks) < 9:
        return [f"Line 2: expected >=9 tokens, got {len(toks)}: {toks}"]

    if toks[0] != '2':
        errors.append(f"Line 2: expected leading '2', got '{toks[0]}'")
    if not PAT_LINE2_SAT.match(toks[1]):
        errors.append(f"Line 2: sat number invalid: '{toks[1]}'")
    if not PAT_ANGLE4.match(toks[2]):
        errors.append(f"Line 2: inclination invalid: '{toks[2]}'")
    if not PAT_ANGLE4.match(toks[3]):
        errors.append(f"Line 2: RAAN invalid: '{toks[3]}'")
    if not PAT_ECC7.match(toks[4]):
        errors.append(f"Line 2: eccentricity invalid: '{toks[4]}'")
    if not PAT_ANGLE4.match(toks[5]):
        errors.append(f"Line 2: argument of perigee invalid: '{toks[5]}'")
    if not PAT_ANGLE4.match(toks[6]):
        errors.append(f"Line 2: mean anomaly invalid: '{toks[6]}'")
    if not PAT_MEANMOTION.match(toks[7]):
        errors.append(f"Line 2: mean motion invalid: '{toks[7]}'")

    last_token = toks[8]
    rev_part = last_token[:-1] or "0"
    checksum_char = last_token[-1]
    if not PAT_REV.match(rev_part):
        errors.append(f"Line 2: revolution number invalid: '{rev_part}'")
    if not checksum_char.isdigit():
        errors.append(f"Line 2: checksum char invalid: '{checksum_char}'")
    else:
        expected = compute_checksum_from_rule(raw_line)
        if int(checksum_char) != expected:
            errors.append(f"Line 2: checksum mismatch: found {checksum_char}, expected {expected}")

    # New check: If argument of perigee negative but rev number != 100, flag error
    try:
        arg_perigee = float(toks[5])
        rev_num = int(rev_part)
        if arg_perigee < 0 and rev_num == 100:
            errors.append(f"Line 2: argument of perigee is negative ({arg_perigee}) but revolution number is 100")
        if arg_perigee < 0 and rev_num != 100:
            errors.append(f"Line 2: argument of perigee is negative ({arg_perigee}) and revolution number is {rev_num} instead of 100")
        elif rev_num != 100:
            errors.append(f"revolution number is {rev_num} instead of 100")

    except Exception as e:
        # If float/int conversion fails, ignore here — already reported in regex checks
        pass

    return errors


# =========================
# File validator
# =========================
def validate_tle_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [ln.strip() for ln in text if ln.strip()]
    if len(lines) < 2:
        return ["File has fewer than 2 lines"]

    # Find first line starting with "1 " and next starting with "2 "
    line1, line2 = None, None
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i+1].startswith("2 "):
            line1, line2 = lines[i], lines[i+1]
            break
    if not line1 or not line2:
        return ["Could not find valid line 1/line 2 pair"]

    errors = []
    errors.extend(validate_line1(line1))
    errors.extend(validate_line2(line2))
    return errors

# =========================
# Main scan
# =========================
BASE_DIR = Path("/ships22/sds/goes/digitized/TLE")

for tle_file in BASE_DIR.rglob("*.tle.txt"):
    # Get the original filename as a string and create the potential ".fix.txt" filename
    fix_filename = tle_file.name.replace(".tle.txt", ".tle.fix.txt")

    # Create the full path for the potential ".fix.txt" file
    fix_file_path = tle_file.with_name(fix_filename)

    # If the ".fix.txt" version exists, use it instead
    if fix_file_path.exists():  # .exists() is a handy Path method
        tle_file = fix_file_path

    #print(f"Validating: {tle_file}")  # For checking which file is used
    errs = validate_tle_file(tle_file)
    if errs:
        # Path parts: .../{sat}/{yyyy}/{yyyy_mm_dd_ddd}/file.tle.txt
        try:
            sat = tle_file.parts[-4]
            date_str = tle_file.parts[-2]
            print(f"{sat} {date_str}:")
        except IndexError:
            print(f"{tle_file}:")
        for e in errs:
            print(f"  - {e}")
