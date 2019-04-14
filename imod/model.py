"""
Contains an imodseawat model object
"""
from collections import UserDict

import imod.pkg
import jinja2
from imod.io import util
from imod.pkg.pkggroup import (
    DrainageGroup,
    GeneralHeadBoundaryGroup,
    PackageGroups,
    RiverGroup,
)


def _to_datetime(time):
    """
    Check whether time is cftime object, else convert to datetime64 series.
    
    cftime currently has no pd.to_datetime equivalent:
    a method that accepts a lot of different input types.
    
    Parameters
    ----------
    time : cftime object or datetime-like scalar
    """
    if isinstance(time, cftime.datetime):
        return time
    else:
        return pd.to_datetime(time)


def _time_discretisation(times):
    """
    Generates dictionary containing stress period time discretisation data.

    Parameters
    ----------
    times : np.array
        Array containing containing time in a datetime-like format
    
    Returns
    -------
    OrderedDict
        OrderedDict with dates as strings for keys,
        stress period duration (in days) as values.
    """

    times = [_to_datetime(t) for t in times]

    d = OrderedDict()
    for start, end in zip(times[:-1], times[1:]):
        period_name = start.strftime("%Y%m%d%H%M%S")
        timedelta = end - start
        duration = timedelta.days + timedelta.seconds / 86400.0
        d[period_name] = duration
    return d


