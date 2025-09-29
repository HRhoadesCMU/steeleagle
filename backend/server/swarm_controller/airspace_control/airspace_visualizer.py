import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np


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
    fig = plt.figure()
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

    plt.show()
