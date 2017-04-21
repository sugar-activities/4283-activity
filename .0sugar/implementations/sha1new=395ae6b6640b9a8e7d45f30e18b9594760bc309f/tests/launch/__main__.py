import unittest

import os
import sys
# 0compile fails otherwise if use `python .` to start tests
sys.path[0] = os.path.abspath(os.curdir)

from synthesis import *
from launch import *


if __name__ == '__main__':
    unittest.main()
