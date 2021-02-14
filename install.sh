#!/usr/bin/env bash

python setup.py install --optimize=1
cp nwg-panel.svg /usr/share/pixmaps/
cp nwg-panel-config.desktop /usr/share/applications/
