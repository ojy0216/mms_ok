import re
from pathlib import Path

from setuptools import find_packages, setup


PROJECT_ROOT = Path(__file__).parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
PYPROJECT_TEXT = PYPROJECT_PATH.read_text(encoding="utf-8")


def _extract_toml_string(key: str) -> str:
    pattern = r'^{key}\s*=\s*"([^"]+)"'.format(key=re.escape(key))
    match = re.search(pattern, PYPROJECT_TEXT, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not find {key!r} in pyproject.toml")
    return match.group(1)


setup(
    name=_extract_toml_string("name"),
    version=_extract_toml_string("version"),
    description=_extract_toml_string("description"),
    long_description=(PROJECT_ROOT / _extract_toml_string("readme")).read_text(
        encoding="utf-8"
    ),
    long_description_content_type="text/markdown",
    author="Juyoung Oh",
    author_email="juyoung.oh@snu.ac.kr",
    url="https://github.com/ojy0216/mms_ok",
    python_requires=_extract_toml_string("requires-python"),
    packages=find_packages(exclude=("tests", "tests.*")),
    include_package_data=True,
    package_data={"mms_ok": ["bitstreams/*.bit"]},
)
