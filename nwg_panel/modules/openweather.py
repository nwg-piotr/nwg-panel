#!/usr/bin/env python3

import json
import os

import gi
import requests
import threading

from nwg_panel.tools import check_key, eprint, load_json

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GLib


class OpenWeather(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        Gtk.EventBox.__init__(self)
        defaults = {"lat": None,
                    "long": None,
                    "appid": "f060ab40f2b012e72350f6acc413132a",
                    "units": "metric",
                    "lang": "",
                    "interval": 1800}
        for key in defaults:
            check_key(settings, key, defaults[key])

        self.settings = settings
        self.icons_path = icons_path

        self.weather = None
        self.forecast = None

        data_home = os.getenv('XDG_DATA_HOME') if os.getenv('XDG_DATA_HOME') else os.path.join(os.getenv("HOME"),
                                                                                               ".local/share")
        # Try to obtain geolocation if unset
        if not settings["lat"] or not settings["long"]:
            # Try nwg-shell settings
            shell_settings_file = os.path.join(data_home, "nwg-shell-config", "settings")
            if os.path.isfile(shell_settings_file):
                shell_settings = load_json(shell_settings_file)
                eprint("OpenWeather: coordinates not set, loading from nwg-shell settings")
                settings["lat"] = shell_settings["night-lat"]
                settings["long"] = shell_settings["night-long"]
                eprint("lat = {}, long = {}".format(settings["lat"], settings["long"]))
            else:
                # Set dummy location
                eprint("OpenWeather: coordinates not set, setting Big Ben in London 51.5008, -0.1246")
                self.lat = 51.5008
                self.long = -0.1246

        self.weather_request = "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&units={}&lang={}&appid={}".format(
            settings["lat"], settings["long"], settings["units"], settings["lang"], settings["appid"])

        self.forecast_request = "https://api.openweathermap.org/data/2.5/forecast?lat={}&lon={}&units={}&lang={}&appid={}".format(
            settings["lat"], settings["long"], settings["units"], settings["lang"], settings["appid"])

        print("Weather request:", self.weather_request)
        print("Forecast request:", self.forecast_request)

        self.refresh()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, settings["interval"], self.refresh)

    def get_weather(self):
        try:
            r = requests.get(self.forecast_request)
            weather = json.loads(r.text)
            GLib.idle_add(self.update_widget, weather)
        except Exception as e:
            print(e)

    def refresh(self):
        thread = threading.Thread(target=self.get_weather)
        thread.daemon = True
        thread.start()
        return True

    def update_widget(self, weather):
        if weather["cod"] == "200":
            for key in weather:
                print(key, weather[key])
