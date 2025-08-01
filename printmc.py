import os
file_loc = r"/arc25/arcdata/alpha/goes/pregvar/"
sub_file = r"goes01/vissr/1976/1976_10_18_292/"
file_name = "goes01.1976.292.170000.vi.area"
area_num = "1021"
file_loc = os.path.join(file_loc, sub_file)
new_name = file_name.replace("area", "gif")
print(f"ln -s {os.path.join(file_loc, file_name)} AREA{area_num}")
print(f"imgdisp.k A/A.{area_num} MAG=-3")
print(f"frmsave.k 1 {new_name}")
print(f"mv {new_name} /data/sgunshor/.")
