#!/usr/bin/env bash

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit
fi

prefix=
opts=()

while true; do
  case "$1" in
    --prefix=*)
      opts+=("$1")
      prefix="${1#--prefix=}"  # no eval: the argument used to be executed as shell code
      prefix="${prefix/#\~/$HOME}"  # eval used to expand a leading ~
      shift
      ;;
    *)
      break
      ;;
  esac
done

opts+=("$@")

: ${prefix:="/usr"}

python3 setup.py install --optimize=1 "${opts[@]}"
mkdir -p "$prefix/share/pixmaps/" "$prefix/share/applications/"
cp nwg-panel.svg "$prefix/share/pixmaps/"
cp nwg-shell.svg "$prefix/share/pixmaps/"
cp nwg-processes.svg "$prefix/share/pixmaps/"
cp nwg-panel-config.desktop "$prefix/share/applications/"
cp nwg-processes.desktop "$prefix/share/applications/"

install -Dm 644 -t "/usr/share/licenses/nwg-panel" LICENSE
install -Dm 644 -t "/usr/share/doc/nwg-panel" README.md
