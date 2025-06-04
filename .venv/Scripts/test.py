for j in range(0, len(vals)):
    if vals[j].startswith(time_text[:2]):
        if vals[j][-2:] != time_text[-2:]:
            # print(f"Error with time_text: values dont match: ({time_text}, {vals[j]})")
            time_text = open_problem_window(time_text, vals[j])
        if vals[j + 1] != date_text:
            # print(f"Error with date_text: values dont match: ({date_text}, {vals[j+1]})")
            date_text = open_problem_window(date_text, vals[j + 1])
        if vals[j + 2] != satellite_text:
            # print(f"Error with satellite_text: values dont match: ({satellite_text}, {vals[j+2]})")
            satellite_text = open_problem_window(satellite_text, vals[j + 2])
        break
    if j == len(vals) - 1:
        print("No time data found by OCR.")