import os

# working directory = repository root folder
path = os.path.join('tests', '_test_c.pyx')
os.system(r'cythonize -f -a -i ' + path)
