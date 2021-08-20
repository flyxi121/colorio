import json
import pathlib

import numpy as np

from ..helpers import ColorDistanceDataset


class RitDupont(ColorDistanceDataset):
    def __init__(self):
        this_dir = pathlib.Path(__file__).resolve().parent

        with open(this_dir / "rit-dupont.json") as f:
            data = json.load(f)

        xyz = np.asarray(data["xyz"])
        pairs = np.asarray(data["pairs"])

        # parameters as used in
        #
        # Melgosa, Huertas, Berns,
        # Performance of recent advanced color-difference formulas using the
        # standardized residual sum of squares index
        # J. Opt. Soc. Am. A/ Vol. 25, No. 7/ July 2008,
        # <https://doi.org/10.1364/JOSAA.25.001828>.
        self.c = 0.69  # average
        self.L_A = 127.3
        self.Yb = 10.9

        super().__init__("RIT-DuPont", data["dv"], xyz[pairs])
