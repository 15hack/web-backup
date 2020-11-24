import py7zlib
import tempfile
from subprocess import DEVNULL, STDOUT, check_call
import os
from glob import glob
import yaml

def get_yml(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        return list(yaml.load_all(f, Loader=yaml.FullLoader))

def find_value(o, *args, avoid=None):
    if avoid is None:
        avoid = (None, )
    elif isinstance(avoid, tuple):
        avoid = (None, ) + avoid
    else:
        avoid = (None, avoid)
    for a in args:
        a = o.get(a)
        if a not in avoid:
            return a

def chunks(arr, size):
    r=[]
    for a in arr:
        r.append(a)
        if len(r)==size:
            yield r
            r=[]
    if r:
        yield r

def unzip(fl, path=None, get=None):
    if path is None:
        path = tempfile.mkdtemp()
    with open(fl, "rb") as f:
        f7z = py7zlib.Archive7z(f)
        for name in f7z.getnames():
            outfilename = os.path.join(path, name)
            outdir = os.path.dirname(outfilename)
            os.makedirs(outdir, exist_ok=True)
            with open(outfilename, 'wb') as outfile:
                outfile.write(f7z.getmember(name).read())
    if get is not None:
        get = sorted(glob(path+"/"+get))
        if len(get)==1:
            return get[0]
        return get
    return path

def read(fl):
    with open(fl, "r") as f:
        return f.read()
