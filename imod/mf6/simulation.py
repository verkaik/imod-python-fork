import collections
import pathlib

import numpy as np
import xarray as xr

import imod


class Modflow6Simulation(collections.UserDict):
    def __init__(self, name):
        super(__class__, self).__init__()
        self.name = name

    def __setitem__(self, key, value):
        # Synchronize names
        if isinstance(imod.mf6.model.Modflow6, value):
            value.modelname = key
        super(__class__, self).__setitem__(key, value)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def time_discretization(self, endtime, starttime=None, *times):
        """
        Collect all unique times
        """
        self.use_cftime = any([model._use_cftime() for model in self.values()])

        times = [imod.wq.timeutil.to_datetime(time, self.use_cftime) for time in times]
        for model in self.values():
            times.append(model._yield_times())

        # TODO: check that endtime is later than all other times.
        times.append(imod.wq.timeutil.to_datetime(endtime, self.use_cftime))
        if starttime is not None:
            times.append(imod.wq.timeutil.to_datetime(starttime, self.use_cftime))

        # np.unique also sorts
        times = np.unique(np.hstack(times))

        duration = imod.wq.timeutil.timestep_duration(times, self.use_cftime)
        # Generate time discretization, just rely on default arguments
        # Probably won't be used that much anyway?
        timestep_duration = xr.DataArray(
            duration, coords={"time": np.array(times)[:-1]}, dims=("time",)
        )
        self["time_discretization"] = imod.mf6.TimeDiscretization(
            timestep_duration=timestep_duration
        )

    def render(self):
        """Renders simulation namefile"""
        # includes timing, models, exchanges, solution groups
        return ""

    def write(self, directory="."):
        if isinstance(directory, str):
            directory = pathlib.Path(directory)
        directory.mkdir(exist_ok=True, parents=True)

        # Write simulation namefile
        mfsim_content = self.render()
        mfsim_path = directory / "mfsim.nam"
        with open(mfsim_path, "w") as f:
            f.write(mfsim_content)

        # Write time discretization file
        self["time_discretization"].write(directory)

        # Write solution groups
        # TODO: where is the mapping between model and solution group?
        # not very relevant now, all models will belong to a single solution
        for key, solution in self.items():
            try:
                if solution._pkg_id == "ims":
                    solution.write(directory, key)
            except AttributeError:
                continue

        # Write individual models
        globaltimes = self["time_discretization"]["time"].values
        for model in self.values():
            # skip timedis, solution group, and exchanges
            if hasattr(model, "modelname"):
                model.write(directory, globaltimes)
