import os
file_loc = r"/arc25/arcdata/alpha/goes/pregvar/goes01/vissr/1976/1976_07_01_183/"
file_name = "goes01.1976.183.170000.ir.area"
area_num = "1011"
new_name = file_name.replace("area", "gif")
print(f"ln -s {os.path.join(file_loc, file_name)} AREA{area_num}")
print(f"imgdisp.k A/A.{area_num} MAG=-3")
print(f"frmsave.k 1 {new_name}")
print(f"mv {new_name} /data/sgunshor/.")
