from setuptools import find_packages, setup

setup(
    name="mms_ok",
    version="1.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "bitslice",
        "loguru",
        "rich",
        "tqdm"
    ],
    author_email="juyoung.oh@snu.ac.kr",
    description="Python package for interfacing with Opal Kelly FPGA boards",
    classifiers=[
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering",
    ],
    python_requires=">=3.7",
)
