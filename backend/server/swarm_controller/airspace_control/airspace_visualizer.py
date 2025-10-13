import json
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

from airspace_region import RegionStatus

class AirspaceVisualizer():
    def __init__(self, region_fname, tx_fname):
        self.read_json_files(region_fname, tx_fname)
        self.extract_region_volumes()
        self.extract_region_timebounds()
        self.extract_active_regions()
        self.extract_voxel_dims_lists()
        self.extract_region_status_dicts()
    
    def read_json_files(self, region_fname, tx_fname):
        with open(region_fname, 'r') as file:
            self.region_data = json.load(file)
        with open(tx_fname, 'r') as file:
            self.tx_data = json.load(file)

    def extract_region_volumes(self):
        self.region_volumes = []
        for key in self.region_data.keys():
            self.region_volumes.append(self.produce_volume_corners(self.region_data[key][0])) # single item list w/ dict

    def extract_region_timebounds(self):
        self.last_t = -1
        self.region_times = [(-1, -1) for i in range(len(self.region_volumes))]
        for steps in self.tx_data:
            curr_step = steps['t_step']
            if curr_step > self.last_t:
                self.last_t = curr_step
            for tx in steps['transactions']:
                region_idx = tx['cid']
                if 'CREATE' in tx['tx_type']:
                    self.region_times[region_idx] = (curr_step, self.region_times[region_idx][1])
                if 'SPLIT' in tx['tx_type']:
                    self.region_times[region_idx] = (self.region_times[region_idx][0], curr_step)            

    def extract_active_regions(self):
        self.active_regions_by_tstep = []
        for i in range(self.last_t + 1):
            self.active_regions_by_tstep.append(self.select_regions_timestep(i))

    def select_regions_timestep(self, timestep):
        active_reg = []
        for i in range(len(self.region_times)):
            r_times = self.region_times[i]
            if timestep >= r_times[0] and (timestep < r_times[1] or r_times[1] == -1): # -1 if active at log end
                active_reg.append(i)
        return active_reg

    def extract_voxel_dims_lists(self):
        self.voxel_dims_by_tstep = []
        for i in range(self.last_t + 1):
            self.voxel_dims_by_tstep.append(self.produce_voxel_dims_timestep(i))

    def produce_voxel_dims_timestep(self, timestep):
        lat_set = set()
        lon_set = set()
        alt_set = set()
        active_reg = self.active_regions_by_tstep[timestep]
        for id in active_reg:
            region = self.region_volumes[id]
            a = region[0] # low top left
            b = region[6] # hi bot right
            lat_set.update([a[0], b[0]])
            lon_set.update([a[1], b[1]])
            alt_set.update([a[2], b[2]])
        lat_list = list(lat_set)
        lon_list = list(lon_set)
        alt_list = list(alt_set)
        lat_list.sort()
        lon_list.sort()
        alt_list.sort()
        result = (lat_list, lon_list, alt_list)
        return result

    # low level then high level, top left, bottom left, bottom right, top right
    def produce_volume_corners(self, r_data):
        min_alt = r_data['min_alt']
        max_alt = r_data['max_alt']
        corners = r_data['corners']
        lo = []
        hi = []
        for c in corners:
            lo.append((c[0], c[1], min_alt))
            hi.append((c[0], c[1], max_alt))
        lo.extend(hi)
        return lo
    
    def extract_region_status_dicts(self):
        self.status_lookup_table = {}
        for i in range(self.last_t + 1):
            self.status_lookup_table[i] = {}
        for key in self.region_data.keys():
            ikey = int(key)
            state_list = self.region_data[key]
            for entry in state_list:
                start_t = entry['start_t']
                end_t = entry['end_t']
                status = entry['status']
                if end_t == -1:
                    end_t = self.last_t + 1
                if start_t == end_t:
                    self.status_lookup_table[start_t][ikey] = status
                for i in range(start_t, end_t):
                    self.status_lookup_table[i][ikey] = status

    def render(self):
        pass

def build_grid():
    filled = np.zeros((3, 3, 3), dtype=int)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                if i == j and i == k and j == k:
                    filled[i, j, k] = 1
                else:
                    filled[i, j, k] = 2
    return filled


def get_cross_alt(grid, alt):
    cross_section_voxels = np.zeros_like(grid[:, :, alt], dtype=int)
    cross_section_voxels[:, :] = grid[:, :, alt]
    print(cross_section_voxels.shape)
    return cross_section_voxels.reshape((3, 3, 1))


def get_cross_lon(grid, lon):
    cross_section_voxels = np.zeros_like(grid[:, lon, :], dtype=int)
    cross_section_voxels[:, :] = grid[:, lon, :]
    print(cross_section_voxels.shape)
    return cross_section_voxels.reshape((3, 1, 3))


def get_cross_lat(grid, lat):
    cross_section_voxels = np.zeros_like(grid[lat, :, :], dtype=int)
    cross_section_voxels[:, :] = grid[lat, :, :]
    print(cross_section_voxels.shape)
    return cross_section_voxels.reshape((1, 3, 3))


def get_coloring(grid):
    print(grid)
    colors = np.empty(grid.shape + (4,))
    green_transparent = [0, 1, 0, 0.25]
    red_transparent = [1, 0, 0, 0.25]
    colors[grid == 1] = green_transparent
    colors[grid == 2] = red_transparent
    return colors


if __name__ == "__main__":
    """fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    SCALING_FACTOR = 0.15
    c_lat = 1
    c_lon = 2
    c_alt = 1

    # u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:20j]
    # x = c_lat + (np.cos(u) * np.sin(v) * SCALING_FACTOR)
    # y = c_lon + (np.sin(u) * np.sin(v) * SCALING_FACTOR)
    # z = c_alt + (np.cos(v) * SCALING_FACTOR)

    # 3. Plot the sphere
    # Customize the appearance with `color`, `alpha` (transparency), and `rstride`/`cstride` for grid density
    # ax.plot_surface(x, y, z, color='lightblue', alpha=0.6, rstride=1, cstride=1)

    filled = build_grid()
    coloring = get_coloring(filled)
    # cross = get_cross_alt(filled, 1)
    # cross = get_cross_lat(filled, 0)
    cross = get_cross_lon(filled, 2)
    cross_coloring = get_coloring(cross)
    print(cross.shape)

    # ax.voxels(filled, facecolors=coloring, edgecolor='k')

    # plt.show()
    # plt.pause(5)
    # ax.clear()
    # ax = fig.add_subplot(111, projection="3d")
    ax.voxels(cross, facecolors=cross_coloring, edgecolor="k")
    ax.set_box_aspect(cross.shape)

    plt.show()"""
    av = AirspaceVisualizer("parsed_regions.json", "parsed_tx.json")
