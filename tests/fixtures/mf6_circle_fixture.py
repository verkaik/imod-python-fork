import meshzoo
import numpy as np
import pytest
import xarray as xr
import xugrid as xu

import imod


def make_circle_model():
    nodes, triangles = meshzoo.disk(6, 6)
    nodes *= 1000.0
    grid = xu.Ugrid2d(*nodes.T, -1, triangles)

    nface = len(triangles)
    nlayer = 2

    idomain = xu.UgridDataArray(
        xr.DataArray(
            np.ones((nlayer, nface), dtype=np.int32),
            coords={"layer": [1, 2]},
            dims=["layer", grid.face_dimension],
        ),
        grid=grid,
    )
    icelltype = xu.full_like(idomain, 0)
    k = xu.full_like(idomain, 1.0)
    k33 = k.copy()
    rch_rate = xu.full_like(idomain.sel(layer=1), 0.001, dtype=float)
    bottom = idomain * xr.DataArray([5.0, 0.0], dims=["layer"])
    chd_location = xu.zeros_like(
        idomain.sel(layer=2), dtype=bool
    ).ugrid.binary_dilation(border_value=True)
    constant_head = xu.full_like(idomain.sel(layer=2), 1.0).where(chd_location)

    gwf_model = imod.mf6.GroundwaterFlowModel()
    gwf_model["disv"] = imod.mf6.VerticesDiscretization(
        top=10.0, bottom=bottom, idomain=idomain
    )
    gwf_model["chd"] = imod.mf6.ConstantHead(
        constant_head, print_input=True, print_flows=True, save_flows=True
    )
    gwf_model["ic"] = imod.mf6.InitialConditions(head=0.0)
    gwf_model["npf"] = imod.mf6.NodePropertyFlow(
        icelltype=icelltype,
        k=k,
        k33=k33,
        save_flows=True,
    )
    gwf_model["sto"] = imod.mf6.SpecificStorage(
        specific_storage=1.0e-5,
        specific_yield=0.15,
        transient=False,
        convertible=0,
    )
    gwf_model["oc"] = imod.mf6.OutputControl(save_head="all", save_budget="all")
    gwf_model["rch"] = imod.mf6.Recharge(rch_rate)

    simulation = imod.mf6.Modflow6Simulation("circle")
    simulation["GWF_1"] = gwf_model
    simulation["solver"] = imod.mf6.Solution(
        print_option="summary",
        csv_output=False,
        no_ptc=True,
        outer_dvclose=1.0e-4,
        outer_maximum=500,
        under_relaxation=None,
        inner_dvclose=1.0e-4,
        inner_rclose=0.001,
        inner_maximum=100,
        linear_acceleration="cg",
        scaling_method=None,
        reordering_method=None,
        relaxation_factor=0.97,
    )
    simulation.time_discretization(times=["2000-01-01", "2000-01-02"])
    return simulation


@pytest.fixture(scope="session")
def circle_model():
    return make_circle_model()


@pytest.mark.usefixtures("circle_model")
@pytest.fixture(scope="session")
def circle_result(tmpdir_factory):
    # Using a tmpdir_factory is the canonical way of sharing a tempory pytest
    # directory between different testing modules.
    modeldir = tmpdir_factory.mktemp("circle")
    simulation = make_circle_model()
    simulation.write(modeldir)
    simulation.run()
    return modeldir
