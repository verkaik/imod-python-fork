from pathlib import Path

import imod
from imod.mf6.model import GroundwaterFlowModel
from imod.mf6.simulation import Modflow6Simulation
from imod.typing.grid import GridDataArray, merge


def merge_heads(simulation_dir: Path, simulation: Modflow6Simulation) -> GridDataArray:
    """
    This function merges the head output of a split simulation into a single
    head file. Both structured and unstructured grids are supported.
    """
    model_names = list(
        simulation.get_models_of_type(GroundwaterFlowModel._model_id).keys()
    )
    heads = []
    for modelname in model_names:
        modelDirectory = simulation_dir / modelname
        grb_path = _get_grb_file_path(modelDirectory)
        head = imod.mf6.open_hds(
            modelDirectory / f"{modelname}.hds",
            grb_path,
        )
        heads.append(head)

    head = merge(heads)
    return head["head"]


def _get_grb_file_path(model_directory: Path) -> Path:
    """
    Given a directory path, returns the path of the grb file in it. Raises an
    exception if there is not exactly 1 grb file in it.
    """

    grb_files = list(model_directory.glob("*.grb"))
    if len(grb_files) != 1:
        raise RuntimeError(
            f"there should be exactly one grb file in directory {model_directory}."
        )
    return grb_files[0]
