"""Fetch pinned official Pyodide core build for CI, verify archive SHA-256."""
from pathlib import Path
import hashlib,sys,tarfile,urllib.request
PINS={
 '0.29.5':'ab08aafc11a3c9a0fe73825eb2cec78bda9464348dd17414e7ec0132ef3451e8',
 '314.0.8':'ff3e5f9d9bc8e98ff30b99515535fc24d375994f47a978c61975d653e162ca37',
}
version=sys.argv[1]
expected=PINS[version]
output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=False)
url=f'https://github.com/pyodide/pyodide/releases/download/{version}/pyodide-core-{version}.tar.bz2'
archive=output/'runtime.tar.bz2'
with urllib.request.urlopen(url) as response,archive.open('xb') as target:
    while chunk:=response.read(1024*1024):target.write(chunk)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
with tarfile.open(archive) as bundle:bundle.extractall(output,filter='data')
print(version,expected,url)
