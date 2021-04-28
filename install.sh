#!/usr/bin/env bash

python3 setup.py install --optimize=1
cp nwg-panel.svg /usr/share/pixmaps/
cp nwg-shell.svg /usr/share/pixmaps/
cp nwg-panel-config.desktop /usr/share/applications/
