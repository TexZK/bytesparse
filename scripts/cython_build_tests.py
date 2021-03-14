import os
import sys

# working directory = repository root folder
sys.path.append('src')
path = os.path.join('tests', '_test_c.pyx')
os.system(r'cythonize -f -a -i ' + path)
