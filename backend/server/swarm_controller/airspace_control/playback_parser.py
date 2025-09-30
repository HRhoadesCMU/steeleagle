from datetime import datetime, timezone
import re
import sys

TIME_IDX = 0
CALLER_IDX = 1
LOGLEVEL_IDX = 2
METHOD_IDX = 3
DATA_IDX = 4

class PlaybackEngine():
    def __init__(self):
        return

    def read_file_to_mem(self, filename):
        with open(filename, 'r') as f:
            print(f"Opened {filename} for parsing...")
            self.raw_data = []
            lines = f.readlines()
            for line in lines:
                split_line = line.strip().split('|')
                cleaned_line = []
                for entry in split_line:
                    cleaned_line.append(entry.strip())
                self.raw_data.append(cleaned_line)
            print(f"Read {len(self.raw_data)} lines from log file into memory for parsing...")
            print(self.raw_data[0])

    def parse_log_file(self, filename):
        pass

    def extract_airspace_base_features(self):
        i = 0
        data_len = len(self.raw_data)
        while i < data_len:
            curr_line = self.raw_data[i]
            match = re.search(r'create_airspace', curr_line[METHOD_IDX])
            if match is not None:
                self.extract_starttime(curr_line)
                self.extract_minmax_alt(curr_line)
                self.extract_airspace_corners(curr_line)
                break
            i += 1

    def extract_transactions(self, filename):
        pass

    def extract_starttime(self, line):
        self.start_time = convert_dtg_to_epoch(line[TIME_IDX])

    def extract_minmax_alt(self, line):
        ''' Assumes only non-negative values for altitude '''
        split_line = line[DATA_IDX].split(", ")
        alt_seg = find_segment(r'altitude', split_line)
        if alt_seg is not None:
            raw_vals = alt_seg.split()[1].split("-")
            min_val = regex_format_float_unsigned(raw_vals[0])
            max_val = regex_format_float_unsigned(raw_vals[1])
            self.min_alt = float(min_val)
            self.max_alt = float(max_val)
        else:
            print("Failed to extract min and max alt values from origin line...")
            return
    
    def extract_airspace_corners(self, line):
        data_line = line[DATA_IDX]
        if find_segment(r'corners', data_line) is None:
            print(data_line)
            print("Failed to extract corners from origin line...")
            return
        self.corners = parse_coordinate_sequence(data_line)
        print(self.corners)


def find_segment(keyword, line_items):
    if type(line_items) == str:
        match = re.search(rf'{keyword}', line_items)
        if match is not None:
            return line_items
        else:
            return None
    for item in line_items:
        match = re.search(rf'{keyword}', item)
        if match is not None:
            return item

def regex_format_float_unsigned(target_string):
    return re.sub(r'[^0-9.]', '', target_string)

def regex_format_float_signed(target_string):
    return re.sub(r'[^0-9.-]', '', target_string)

def parse_2d_coordinate(target_string):
    components = target_string.split(",")
    lat = regex_format_float_signed(components[0])
    lon = regex_format_float_signed(components[1])
    return (lat, lon)

def parse_3d_coordinate(target_string):
    components = target_string.split(",")
    lat = regex_format_float_signed(components[0])
    lon = regex_format_float_signed(components[1])
    alt = regex_format_float_signed(components[2])
    return (lat, lon, alt)

def parse_coordinate_sequence(target_string):
    components = target_string.split("),")
    print(components)
    coord_list = []
    if (len(components[0].split(",")) == 2):
        for item in components:
            coord_list.append(parse_2d_coordinate(item))
    else:
        for item in components:
            coord_list.append(parse_3d_coordinate(item))
    return coord_list

def convert_dtg_to_epoch(dtg_string):
    dtg_format = "%Y-%m-%d %H:%M:%S"
    dt_obj = datetime.strptime(dtg_string, dtg_format)
    epoch_time = dt_obj.timestamp()
    return epoch_time

def convert_epoch_to_dtg(epoch_value):
    return datetime.fromtimestamp(epoch_value, tz=timezone.utc)

if __name__ == "__main__":
    pe = PlaybackEngine()
    pe.read_file_to_mem('airspace_logs/airspace_control.log')
    pe.extract_airspace_base_features()