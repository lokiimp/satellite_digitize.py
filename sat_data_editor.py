import datetime

def prompt_date(prompt_text, default_date):
    while True:
        date_str = input(f"{prompt_text} (YYYY-MM-DD) [default: {default_date}]: ").strip()
        if not date_str:
            return default_date
        try:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

def ymd_from_year_doy(year, doy):
    return (datetime.datetime(year, 1, 1) + datetime.timedelta(doy - 1)).date()

def main():
    input_file = "ATS-3_useful-h2.txt"
    output_file = "ATS-3_useful-h2_labeled.txt"
    satellites = {}

    # Read and group data by satellite
    with open(input_file, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            name, year, day = parts[:3]
            date = ymd_from_year_doy(int(year), int(day))
            satellites.setdefault(name, []).append({
                "date": date,
                "raw": line.strip()
            })

    with open(output_file, "w") as out:
        for sat, records in satellites.items():
            print(f"\nLabeling for satellite: {sat}")
            records.sort(key=lambda r: r["date"])
            dates = [r["date"] for r in records]

            # Launch is always the first available day
            launch_date = dates[0]
            print(f"First available date for {sat} is {launch_date} (will be launch day)")
            post_launch_end = launch_date + datetime.timedelta(days=10)

            # Prompt for operational and decommissioned transitions
            op_date = prompt_date(f"Enter OPERATIONAL start date for {sat}", "")
            decomm_date = prompt_date(f"Enter DECOMMISSIONED date for {sat}", "")

            decomm_old_start = decomm_date + datetime.timedelta(days=10) if decomm_date else None

            for rec in records:
                d = rec["date"]
                if d == launch_date:
                    status = "launch"
                elif launch_date < d <= post_launch_end:
                    status = "post-launch"
                elif op_date and d < op_date:
                    status = "pre-operational"
                elif op_date and d >= op_date and (not decomm_date or d < decomm_date):
                    status = "operational"
                elif decomm_date and d >= decomm_date and (not decomm_old_start or d < decomm_old_start):
                    status = "decommissioned"
                elif decomm_old_start and d >= decomm_old_start:
                    status = "decommissioned_old"
                else:
                    status = "unknown"
                out.write(f"{rec['raw']} {status}\n")

    print(f"\nLabeled data written to {output_file}")

if __name__ == "__main__":
    main()