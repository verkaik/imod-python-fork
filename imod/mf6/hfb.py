import numpy as np
import xarray as xr
import xugrid as xu

from imod.mf6.pkgbase import BoundaryCondition
from imod.schemata import (
    AnyValueSchema,
    CoordsSchema,
    DimsSchema,
    DTypeSchema,
    IndexesSchema,
)


def edge_to_cell(notnull, arrdict, layer, idomain, grid):
    nlayer = idomain["idomain_layer"].size
    idomain2d = idomain.values.reshape((nlayer, -1))
    no_layer_dim = notnull.ndim == 1
    edge_faces = grid.edge_face_connectivity

    # Fill in the indices
    # For every edge, find the connected faces.
    if no_layer_dim:
        edge = np.argwhere(notnull).transpose()[0]
        layer = layer - 1
        cell2d = edge_faces[edge]
        valid = ((cell2d != grid.fill_value) & (idomain2d[layer, cell2d] > 0)).all(
            axis=1
        )
    else:
        layer, edge = np.argwhere(notnull).transpose()
        layer2d = np.repeat(layer, 2).reshape((-1, 2))
        cell2d = edge_faces[edge]
        valid = ((cell2d != grid.fill_value) & (idomain2d[layer2d, cell2d] > 0)).all(
            axis=1
        )
        layer = layer[valid]

    # Skip the exterior edges (marked with a fill value).
    cell2d = cell2d[valid]
    c = arrdict["resistance"][notnull][valid]
    return layer, cell2d, c


def dis_recarr(arrdict, layer, notnull, idomain, grid):
    # Define the numpy structured array dtype
    index_spec = [
        ("layer_1", np.int32),
        ("row_1", np.int32),
        ("column_1", np.int32),
        ("layer_2", np.int32),
        ("row_2", np.int32),
        ("column_2", np.int32),
    ]
    field_spec = [(key, np.float64) for key in arrdict]
    sparse_dtype = np.dtype(index_spec + field_spec)
    # Find the indices
    layer, cell2d, c = edge_to_cell(notnull, arrdict, layer, idomain, grid)
    shape = (idomain["y"].size, idomain["x"].size)
    row_1, column_1 = np.unravel_index(cell2d[:, 0], shape)
    row_2, column_2 = np.unravel_index(cell2d[:, 1], shape)
    # Set the indices
    recarr = np.empty(len(cell2d), dtype=sparse_dtype)
    recarr["layer_1"] = layer + 1
    recarr["layer_2"] = recarr["layer_1"]
    recarr["row_1"] = row_1 + 1
    recarr["column_1"] = column_1 + 1
    recarr["row_2"] = row_2 + 1
    recarr["column_2"] = column_2 + 1
    recarr["resistance"] = c
    return recarr


def disv_recarr(arrdict, layer, notnull, idomain, grid):
    # Define the numpy structured array dtype
    index_spec = [
        ("layer_1", np.int32),
        ("cell2d_1", np.int32),
        ("layer_2", np.int32),
        ("cell2d_2", np.int32),
    ]
    field_spec = [(key, np.float64) for key in arrdict]
    sparse_dtype = np.dtype(index_spec + field_spec)
    # Initialize the structured array
    layer, cell2d, c = edge_to_cell(notnull, arrdict, layer, idomain, grid)
    # Set the indices
    recarr = np.empty(len(cell2d), dtype=sparse_dtype)
    recarr["layer_1"] = layer + 1
    recarr["layer_2"] = recarr["layer_1"]
    recarr["cell2d_1"] = cell2d[:, 0] + 1
    recarr["cell2d_2"] = cell2d[:, 1] + 1
    recarr["resistance"] = c
    return recarr


class HorizontalFlowBarrier(BoundaryCondition):
    """
    Horizontal Flow Barrier (HFB) package

    Input to the Horizontal Flow Barrier (HFB) Package is read from the file that has type “HFB6” in the
    Name File.
    Only one HFB Package can be specified for a GWF model.
    https://water.usgs.gov/water-resources/software/MODFLOW-6/mf6io_6.2.2.pdf

    Parameters
    ----------
    resistance: xugrid.UgridDataArray
        resistance of the barrier. Negative values are interpreted as a
        multiplier of the conductance.
    idomain: xugrid.UgridDataArray or xr.DataArray

    Examples
    --------
    The easiest way to create a horizontal flow barrier is by using
    ``xugrid.snap_to_grid``, which snaps to the line geometry of a ``geopandas.GeoDataFrame``
    to a ``xugrid.Ugrid2d`` topology. Note that a layer coordinate is required.

    >> snapped, snapped_gdf = xugrid.snap_to_grid(gdf, grid=idomain)
    >> resistance = snapped["resistance"].assign_coords(layer=1)
    >> hfb = imod.mf6.HorizontalFlowBarrier(resistance=resistance)

    """

    _pkg_id = "hfb"
    _init_schemata = {
        "resistance": [
            DTypeSchema(np.floating),
            IndexesSchema(),
            CoordsSchema(("layer",)),
            DimsSchema("layer", "{edge_dim}") | DimsSchema("{edge_dim}"),
        ],
        "idomain": [
            DTypeSchema(np.integer),
            DimsSchema("idomain_layer", "y", "x")
            | DimsSchema("idomain_layer", "{face_dim}"),
            IndexesSchema(),
        ],
    }
    _write_schemata = {
        "idomain": (AnyValueSchema(">", 0),),
    }
    _period_data = ("resistance",)
    _keyword_map = {}
    _template = BoundaryCondition._initialize_template(_pkg_id)

    def __init__(
        self,
        resistance,
        idomain,
        print_input=False,
    ):
        super().__init__(locals())
        self.dataset["resistance"] = resistance
        if "layer" in idomain.dims:
            idomain = idomain.rename({"layer": "idomain_layer"})
        self.dataset["idomain"] = idomain
        self.dataset["print_input"] = print_input

    def to_sparse(self, arrdict, layer):
        data = next(iter(arrdict.values()))
        grid = self.dataset.ugrid.grid
        notnull = ~np.isnan(data)
        idomain = self.dataset["idomain"]
        if isinstance(idomain, xr.DataArray):
            recarr = dis_recarr(arrdict, layer, notnull, idomain, grid)
        elif isinstance(idomain, xu.UgridDataArray):
            recarr = disv_recarr(arrdict, layer, notnull, idomain, grid)
        else:
            raise TypeError(
                "self.dataset should be xarray.Dataset or xugrid.UgridDataset,"
                f" is {type(self.dataset)} instead"
            )
        return recarr

    def write(self, directory, pkgname, globaltimes, binary):
        super().write(directory, pkgname, globaltimes, binary=False)
