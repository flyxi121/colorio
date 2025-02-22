import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike

from . import observers
from ._helpers import SpectralData
from .cs import ColorSpace, SrgbLinear
from .illuminants import planckian_radiator, spectrum_to_xyz100


def _xyy_from_xyz100(xyz):
    sum_xyz = np.sum(xyz, axis=0)
    x = xyz[0]
    y = xyz[1]
    return np.array([x / sum_xyz, y / sum_xyz, y / 100])


# def _xyy_to_xyz100(xyy):
#     x, y, Y = xyy
#     return np.array([Y / y * x, Y, Y / y * (1 - x - y)]) * 100


def _plot_monochromatic(observer, fill_horseshoe=True):
    # draw outline of monochromatic spectra
    lmbda_nm = np.arange(380, 701)
    values = []
    # TODO vectorize (see <https://github.com/numpy/numpy/issues/10439>)
    for k, _ in enumerate(lmbda_nm):
        data = np.zeros(len(lmbda_nm))
        data[k] = 1.0
        sd = SpectralData(lmbda_nm, data)
        values.append(_xyy_from_xyz100(spectrum_to_xyz100(sd, observer))[:2])
    values = np.array(values)

    # Add the values between the first and the last point of the horseshoe
    t = np.linspace(0.0, 1.0, 101)
    connect = np.outer(values[0], t) + np.outer(values[-1], 1 - t)
    full = np.concatenate([values, connect.T])

    # fill horseshoe area
    if fill_horseshoe:
        plt.fill(*full.T, color=[0.8, 0.8, 0.8], zorder=0)
    # plot horseshoe outline
    plt.plot(
        values[:, 0],
        values[:, 1],
        "-k",
        # label="monochromatic light"
    )
    # plot dotted connector
    plt.plot(connect[0], connect[1], ":k")


def _plot_planckian_locus(observer):
    # plot planckian locus
    values = []
    for temp in np.arange(1000, 20001, 100):
        values.append(
            _xyy_from_xyz100(spectrum_to_xyz100(planckian_radiator(temp), observer))
        )
    values = np.array(values)
    plt.plot(values[:, 0], values[:, 1], ":k", label="Planckian locus")


def plot_xy_gamut(fill_horseshoe=True, plot_planckian_locus=True):
    """Show a flat color gamut, by default xy. There exists a chroma gamut for all
    color models which transform lines in XYZ to lines, and hence have a natural
    decomposition into lightness and chroma components. Also, the flat gamut is the
    same for every lightness value. Examples for color models with this property are
    CIELUV and IPT, examples for color models without are CIELAB and CIECAM02.
    """
    observer = observers.cie_1931_2()
    # observer = observers.cie_1964_10()

    _plot_monochromatic(observer, fill_horseshoe=fill_horseshoe)
    # plt.grid()

    # if plot_rgb_triangle:
    #     _plot_rgb_triangle()
    if plot_planckian_locus:
        _plot_planckian_locus(observer)

    plt.gca().set_aspect("equal")
    # plt.legend()
    plt.xlabel("x")
    plt.ylabel("y")
    return plt


def xy_gamut_mesh(lcar):
    import optimesh
    import pygmsh

    observer = observers.cie_1931_2()

    # Gather all points on the horseshoe outline
    lmbda_nm = np.arange(380, 701)
    all_points = np.empty((len(lmbda_nm), 2))
    for k in range(len(lmbda_nm)):
        data = np.zeros(len(lmbda_nm))
        data[k] = 1.0
        xyz100 = spectrum_to_xyz100(SpectralData(lmbda_nm, data), observer)
        all_points[k] = _xyy_from_xyz100(xyz100)[:2]

    # Generate gmsh geometry: spline + straight line
    all_points = np.column_stack([all_points, np.zeros(len(all_points))])
    with pygmsh.geo.Geometry() as geom:
        gmsh_points = [geom.add_point(pt, lcar) for pt in all_points]
        s1 = geom.add_spline(gmsh_points)
        s2 = geom.add_line(gmsh_points[-1], gmsh_points[0])
        ll = geom.add_curve_loop([s1, s2])
        geom.add_plane_surface(ll)
        mesh = geom.generate_mesh()

    # Work around numpy bug <https://github.com/numpy/numpy/issues/17760>
    cells = mesh.get_cells_type("triangle").astype(int)
    points, cells = optimesh.optimize_points_cells(
        mesh.points, cells, "lloyd", 1.0e-2, 100, omega=2.0
    )
    return points, cells


