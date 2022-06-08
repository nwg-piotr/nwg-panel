#!/usr/bin/env python3

import json
import os
import stat
import threading

import gi
import requests

from nwg_panel.tools import check_key, eprint, load_json, save_json, temp_dir, file_age, update_image
from datetime import datetime

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib


class OpenWeather(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        Gtk.EventBox.__init__(self)
        defaults = {"lat": None,
                    "long": None,
                    "appid": "f060ab40f2b012e72350f6acc413132a",
                    "units": "metric",
                    "lang": "pl",
                    "show-desc": False,
                    "interval": 10,
                    "icon-size": 24,
                    "icon-placement": "left",
                    "css-name": "clock",
                    "angle": 0.0}
        for key in defaults:
            check_key(settings, key, defaults[key])

        self.set_property("name", settings["css-name"])

        self.settings = settings
        self.icons_path = icons_path

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label.new("")
        self.icon_path = None

        self.weather = None
        self.forecast = None

        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
            self.label.set_angle(settings["angle"])

        update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], self.icons_path)

        data_home = os.getenv('XDG_DATA_HOME') if os.getenv('XDG_DATA_HOME') else os.path.join(os.getenv("HOME"),
                                                                                               ".local/share")
        tmp_dir = temp_dir()
        self.weather_file = os.path.join(tmp_dir, "nwg-openweather-weather")

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
        # print("Forecast request:", self.forecast_request)

        self.build_box()
        self.refresh()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_LOW, 180, self.refresh)

    def build_box(self):
        if self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 2)
        self.box.pack_start(self.label, False, False, 2)
        if self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 2)

    def refresh(self):
        thread = threading.Thread(target=self.get_weather)
        thread.daemon = True
        thread.start()
        return True

    def get_weather(self):
        # On sway reload we'll load last saved json from file (instead of requesting data),
        # if the file exists and refresh interval has not yet elapsed.
        if not os.path.isfile(self.weather_file) or int(file_age(self.weather_file)) > self.settings[
                "interval"] * 60 - 1:
            eprint("Requesting weather data")
            try:
                r = requests.get(self.weather_request)
                weather = json.loads(r.text)
                save_json(weather, self.weather_file)
                GLib.idle_add(self.update_widget, weather)
            except Exception as e:
                eprint(e)
        else:
            weather = load_json(self.weather_file)
            GLib.idle_add(self.update_widget, weather)

    def update_widget(self, weather):
        if weather["cod"] in [200, "200"]:
            for key in weather:
                print(key, weather[key])
            new_path = os.path.join(self.icons_path, "ow-{}.svg".format(weather["weather"][0]["icon"]))
            if self.icon_path != new_path:
                print("Setting image from {}".format(new_path))
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        new_path, self.settings["icon-size"], self.settings["icon-size"])
                    self.image.set_from_pixbuf(pixbuf)
                    self.icon_path = new_path
                except:
                    print("Failed setting image from {}".format(new_path))
            lbl_content = ""
            temp = ""
            if weather["main"]["temp"]:
                if self.settings["units"] == "metric":
                    deg = "°C"
                elif self.settings["units"] == "imperial":
                    deg = "°F"
                else:
                    deg = "°K"
                try:
                    val = round(float(weather["main"]["temp"]), 1)
                    temp = "{}{}".format(str(val), deg)
                    lbl_content += temp
                except:
                    pass

            desc = weather["weather"][0]["description"].capitalize()
            if self.settings["show-desc"]:
                lbl_content += " {}".format(desc)

            self.label.set_text(lbl_content)

            time = datetime.fromtimestamp(os.stat(self.weather_file)[stat.ST_MTIME])
            self.set_tooltip_text("{}  {}  {}  ({})".format(weather["name"], temp, desc, time.strftime("%H:%M")))

        self.show_all()
