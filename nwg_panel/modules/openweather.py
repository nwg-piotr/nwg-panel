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

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, GtkLayerShell


def on_enter_notify_event(widget, event):
    widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
    widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)


def on_leave_notify_event(widget, event):
    widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
    widget.unset_state_flags(Gtk.StateFlags.SELECTED)


degrees = {"": "°K", "metric": "°C", "imperial": "°F"}


def direction(deg):
    if 0 <= deg <= 23 or 337 <= deg <= 360:
        return "N"
    elif 24 <= deg <= 68:
        return "NE"
    elif 69 <= deg <= 113:
        return "E"
    elif 114 <= deg <= 158:
        return "SE"
    elif 159 <= deg <= 203:
        return "S"
    elif 204 <= deg <= 248:
        return "SW"
    elif 249 <= deg <= 293:
        return "W"
    elif 293 <= deg <= 336:
        return "NW"
    else:
        return "?"


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()
    else:
        return True


class OpenWeather(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        Gtk.EventBox.__init__(self)
        defaults = {"lat": None,
                    "long": None,
                    "appid": "f060ab40f2b012e72350f6acc413132a",
                    "units": "metric",
                    "lang": "pl",
                    "num-timestamps": 8,
                    "show-desc": False,
                    "loc-label": "",
                    "interval": 10,
                    "icon-size": 24,
                    "icon-placement": "left",
                    "css-name": "clock",
                    "on-right-click": "",
                    "on-middle-click": "",
                    "on-scroll": "",
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

        self.connect('button-press-event', self.on_button_press)
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.connect('scroll-event', self.on_scroll)

        self.connect('enter-notify-event', on_enter_notify_event)
        self.connect('leave-notify-event', on_leave_notify_event)

        self.popup = Gtk.Window()

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

        self.forecast_request = "https://api.openweathermap.org/data/2.5/forecast?lat={}&lon={}&units={}&lang={}&cnt={}&appid={}".format(
            settings["lat"], settings["long"], settings["units"], settings["lang"], settings["num-timestamps"],
            settings["appid"])

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

    def on_button_press(self, widget, event):
        if event.button == 1:
            self.get_forecast()
        elif event.button == 2 and self.settings["on-middle-click"]:
            self.launch(self.settings["on-middle-click"])
        elif event.button == 3 and self.settings["on-right-click"]:
            self.launch(self.settings["on-right-click"])

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        elif event.direction == Gdk.ScrollDirection.DOWN and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        else:
            print("No command assigned")

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

        return weather

    def update_widget(self, weather):
        if weather["cod"] in [200, "200"]:
            """for key in weather:
                print(key, weather[key])"""
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
                deg = degrees[self.settings["units"]]
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
            loc_label = weather["name"] if not self.settings["loc-label"] else self.settings["loc-label"]
            self.set_tooltip_text("{}  {}  {}  ({})".format(loc_label, temp, desc, time.strftime("%H:%M")))

        self.show_all()

    def get_forecast(self):
        eprint("Requesting forecast data")
        try:
            r = requests.get(self.forecast_request)
            forecast = json.loads(r.text)
            GLib.idle_add(self.display_popup, forecast)
        except Exception as e:
            eprint(e)

    def display_popup(self, forecast):
        weather = self.get_weather()

        print("weather:", weather)
        if forecast["cod"] in [200, "200"]:
            if self.popup.is_visible():
                self.popup.close()
                self.popup.destroy()

            self.popup = Gtk.Window.new(Gtk.WindowType.POPUP)

            GtkLayerShell.init_for_window(self.popup)
            GtkLayerShell.set_keyboard_interactivity(self.popup, True)
            self.popup.connect("key-release-event", handle_keyboard)

            vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
            vbox.set_property("margin", 12)
            self.popup.add(vbox)

            try:
                icon_path = os.path.join(self.icons_path, "ow-{}.svg".format(weather["weather"][0]["icon"]))
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 48, 48)
                hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
                img = Gtk.Image.new_from_pixbuf(pixbuf)
                img.set_property("halign", Gtk.Align.END)
                hbox.pack_start(img, True, True, 0)
                lbl = Gtk.Label()
                temp = weather["main"]["temp"]
                lbl.set_markup(
                    '<span size="xx-large">{}{}</span>'.format(str(round(temp, 1)), degrees[self.settings["units"]]))
                lbl.set_property("halign", Gtk.Align.START)
                hbox.pack_start(lbl, True, True, 0)
                vbox.pack_start(hbox, False, False, 0)
            except Exception as e:
                eprint(e)

            try:
                hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                loc_label = weather["name"] if not self.settings["loc-label"] else self.settings["loc-label"]
                lbl = Gtk.Label()
                lbl.set_text("{}, {}".format(loc_label, weather["sys"]["country"]))
                hbox.pack_start(lbl, True, True, 0)
                vbox.pack_start(hbox, False, False, 0)
            except Exception as e:
                eprint(e)

            try:
                hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                lbl = Gtk.Label()
                lbl.set_text(
                    "Feels like {}°, hum {}%, {} hPa".format(weather["main"]["feels_like"],
                                                             weather["main"]["humidity"],
                                                             weather["main"]["pressure"]))
                hbox.pack_start(lbl, True, True, 0)
                vbox.pack_start(hbox, False, False, 6)
            except Exception as e:
                eprint(e)

            for key in forecast:
                print(key, forecast[key])
            item = forecast["list"][0]
            print("---")
            for key in item:
                print(key, item[key])

            self.popup.show_all()
