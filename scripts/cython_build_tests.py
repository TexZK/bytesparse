import os

os.chdir(os.path.join('..', 'tests'))
os.system(r'cythonize -f -a -i _test_c.pyx')
