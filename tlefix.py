#!/usr/bin/env python3
import os

BASE_DIR = "/ships22/sds/goes/digitized/TLE"


def calc_checksum(line):
    """TLE checksum: sum of all digits plus 1 per minus sign, modulo 10."""
    total = 0
    for ch in line[:68]:  # exclude checksum digit itself
        if ch.isdigit():
            total += int(ch)
        elif ch == '-':
            total += 1
    return total % 10


for sat in os.listdir(BASE_DIR):
    sat_dir = os.path.join(BASE_DIR, sat)
    if not os.path.isdir(sat_dir):
        continue
    for year in os.listdir(sat_dir):
        year_dir = os.path.join(sat_dir, year)
        if not os.path.isdir(year_dir):
            continue
        for folder in os.listdir(year_dir):
            folder_path = os.path.join(year_dir, folder)
            if not os.path.isdir(folder_path):
                continue
            for fname in os.listdir(folder_path):
                if fname.endswith(".tle.txt"):
                    file_path = os.path.join(folder_path, fname)
                    with open(file_path, "r") as f:
                        lines = f.read().splitlines()

                    if len(lines) < 2:
                        continue

                    # Determine which line is Line 1 (some files have a title line)
                    line1_idx = 0 if lines[0].startswith("1 ") else 1
                    if len(lines) <= line1_idx:
                        continue
                    line1 = lines[line1_idx]

                    # New check for the 70-character line error
                    # e.g., "...  503184-6 ..." which is 9 chars and makes the line too long.
                    # Condition: Line is too long AND has two spaces at cols 45-46,
                    # a 6-digit mantissa, and an exponent sign.
                    if (len(line1.strip()) >= 70 and
                            line1[44:46] == '  ' and
                            line1[46:52].isdigit() and
                            line1[52] in ('+', '-')):

                        print(f"Fixing long TLE (9-char 2nd deriv): {file_path}")

                        # Extract parts around the 9-character malformed field
                        part_before = line1[:44]
                        mantissa = line1[46:52]
                        exponent = line1[52:54]
                        # The rest of the line body is shifted right by one character
                        part_after = line1[54:70]

                        # Fix: Remove the last digit of the mantissa and create a standard 8-char field
                        trimmed_mantissa = mantissa[:-1]
                        # The new field uses a single leading space for the sign
                        fixed_field = ' ' + trimmed_mantissa + exponent

                        # Rebuild the line body to the correct 68-character length
                        new_body = part_before + fixed_field + part_after

                        # Recalculate checksum and form the final, correct 69-character line
                        checksum = calc_checksum(new_body)
                        line1 = new_body + str(checksum)

                        lines[line1_idx] = line1
                        out_path = file_path.replace(".tle.txt", ".tle.fix.txt")
                        with open(out_path, "w") as out:
                            out.write("\n".join(lines) + "\n")

                    # Original check for the 8-character field error (missing sign)
                    else:
                        sec_deriv = line1[44:52]
                        if (sec_deriv[0] not in (' ', '+', '-') and
                                sec_deriv[0:6].isdigit() and
                                sec_deriv[6] in ('+', '-')):
                            print(f"Fixing standard TLE (missing sign): {file_path}")
                            mantissa = sec_deriv[0:6]  # six digits
                            exponent = sec_deriv[6:]  # exponent sign + digit

                            # Insert space for positive sign, trim mantissa to 5 digits
                            fixed_field = " " + mantissa[:5] + exponent

                            # Replace field
                            line1 = line1[:44] + fixed_field + line1[52:]

                            # Recalculate checksum
                            checksum = calc_checksum(line1)
                            line1 = line1[:68] + str(checksum)

                            lines[line1_idx] = line1
                            out_path = file_path.replace(".tle.txt", ".tle.fix.txt")
                            if os.path.exists(out_path):
                                print(f"path exists: {out_path}")
                            else:
                                with open(out_path, "w") as out:
                                    out.write("\n".join(lines) + "\n")