#!/usr/bin/env python3

from gi.repository import Gtk

import sys
sys.path.append('../')

import subprocess

import nwg_panel.common
from nwg_panel.tools import check_key


class Executor(Gtk.EventBox):
    def __init__(self, settings):
        self.settings = settings
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        
        self.build_box()
    
    def build_box(self):
        pass
        # print(self.script_output())
    
    def script_output(self):
        if "script" not in self.settings:
            return None, None
        else:
            output = subprocess.check_output(self.settings["script"], shell=True).decode("utf-8").strip().splitlines()
            if len(output) > 1:
                return output[0], output[1]
            else:
                return None, output[0]
