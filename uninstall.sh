#!/usr/bin/env bash

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit
fi

# https://stackoverflow.com/questions/122327/how-do-i-find-the-location-of-my-python-site-packages-directory
SITE_PACKAGES=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
if [[ $SITE_PACKAGES != /usr/lib/* ]]; then
  echo "Error: Unexpected SITE_PACKAGES '$SITE_PACKAGES', expected a path starting with /usr/lib/"
  exit 1
fi

rm -r $SITE_PACKAGES/nwg_panel*
rm /usr/bin/nwg-panel
rm /usr/bin/nwg-panel-config
rm  /usr/share/pixmaps/nwg-panel.svg
rm  /usr/share/pixmaps/nwg-shell.svg
rm  /usr/share/applications/nwg-panel-config.desktop
