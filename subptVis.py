import sys, os, argparse, datetime

try:
    import matplotlib

    matplotlib.use('agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError as e:
    print("Matplotlib is needed to generate graphs")
    sys.exit(1)
try:
    import numpy as np
except ImportError as e:
    print("Numpy is needed to generate graphs")
    sys.exit(1)

SAT_ROW = 0
YEAR_ROW = 1
DAY_ROW = 2
SUBPOINT_LON_ROW = 3
SUBPOINT_LAT_ROW = 4


def genData(data, max_daily_jump=15):
    # Convert longitude to float degrees
    lat_vals = np.char.partition(data[:, SUBPOINT_LAT_ROW], ':')[:, 0].astype(float)

    lat_vals = -lat_vals
    # Filter out large jumps
    years = data[:, YEAR_ROW].astype(int)
    days = data[:, DAY_ROW].astype(int)

    mask = np.ones(len(data), dtype=bool)
    for i in range(1, len(data)):
        if data[i][SAT_ROW] == data[i-1][SAT_ROW]:  # same sat
            jump = abs(lat_vals[i] - lat_vals[i-1])
            # Handle wrap-around near ±180°
            if jump > 180:
                jump = 360 - jump
            if jump > max_daily_jump:
                mask[i] = False

    lat_vals = lat_vals[mask]
    heights = np.full(len(lat_vals), 1/365, dtype=float)
    widths = np.full(len(lat_vals), 4, dtype=float)
    bottoms = years[mask] + days[mask] / 365

    return lat_vals, heights, widths, bottoms



def main(argv):
    parser = argparse.ArgumentParser(description='A utility that visualizes daily positions of satellites')
    parser.add_argument('-v', '--verbose', action='store_true', help='programs verbocity')
    parser.add_argument('-o', '--outdir', default='.', help='directory to store generates image(s), default .')
    parser.add_argument('-l', '--list', nargs='+', help='One or more paths to generated daily subpoint files',
                        required=True)

    args = parser.parse_args(argv)

    if (not os.path.isdir(args.outdir)):
        print("Output directory does not exist: " + args.outdir)
        sys.exit(1)

    plt.ylabel('Year')
    plt.xlabel('Longitude')
    plt.title('Geostationary Equator Coverage')
    plt.figure().set_figheight(15)
    plt.xlim(-180, 180)

    min_date = 9999999
    max_date = -9999999
    plot_list = []
    patch_list = []
    for subpt in args.list:
        data = np.loadtxt(subpt, dtype='str')
        min_date = min(min_date, int(data[0][1]))
        max_date = max(max_date, int(data[-1][1]))
        if (args.verbose):
            print("Graphing " + data[0][0])
        gen = genData(data, max_daily_jump=2)
        p = plt.bar(gen[0], gen[1], width=gen[2], bottom=gen[3])
        patch_list.append(mpatches.Patch(label=data[0][0], color=p[-1].get_facecolor()))

    year_axis = np.arange(max_date, min_date - 1, -1, dtype='int')
    plt.yticks(year_axis)
    plt.gca().invert_yaxis()
    plt.legend(handles=patch_list, bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)
    plt.tight_layout()

    if (len(args.list) == 1):
        out_name = data[0][0]
    else:
        out_name = "sats"
    plt.savefig(os.path.join(args.outdir, out_name + '.png'))


if __name__ == '__main__':
    main(sys.argv[1:])
