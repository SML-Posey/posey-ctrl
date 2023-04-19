import os
from glob import glob

from setuptools import setup, find_packages

from poseyctrl import VERSION


def read(filename):
    """Read in lines of files in path relative to this file."""
    return open(os.path.join(os.path.dirname(__file__), filename)).read()


pkg_files = []
for elem in glob('poseyctrl/resources/**/*', recursive=True):
    if os.path.isfile(elem):
        pkg_files.append(elem.replace('poseyctrl/', ''))
print(pkg_files)

setup(
    name='poseyctrl',
    version=VERSION,
    description='Bidirectional communication, data logging, and real-time plotting for Posey devices.',
    long_description=read('readme.md'),
    author='Anthony Wertz',
    author_email='awertz@cmu.edu',
    license='GPL3',
    packages=find_packages(),
    package_data={'poseyctrl': pkg_files},
    include_package_data=True,
    install_requires=[
        'multiprocess',
        'dill',
        'numpy',
        'pandas',
        'pySerial',
        'jsbeautifier',
        'asyncio',
    ],
    entry_points={
        'console_scripts': [
            'posey-decode-bin=poseyctrl.apps.posey_decode_bin:posey_decode_bin',
            'posey-listen=poseyctrl.apps.posey_listen:posey_listen',
            'posey-cmd=poseyctrl.apps.posey_cmd:posey_cmd',
            'posey-extract=poseyctrl.apps.posey_extract:posey_extract',
            'posey-sniffer=poseyctrl.apps.posey_sniffer:posey_sniffer',
        ]
    })
