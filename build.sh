set -e

rm -rf build dist *.egg-info
python setup.py sdist bdist_wheel
python -m twine check --strict dist/*
python -m twine upload dist/*
