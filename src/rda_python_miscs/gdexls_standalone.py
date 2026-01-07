#!/glade/work/zji/conda-envs/pg-gdex/bin/python
# -*- coding: utf-8 -*-
#  2025-09-23, zji@ucar.edu, created for a standalone version of gdexls
import re
import sys
pgpath = '/glade/work/zji/conda-envs/pg-gdex/lib/python3.12/site-packages'
if pgpath not in sys.path: sys.path.insert(0, pgpath)

from rda_python_miscs.gdexls import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
