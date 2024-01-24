rm -fr dist
.venv/bin/python3 -m build && .venv/bin/python3 -m pip install dist/*.whl --force-reinstall
