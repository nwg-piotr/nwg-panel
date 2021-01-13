#!/usr/bin/env python3

from gi.repository import Gtk


class Panel(Gtk.Window):
    def __init__(self, padding_h=0, padding_v=0, icon=None):
        super(Panel, self).__init__()