def get_mono_outline_xy(observer, max_stepsize):
    """Monochromatic light of different frequencies form a horseshoe-like shape in
    xy-space. Get the outline of that space.
    """
    m = observer.lmbda_nm.shape[0]
    mono = np.zeros(m)

    # first the straight connector at the bottom
    mono[:] = 0.0
    mono[-1] = 1.0
    mono_spectrum = SpectralData(observer.lmbda_nm, mono)
    first = _xyy_from_xyz100(spectrum_to_xyz100(mono_spectrum, observer))[:2]
    mono[:] = 0.0
    mono[0] = 1.0
    mono_spectrum = SpectralData(observer.lmbda_nm, mono)
    last = _xyy_from_xyz100(spectrum_to_xyz100(mono_spectrum, observer))[:2]
    #
    diff = first - last
    dist = np.sqrt(np.sum(diff ** 2))
    num_steps = dist / max_stepsize
    num_steps = int(num_steps) + 2
    # connection between lowest and highest frequencies
    vals_conn = np.array(
        [first * (1 - t) + last * t for t in np.linspace(0, 1, num_steps)]
    )

    vals_mono = [vals_conn[-1]]
    for k in range(1, m):
        mono[:] = 0.0
        mono[k] = 1.0
        mono_spectrum = SpectralData(observer.lmbda_nm, mono)
        val = _xyy_from_xyz100(spectrum_to_xyz100(mono_spectrum, observer))[:2]

        diff = vals_mono[-1] - val
        dist = np.sqrt(np.dot(diff, diff))

        if dist > max_stepsize:
            vals_mono.append(val)
    vals_mono.append(vals_conn[0])
    vals_mono = np.array(vals_mono)

    return vals_mono, vals_conn


def plot_srgb1_gradient(colorspace, srgb0, srgb1, n=256):
    srgb = get_srgb1_gradient(colorspace, srgb0, srgb1, n=n)

    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("empty", srgb, n)

    gradient = np.linspace(0.0, 1.0, n)
    gradient = np.vstack((gradient, gradient))
    plt.imshow(gradient, aspect="auto", cmap=cmap)
    plt.axis("off")
    plt.title(f"SRGB gradient in {colorspace.name}")
    return plt


def get_srgb1_gradient(
    colorspace: ColorSpace, srgb0: ArrayLike, srgb1: ArrayLike, n: int
) -> np.ndarray:
    # convert to colorspace
    s = SrgbLinear()

    def to_cs(srgb):
        return colorspace.from_xyz100(s.to_xyz100(s.from_rgb1(srgb)))

    def to_rgb1(vals):
        return s.to_rgb1(s.from_xyz100(colorspace.to_xyz100(vals), mode="clip"))

    cs = [to_cs(srgb0), to_cs(srgb1)]

    # linspace
    ls = np.linspace(cs[0], cs[1], endpoint=True, num=n, axis=0)

    # back to srgb
    return to_rgb1(ls.T).T


def plot_srgb255_gradient(
    colorspace: ColorSpace, srgb0: ArrayLike, srgb1: ArrayLike, n: int = 256
):
    srgb0 = np.asarray(srgb0)
    srgb1 = np.asarray(srgb1)
    return plot_srgb1_gradient(colorspace, srgb0 / 255, srgb1 / 255, n)


def get_srgb255_gradient(
    colorspace: ColorSpace, srgb0: ArrayLike, srgb1: ArrayLike, n: int
) -> np.ndarray:
    srgb0 = np.asarray(srgb0)
    srgb1 = np.asarray(srgb1)
    return get_srgb1_gradient(colorspace, srgb0 / 255, srgb1 / 255, n) * 255


def plot_primary_srgb_gradients(colorspace: ColorSpace, n: int = 256):
    pairs = [
        [([1, 1, 1], [1, 0, 0]), ([1, 0, 0], [0, 1, 0])],
        [([1, 1, 1], [0, 1, 0]), ([0, 1, 0], [0, 0, 1])],
        [([1, 1, 1], [0, 0, 1]), ([0, 0, 1], [1, 0, 0])],
        [([0, 0, 0], [1, 0, 0]), ([1, 0, 0], [0, 1, 1])],
        [([0, 0, 0], [0, 1, 0]), ([0, 1, 0], [1, 0, 1])],
        [([0, 0, 0], [0, 0, 1]), ([0, 0, 1], [1, 1, 0])],
    ]
    fig, axes = plt.subplots(len(pairs), 2)
    for i in range(len(pairs)):
        for j in range(2):
            pair = pairs[i][j]
            ax = axes[i][j]
            srgb = get_srgb1_gradient(colorspace, pair[0], pair[1], n=n)

            cmap = matplotlib.colors.LinearSegmentedColormap.from_list("", srgb, n)

            gradient = np.linspace(0.0, 1.0, n)
            gradient = np.vstack((gradient, gradient))
            ax.imshow(gradient, aspect="auto", cmap=cmap)
            ax.axis("off")
    fig.suptitle(f"primary SRGB gradients in {colorspace.name}")
    return plt
