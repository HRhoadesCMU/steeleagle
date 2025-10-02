import airspace_region
from datetime import datetime, timezone
from enum import Enum
import re
import sys

TIME_IDX = 0
CALLER_IDX = 1
LOGLEVEL_IDX = 2
METHOD_IDX = 3
DATA_IDX = 4

class TransactionType(Enum):
    DESTROY = 0
    CREATE = 1
    SPLIT_LAT = 2
    SPLIT_LON = 3
    SPLIT_ALT = 4
    JOIN_LAT = 5
    JOIN_LON = 6
    JOIN_ALT = 7
    STATUS_CHANGE = 8
    OWNER_CHANGE = 9
    OCCUPANT_CHANGE = 10

class RegionState():
    def __init__(self, start_t, min_alt, max_alt, corners, status, owner, occupant):
        self.start_t = start_t
        self.end_t = -1
        self.min_alt = min_alt
        self.max_alt = max_alt
        self.corners = corners
        self.status = status
        self.owner = owner
        self.occupant = occupant

    def is_current_state(self):
        return self.end_t == -1

    def set_end_t(self, end_t):
        self.end_t = end_t

class AirspaceTransaction():
    def __init__(self, target_cid, transaction_type, transaction_details):
        self.cid = target_cid
        self.tx_type = transaction_type
        self.tx_info = transaction_details

class PlaybackEngine():
    def __init__(self):
        self.actions_by_tstep = [] # list of transactions tied to t=x
        self.regions = {} # cid -> list[RegionState]

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
                self.extract_grid_minmax_alt(curr_line)
                self.extract_airspace_corners(curr_line)
                break
            i += 1
        while i < data_len:
            self.parse_line(self.raw_data[i])
            i += 1
        

    def extract_transactions(self, filename):
        pass

    def extract_starttime(self, line):
        self.start_time = convert_dtg_to_epoch(line[TIME_IDX])

    def extract_epoch_time(self, line_seg):
        return convert_dtg_to_epoch(line_seg)

    def extract_grid_minmax_alt(self, line):
        ''' Assumes only non-negative values for altitude '''
        split_line = line[DATA_IDX].split(", ")
        alt_seg = find_segment(r'altitude', split_line)
        if alt_seg is not None:
            self.min_alt, self.max_alt = parse_minmax_alt(alt_seg)
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

    def parse_line(self, line):
        t_stamp = self.produce_relative_timestamp(line[TIME_IDX])
        method = line[METHOD_IDX]
        if find_segment(r'init', method):
            if find_segment(r'geohash precision', line[DATA_IDX]):
                return
            self.extract_region_creation(t_stamp, line[DATA_IDX])
            # add to list of regions w/ start time defined
            # add to tx log
        elif find_segment(r'split_by', method):
            # end current state of cid, cid is destroyed
            if find_segment(r'lat', method):
                self.extract_region_split(t_stamp, line[DATA_IDX], TransactionType.SPLIT_LAT)
            elif find_segment(r'lon', method):
                self.extract_region_split(t_stamp, line[DATA_IDX], TransactionType.SPLIT_LON)
            else:
                self.extract_region_split(t_stamp, line[DATA_IDX], TransactionType.SPLIT_ALT)
        elif find_segment(r'reserve', method):
            # end current state of cid
            # start new state of cid
            # add to tx log
            self.extract_region_reservation(t_stamp, line[DATA_IDX])
        elif find_segment(r'update', method):
            # end current state of cid
            # start new state of cid
            # add to tx log
            if find_segment(r'owner', method):
                self.extract_owner_update(t_stamp, line[DATA_IDX])
            elif find_segment(r'status', method):
                self.extract_status_update(t_stamp, line[DATA_IDX])
        elif find_segment(r'add_occupant', method):
            # end current state of cid
            # start new state of cid
            # add to tx log
            self.extract_add_occupant(t_stamp, line[DATA_IDX])

    def produce_relative_timestamp(self, time_seg):
        e_time = self.extract_epoch_time(time_seg)
        return (e_time - self.start_time) / 1000
    
    def extract_region_creation(self, rel_timestamp, data_seg):
        cid_split = data_seg.split(" >> ")
        cid = regex_format_int_unsigned(cid_split[0])
        range_seg, corner_seg = cid_split[1].split("corners: ")
        alt_seg = range_seg.split("alt=")[1]
        min_alt, max_alt = parse_minmax_alt(alt_seg)
        corners = parse_coordinate_sequence(corner_seg)
        r_state = RegionState(rel_timestamp, min_alt, max_alt, corners,
                              airspace_region.RegionStatus.FREE, None, None)
        self.regions[cid] = [r_state]
        # Need to format a tx for this
        self.actions_by_tstep[rel_timestamp].append()
        

    def extract_region_split(self, rel_timestamp, data_seg, split_type):
        pass

    def extract_region_reservation(self, rel_timestamp, data_seg):
        pass

    def extract_owner_update(self, rel_timestamp, data_seg):
        pass

    def extract_status_update(self, rel_timestamp, data_seg):
        pass

    def extract_add_occupant(self, rel_timestamp, data_seg):
        pass


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
    return float(re.sub(r'[^0-9.]', '', target_string))

def regex_format_float_signed(target_string):
    return float(re.sub(r'[^0-9.-]', '', target_string))

def regex_format_int_unsigned(target_string):
    return int(re.sub(r'[^0-9]', '', target_string))

def regex_format_int_signed(target_string):
    return int(re.sub(r'[^0-9-]', '', target_string))

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
    coords = re.findall(r'\(([^()]*)\)', target_string)
    coord_list = []
    if (len(coords[0].split(",")) == 2):
        for item in coords:
            coord_list.append(parse_2d_coordinate(item))
    else:
        for item in coords:
            coord_list.append(parse_3d_coordinate(item))
    return coord_list

def parse_minmax_alt(alt_seg):
    raw_vals = alt_seg.split("<->")
    min_alt = regex_format_float_unsigned(raw_vals[0])
    max_alt = regex_format_float_unsigned(raw_vals[1])
    return (min_alt, max_alt)

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