"""
Converts a tle file into a list of subpoints
"""

__author__ = 'Max Drexler'
__email__ = 'mndrexler@wisc.edu'

import os, sys, re, subprocess, datetime, argparse, tempfile
from shutil import rmtree

ARGS = None  # args is global so file cleanup is possible after <CTRL> C is pressed
PATH_TO_MCIDAS_SCRIPT = './bin/tle_get_sub_point.bash'
VALID_TLE_REG = re.compile(
    r"(1 \d{5}[US ] \d{5}[A-Z ]{1,3} (\d{2})(\d.{11}) [- ].\d{8} [-+ ]\d{5}[-+ ]\d [-+ ]\d{5}[-+]\d [0-4] [ \d]{4}\d\n"
    r"2 \d{5} [ \d]{3}.[\d ]{4} [ \d]{3}.[ \d]{4} \d{7} [ \d]{3}.[\d ]{4} [ \d]{3}.[\d ]{4} [ \d]{2}.[\d ]{8}[ \d]{5}\d)",
    re.MULTILINE)


# this is the regex for a valid TLE entry

# prints a progress bar to stdout
def printProg(num, total, barLen=50):
    percent = num / total
    sys.stdout.write("\r")
    sys.stdout.write("[{:<{}}] {:.0f}% Generating subpoints".format("=" * int(barLen * percent), barLen, percent * 100))
    sys.stdout.flush()
    if (percent >= 1.0):
        sys.stdout.write('\n')


def calcDate(endYear, day):
    """
    calculates the date and returns it in an array [yyyy, ddd, HH:MM:ss]
    endYear: the last two digits of a year
    day: the full decimal day of year
        """

    outArr = []
    # hacky way to figure out if tle is from the 20th or 21st centruy.
    # Will need to be updated eventually (2061)
    if (int(endYear) > 60):
        year = "19" + endYear
    else:
        year = "20" + endYear

    outArr.append(year)
    outArr.append(day[:3])
    outArr.append(calcTime(float(day[3:])))
    return outArr


def calcTime(dayDec):
    """
    calculates the time in the format HH:MM:ss based on the decimal day
        """
    if (dayDec < 0.000006):
        return "00:00:00"
    hourDec = dayDec * 24
    minDec = float(str(hourDec)[str(hourDec).find('.'):]) * 60
    hour = str(hourDec)[:str(hourDec).find('.')].zfill(2)
    secDec = float(str(minDec)[str(minDec).find('.'):]) * 60
    minute = str(minDec)[:str(minDec).find('.')].zfill(2)
    sec = str(round(secDec)).zfill(2)
    if (sec == "60"):
        sec = "59"
    return ':'.join((hour, minute, sec))


