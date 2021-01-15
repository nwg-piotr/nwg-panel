#!/usr/bin/env python3

from i3ipc import Connection

i3 = Connection()
i3_tree = None
old_ipc_data = {}
test_widget = None
config_dir = ""
config = None
tree = None
