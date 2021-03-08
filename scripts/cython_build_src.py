import os

os.chdir(os.path.join('..', 'src', 'bytesparse'))
os.system(r'cythonize -f -a -i _c.pyx')
