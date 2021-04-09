from imod.flow.pkgbase import Package
import numpy as np

class HorizontalHydraulicConductivity(Package):
    """
    Specify horizontal hydraulic conductivity of the aquifers.

    Assigning this package to a model means you chose MODFLOW 2005's
    "Layer Property Flow (LPF)" schematization.
    Assigning packages of the Block Centered Flow (BCF) as well
    to the model will result in errors.

    Parameters
    ----------
    k_horizontal : xr.DataArray
        Horizontal hydraulic conductivity, dims = ("layer", "y", "x").
    """

    _pkg_id = "khv"
    _variable_order = ["k_horizontal"]

    def __init__(self, k_horizontal=None):
        super(__class__, self).__init__()
        self.dataset["k_horizontal"] = k_horizontal

    def _pkgcheck(self, active_cells=None):
        vars_to_check = ["k_horizontal"]
        self._check_if_nan_in_active_cells(
            active_cells=active_cells, 
            vars_to_check=vars_to_check
            )

class VerticalHydraulicConductivity(Package):
    """
    Specify vertical hydraulic conductivity for aquitards (between BOT and TOP)
    To specify the vertical hydraulic conductivity for aquifers,
    use "VerticalAnisotropy" in combination with HorizontalHydraulicConductivity.

    Assigning this package to a model means you chose MODFLOW 2005's
    "Layer Property Flow (LPF)" schematization.
    Assigning packages of the Block Centered Flow (BCF) as well
    to the model will result in errors.

    Parameters
    ----------
    k_vertical : xr.DataArray
        Vertical hydraulic conductivity, dims = ("layer", "y", "x").
    """

    _pkg_id = "kvv"
    _variable_order = ["k_vertical"]

    def __init__(self, k_vertical=None):
        super(__class__, self).__init__()
        self.dataset["k_vertical"] = k_vertical

    def _pkgcheck(self, active_cells=None):
        vars_to_check = ["k_vertical"]
        self._check_if_nan_in_active_cells(
            active_cells=active_cells, 
            vars_to_check=vars_to_check
            )

class VerticalAnistropy(Package):
    """
    Specify the vertical anisotropy for aquifers, defined as the
    vertical hydraulic conductivity over the horizontal
    hydraulic conductivity.

    vertical_anistropy : xr.DataArray
        Vertical anistropy factor (Kv/Kh), dims = ("layer", "y", "x").
    """

    _pkg_id = "kva"
    _variable_order = ["vertical_anistropy"]

    def __init__(self, vertical_anistropy=None):
        super(__class__, self).__init__()
        self.dataset["vertical_anistropy"] = vertical_anistropy

    def _pkgcheck(self, active_cells=None):
        vars_to_check = ["vertical_anistropy"]
        self._check_if_nan_in_active_cells(
            active_cells=active_cells, 
            vars_to_check=vars_to_check
            )
