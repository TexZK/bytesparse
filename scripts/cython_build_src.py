import os

# working directory = repository root folder
path = os.path.join('src', 'bytesparse', '_c.pyx')
os.system(r'cythonize -f -i ' + path)
