#!/glade/work/zji/conda-envs/pg-gdex/bin/python
# -*- coding: utf-8 -*-
#  2026-09-23, zji@ucar.edu, created for a standalone version of gdexdrop
#
#  Copy this file to a common area, such as /glade/u/home/gdexdata/bin, so that
#  users without the conda environment or a venv activated can run gdexdrop.
#  The shebang and pgpath below name the environment gdexdrop is installed in.
#
#  Run directly, it executes as the CALLING user, so the dropped files are owned
#  by the caller.  To have them owned by 'gdexdata' for a caller outside the DECS
#  group, compile a 4755 cmwrapper binary that execs this script:
#
#     pywrapper-install -m gdexdrop -t <common area>/gdexdrop_standalone.py \
#                       -d <common area>
import re
import sys
pgpath = '/glade/work/zji/conda-envs/pg-gdex/lib/python3.12/site-packages'
if pgpath not in sys.path: sys.path.insert(0, pgpath)

from rda_python_miscs.gdexdrop import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
