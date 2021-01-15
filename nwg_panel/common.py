#!/usr/bin/env python3

from i3ipc import Connection

i3 = Connection()
i3_tree = None

panels_list = []
config_dir = ""
config = None
tree = None
