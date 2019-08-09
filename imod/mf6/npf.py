from imod.mf6.pkgbase import Package


class NodePropertyFlow(Package):
    """
    Attributes
    ----------

    cell_averaging : str
        Method calculating horizontal cell connection conductance.
        Options: {"harmonic", "logarithmic", "mean-log_k", "mean-mean_k"}
    

    """

    _pkg_id = "npf"
    _binary_data = (
        "celltype",
        "k",
        "rewet_layer",
        "k22",
        "k33",
        "angle1",
        "angle2",
        "angle3",
    )

    def __init__(
        self,
        celltype,
        k,
        rewet=False,
        rewet_layer=None,
        rewet_factor=None,
        rewet_iterations=None,
        rewet_method=None,
        k22=None,
        k33=None,
        angle1=None,
        angle2=None,
        angle3=None,
        cell_averaging="harmonic",
        save_flows=False,
        starting_head_as_confined_thickness=False,
        variable_vertical_conductance=False,
        dewatered=False,
        perched=False,
        save_specific_discharge=False,
    ):
        super(__class__, self).__init__()
        # check rewetting
        if not rewet and any(rewet_layer, rewet_factor, rewet_iterations, rewet_method):
            raise ValueError(
                "rewet_layer, rewet_factor, rewet_iterations, and rewet_method should"
                " all be left at a default value of None if rewet is False."
            )
        self["celltype"] = celltype
        self["k"] = k
        self["rewet"] = rewet
        self["rewet_layer"] = rewet_layer
        self["rewet_factor"] = rewet_factor
        self["rewet_iterations"] = rewet_iterations
        self["rewet_method"] = rewet_method
        self["k22"] = k22
        self["k33"] = k33
        self["angle1"] = angle1
        self["angle2"] = angle2
        self["angle3"] = angle3
        self["cell_averaging"] = cell_averaging
        self["save_flows"] = save_flows
        self[
            "starting_head_as_confined_thickness"
        ] = starting_head_as_confined_thickness
        self["variable_vertical_conductance"] = variable_vertical_conductance
        self["dewatered"] = dewatered
        self["perched"] = perched
        self["save_specific_discharge"] = save_specific_discharge