def main(argv):
    global ARGS
    if not os.path.exists(PATH_TO_MCIDAS_SCRIPT):
        print("%s does not exist" % PATH_TO_MCIDAS_SCRIPT)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="A utility that generates the daily position of a satellite based on a file with lots of Two Line Elements(TLEs)")
    parser.add_argument('satellite', help='the name of the satellite for the TLE file')
    parser.add_argument('tle_file', help='path to the TLE file')
    parser.add_argument('-o', '--output', default=None,
                        help='specify where to output daily positions, default is stdout')
    parser.add_argument('-m', '--mode', choices=['w', 'x', 'wb', 'xb'], default='w',
                        help='mode to open output file, default is %(default)s')
    parser.add_argument('--height', action='store_true', help='option to include the satellite height in the sbpt file')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    ARGS = parser.parse_args(argv)

    ######################VERIFY INPUTS###############################

    SAT = ARGS.satellite.upper()
    # TODO: error check satellite
    TLE_PATH = ARGS.tle_file
    if (not os.path.isfile(TLE_PATH)):
        print("Specified TLE file does not exist")
        sys.exit(1)

    if (ARGS.output):
        try:
            OUT = open(ARGS.output, ARGS.mode)
        except:
            print("Couldn't open %s with mode %s" % (ARGS.output, ARGS.mode))
            sys.exit(1)
    else:
        OUT = sys.stdout

    ###################GENERATE SUBPOINTS###########################

    subpoint_dict = {}
    min_date = 9999999
    max_date = -9999999

    tmp_out = tempfile.NamedTemporaryFile(mode='w+')
    # tmp_out = open('tmp.out', mode='w+')
    tmp_out.seek(0)
    tmp_out.write('\n\n\n')
    tmp_out.flush()
    tmp_out.read()
    with open(TLE_PATH, encoding='utf-8') as tle_file:
        tleMatchList = VALID_TLE_REG.findall(tle_file.read())

    numMatches = len(tleMatchList)
    if (numMatches == 0):
        print("TLE file contains 0 valid two/three line elements")
        sys.exit(0)

    if (ARGS.verbose > 0):
        num = 1
        error_lines = []

    ###### VERY JANKY FIX TO WRONG INITIAL TLE PROBLEM ######
    """ When running script the first TLE in TLE file would not be converted
        into a sbpt file for some reason. Mcidas gives weird error:

        "ATS1 1966341 not find elements -2147483648:-2147483648:-2147483648 -2147483648:-2147483648:-2147483648 -nan"

        By calling mcidas script twice on the first TLE the problem is fixed.
    """

    tle = '\n'.join((SAT, tleMatchList[0][0]))
    tmp_out.seek(0)  # reuse the same file descriptor by rewriting previous mcidas data
    tmp_out.write(tle + '\n')
    date_arr = calcDate(tleMatchList[0][1], tleMatchList[0][2])
    run_cmd = " ".join((PATH_TO_MCIDAS_SCRIPT, SAT, date_arr[0], date_arr[1], date_arr[2], tmp_out.name))
    mcidas_popen = subprocess.Popen(run_cmd, shell=True, stdout=subprocess.PIPE)
    mcidas_out = mcidas_popen.communicate()[0][:-1].decode('utf-8').split()
    mcidas_popen.wait()
    ##########################################################

    # mcidas can only read one tle at a time
    # separate each tle, write it to file, call mcidas, repeat
    for i in range(numMatches):
        tle = '\n'.join((SAT, tleMatchList[i][0]))
        tmp_out.seek(0)  # reuse the same file descriptor by rewriting previous mcidas data
        tmp_out.write(tle + '\n')
        date_arr = calcDate(tleMatchList[i][1], tleMatchList[i][2])
        run_cmd = " ".join((PATH_TO_MCIDAS_SCRIPT, SAT, date_arr[0], date_arr[1], date_arr[2], tmp_out.name))
        mcidas_popen = subprocess.Popen(run_cmd, shell=True, stdout=subprocess.PIPE)
        mcidas_out = mcidas_popen.communicate()[0][:-1].decode('utf-8').split()
        mcidas_popen.wait()

        if (ARGS.verbose > 0):
            printProg(num, numMatches)
            num += 1
        if (len(mcidas_out) != 5):  # invalid mcidas input/mcidas doesn't know output
            if (ARGS.verbose > 0):
                print(tle)
                print(date_arr)
                print(run_cmd)
                error_lines.append("\nSKIPPED TLE: \n\t%s \n\t-> mcidas output:\n\t\t[%s]" % (
                '\n\t'.join(tle.split('\n')), " ".join(mcidas_out)))
            continue

        wrtTpl = (mcidas_out[2], mcidas_out[3])
        if (ARGS.height):
            wrtTpl += (mcidas_out[4],)
        subpoint_dict[mcidas_out[1]] = wrtTpl

        sat_date = int(mcidas_out[1])
        min_date = min(sat_date, min_date)
        max_date = max(sat_date, max_date)

    tmp_out.close()

    if (ARGS.verbose > 0):
        sys.stdout.writelines(error_lines)
        sys.stdout.write('\n')

    if (len(subpoint_dict) < 1):
        print("Could not generate any subpoints from TLEs")
        sys.exit(0)
    ################FIND DAILY SUBPOINTS##########################

    start_date = datetime.datetime.strptime(str(min_date), "%Y%j")
    end_date = datetime.datetime.strptime(str(max_date), "%Y%j")
    delta = end_date - start_date

    prev_sbpt = subpoint_dict[str(min_date)]
    for i in range(delta.days + 1):
        cur_day = start_date + datetime.timedelta(days=i)
        try:
            sbpt = subpoint_dict[cur_day.strftime("%Y%j")]
            prev_sbpt = sbpt
        except:
            sbpt = prev_sbpt
        OUT.write(" ".join((SAT, cur_day.strftime("%Y %j"),) + sbpt) + '\n')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        print('\n')
        if (ARGS and ARGS.output):
            os.remove(ARGS.output)
