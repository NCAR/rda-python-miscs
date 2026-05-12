# rda_python_miscs

RDA Python package to hold miscellaneous utility programs for the
[NSF NCAR Geoscience Data Exchange (GDEX)](https://gdex.ucar.edu).

## Programs

The package provides two categories of programs:

**Run as current user (no setuid required):**

| Command | Alias | Description |
|---------|-------|-------------|
| `bashqsub` | | Submit bash batch jobs |
| `tcshqsub` | | Submit tcsh batch jobs |
| `rdasub` | `gdexsub` | Submit RDA batch jobs |
| `pgwget` | | Download files via wget |
| `rdals` | `gdexls` | List files with GDEX metadata |
| `rdaps` | `gdexps` | List running RDA processes |
| `rdazip` | `gdexzip` | Zip/unzip RDA data files |
| `rdaown` | `gdexown` | Change file ownership to gdexdata |
| `pgrst` | | Convert .usg files to RST and push to gdex-docs-* repos on GitHub for readthedocs.io |

**Run as gdexdata via setuid (requires setup below):**

| Command | Alias | Connector script | Description |
|---------|-------|-----------------|-------------|
| `rdacp` | `gdexcp` | `setuid_rdacp` / `setuid_gdexcp` | Copy files as gdexdata |
| `rdakill` | `gdexkill` | `setuid_rdakill` / `setuid_gdexkill` | Kill processes as gdexdata |
| `rdamod` | `gdexmod` | `setuid_rdamod` / `setuid_gdexmod` | Modify files as gdexdata |

## Setuid Setup

The setuid programs (`rdacp`, `rdakill`, `rdamod` and their `gdex*` aliases)
execute as the common user `gdexdata` via the `rda_python_setuid` mechanism.
`rda_python_setuid` is declared as a dependency and installed automatically
with this package.

### Environment setup

#### Option A — Python venv (DECS machines)

```bash
python3 -m venv $ENVHOME          # e.g. /glade/u/home/gdexdata/gdexmsenv
source $ENVHOME/bin/activate
pip install rda_python_miscs
```

#### Option B — Conda (DAV/Casper)

```bash
conda activate pg-gdex            # e.g. /glade/work/gdexdata/conda-envs/pg-gdex
pip install rda_python_miscs
```

### Full setuid install (requires sudo access to gdexdata)

Run these steps once per environment after `pip install`:

```bash
# Compile the pywrapper C binary (once per environment):
pywrapper-install --user gdexdata

# Wire up each setuid program:
pywrapper-install --link rdacp   --user gdexdata
pywrapper-install --link gdexcp  --user gdexdata
pywrapper-install --link rdakill --user gdexdata
pywrapper-install --link gdexkill --user gdexdata
pywrapper-install --link rdamod   --user gdexdata
pywrapper-install --link gdexmod  --user gdexdata
```

`pywrapper-install` with no arguments displays the full user guide.

### Simple install (no sudo required, runs as current user)

Users who do not need the setuid mechanism can create direct symlinks instead:

```bash
pywrapper-install --link rdacp    --simple
pywrapper-install --link gdexcp   --simple
pywrapper-install --link rdakill  --simple
pywrapper-install --link gdexkill --simple
pywrapper-install --link rdamod   --simple
pywrapper-install --link gdexmod  --simple
```

Each command creates `bin/<name> -> bin/setuid_<name>` and the program runs
as the current user with no privilege change.
