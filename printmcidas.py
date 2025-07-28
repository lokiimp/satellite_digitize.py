import os
import re

img_path = "/arc25/arcdata/alpha/goes/pregvar/sms02/vissr/1977/1977_01_04_004/sms02.1977.004.204500.vi.raw"
num = "1009"
sat = "SMS-2"

# Extract components from the path
img_filename = os.path.basename(img_path)  # e.g. sms02.1977.002.204500.vi.raw

# Use regex to parse the filename
match = re.match(r"(.*)\.(\d{4})\.(\d{3})\.(\d{6})\.(..).*", img_filename)
if match:
    prefix, year, doy, hhmmss, band = match.groups()
    day = f"{year}{doy}"         # e.g. 1977002
    time = f"{hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:]}"  # e.g. 20:45:00
    img_name = f"{prefix}.{year}.{doy}.{hhmmss}.{band}"       # e.g. sms02.1977.002.204500
else:
    raise ValueError("Filename does not match expected format.")

# Output commands
print(f'imgmake.k {img_path} A/A.{num} 12109 12109 DAY={day} TIME={time} DEV=CCC MEMO="{sat}"')
print(f'imgdisp.k A/A.{num} MAG=1')
print(f'frmsave.k 1 {img_name}.gif')
print(f'cp $HOME/mcidas/data/{img_name}.gif /data/sgunshor/.')