# This class allows only imod packages as values
class Model(UserDict):
    def __init__(self, ibound):
        dict.__init__(self)
        self["ibound"] = ibound

    def __setitem__(self, key, value):
        # TODO: raise ValueError on setting certain duplicates
        # e.g. two solvers
        if not hasattr(value, "_pkg_id"):
            raise ValueError("not a package")
        dict.__setitem__(self, key, value)

    def update(self, *arg, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v


class SeawatModel(Model):
    """
    Examples
    --------
    m = SeawatModel("example")
    m["riv"] = River(...)
    ...etc.
    m.time_discretization(endtime)
    m.write()
    """

    # These templates end up here since they require global information
    # from more than one package
    _PACKAGE_GROUPS = PackageGroups

    _gen_template = jinja2.Template(
        "[gen]\n"
        "    modelname = {{modelname}}\n"
        "    writehelp = {{writehelp}}\n"
        "    result_dir = {{modelname}}\n"
        "    packages = {{package_set|join(",
        ")}}\n"
        "    coord_xll = {{xmin}}\n"
        "    coord_yll = {{ymin}}\n"
        "    start_year = {{start_date[:4]}}\n"
        "    start_month = {{start_date[4:6]}}\n"
        "    start_day = {{start_date[6:8]}}\n",
    )

    def __init__(self, modelname):
        self["modelname"] = modelname

    def _group(self):
        """
        Group multiple systems of a single package
        E.g. all river or drainage sub-systems
        """
        groups = {}
        has_group = set()
        groupable = set(self._PACKAGE_GROUPS.__members__.keys())
        for key, package in self.items():
            pkg_id = package._pkg_id
            if pkg_id in groupable:
                if pkg_id in has_group:  # already exists
                    groups[pkg_id][key] = package
                else:
                    groups[pkg_id] = {key: package}
                    has_group.update(pkg_id)

        package_groups = []
        for pkg_id, group in groups:
            # Create PackageGroup for every package
            # RiverGroup for rivers, DrainageGroup for drainage, etc.
            package_groups.append(self._PACKAGE_GROUPS[pkg_id].value(**group))

        return package_groups

    def time_discretisation(self, endtime):
        """
        Collect all unique times
        """
        # TODO: check for cftime, force all to cftime if necessary
        times = set()  # set only allows for unique values
        for ds in self.values():
            if "time" in ds.coords:
                times.update(ds.coords["time"].values)
        # TODO: check that endtime is later than all other times.
        times.update(endtime)
        duration = _time_discretisation(times)
        # Generate time discretization, just rely on default arguments
        # Probably won't be used that much anyway?
        self["time_discretization"] = imod.pkg.TimeDiscretization(
            time=times, timestep_duration=duration
        )

    def _get_pkgkey(self, pkg_id):
        """
        Get package key that belongs to a certain pkg_id, since the keys are
        user specified.
        """
        key = [pkgname for pkgname, pkg in self.items() if pkg._pkg_id == pkg_id]
        nkey = len(key)
        if nkey > 1:
            raise ValueError(f"Multiple instances of {key} detected")
        elif nkey == 1:
            return key[0]
        else:
            return None

    def _render_gen(self, modelname, globaltimes, writehelp=False):
        package_set = set([pkg._pkg_id for pkg in self.values()])
        baskey = self._get_pkgkey("bas")
        bas = self[baskey]
        _, xmin, xmax, _, ymin, ymax = util.spatial_reference(bas["ibound"])
        d = {}
        d["xmin"] = xmin
        d["xmax"] = xmax
        d["ymin"] = ymin
        d["ymax"] = ymax
        d["package_set"] = package_set
        d["start_date"] = globaltimes.keys()[0]
        d["writehelp"] = writehelp
        return self._gen_template.render(d)

    def _render(self, key, directory, globaltimes):
        """
        Rendering method for straightforward packages
        """
        key = self._get_pkgkey(key)
        if key is None:
            # Maybe do enum look for full package name?
            raise ValueError(f"No {key} package provided.")
        return self[key].render(directory=directory, globaltimes=globaltimes)

    def _render_dis(self, directory):
        baskey = self._get_pkgkey("bas")
        diskey = self._get_pkgkey("dis")
        bascontent = self[baskey]._render_dis(directory=directory)
        discontent = self[diskey]._render(directory=directory)
        return bascontent + discontent

    def _render_groups(self, directory, globaltimes):
        package_groups = self._group()
        content = [
            group.render(directory, globaltimes) for group in package_groups.values()
        ]
        ssm_content = [
            group.render_ssm(directory, globaltimes)
            for group in package_groups.values()
        ]
        # TODO: do this in a single pass, combined with _n_max_active for modflow part?
        n_sinkssources = sum(
            [group.max_n_sinkssources() for group in package_groups.values()]
        )
        ssm_content = f"[ssm]\n    mxss = {n_sinkssources}\n" + ssm_content
        return content, ssm_content

    def _render_flowsolver(self):
        pcgkey = self._get_pkgkey("pcg")
        pksfkey = self._get_pkgkey("pksf")
        if pcgkey and pksfkey:
            raise ValueError("pcg and pksf solver both provided. Provide only one.")
        if not pcgkey and not pksfkey:
            raise ValueError("No flow solver provided")
        if pcgkey:
            return self[pcgkey]._render()
        else:
            return self[pksfkey]._render()

    def _render_btn(self, directory):
        btnkey = self._get_pkgkey("btn")
        diskey = self._get_pkgkey("dis")
        if btnkey is None:
            raise ValueError("No BasicTransport package provided.")
        btncontent = self[btnkey]._render(directory)
        discontent = self[diskey]._render_btn()
        return btncontent + discontent

    def _render_transportsolver(self):
        gcgkey = self._get_pkgkey("pcg")
        pkstkey = self._get_pkgkey("pksf")
        if gcgkey and pkstkey:
            raise ValueError("gcg and pkst solver both provided. Provide only one.")
        if not gcgkey and not pkstkey:
            raise ValueError("No transport solver provided")
        if gcgkey:
            return self[gcgkey]._render()
        else:
            return self[pkstkey]._render()

    def render(self, writehelp=False):
        """
        Render the runfile as a string, package by package.
        """
        diskey = self._get_pkgkey("dis")
        globaltimes = self[diskey]["time"].values
        directory = self["modelname"]

        modflowcontent, ssmcontent = self._render_groups(
            directory=directory, globaltimes=globaltimes
        )

        content = []
        content.append(
            self._render_gen(
                modelname=self["modelname"],
                globaltimes=globaltimes,
                writehelp=writehelp,
            )
        )
        content.append(self._render_dis())
        # Modflow
        for key in ("bas", "occ", "lpf", "rch"):
            content.append(
                self._render(key=key, directory=directory, globaltimes=globaltimes)
            )
        content.append(modflowcontent)
        content.append(self._render_flowsolver())

        # MT3D and Seawat
        content.append(self._render_btn())
        for key in ("vdf", "adv", "dsp"):
            self._render(key=key, directory=directory, globaltimes=globaltimes)
        content.append(ssmcontent)
        content.append(self._render_transportsolver())

        return "".join(content)

    def save(self, directory):
        for ds in self.values():
            if isinstance(ds, imod.pkg.Well):
                # TODO: implement
                raise NotImplementedError
            else:
                for name, da in ds.data_vars.items():
                    if "y" in da.coords and "x" in da.coords:
                        imod.io.idf.save(directory, da)

    def write(self):
        # TODO: just write to an arbitrary directory
        runfile_content = self.render()
        runfilepath = f"{self["modelname"]}.run"
        # Write the runfile
        with open(runfilepath, "w") as f:
            f.write(runfile_content)
        # Write all IDFs and IPFs
        self.save(self["modelname"])
