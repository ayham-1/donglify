#!/bin/bash

rm -fr dist
python3 -m build && python3 -m pip install dist/*.whl --force-reinstall
