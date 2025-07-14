area = 1003

for i in range(1,9):
    print(f"imgdisp.k A/A.{area} MAG=-{i}")
    print(f"frmsave.k 1 {area}mag-{i}.gif")
    print(f"cp $HOME/mcidas/data/{area}mag-{i}.gif /data/sgunshor/.")
    print()