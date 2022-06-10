#!/usr/bin/env python3

import json
import os
import stat
import threading
from datetime import datetime

import gi
import requests

from nwg_panel.common import config_dir
from nwg_panel.tools import check_key, eprint, load_json, save_json, temp_dir, file_age, hms, update_image

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


def on_button_press(window, event):
    if event.button == 1:
        window.close()


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
                    "interval": 600,
                    "icon-size": 24,
                    "icon-placement": "left",
                    "css-name": "clock",
                    "popup-css-name": "weather",
                    "on-right-click": "",
                    "on-middle-click": "",
                    "on-scroll": "",
                    "angle": 0.0,
                    "popup-icons": "light",
                    "forecast-icon-size": 18,
                    "forecast-text-size": "small"}
        for key in defaults:
            check_key(settings, key, defaults[key])

        self.set_property("name", settings["css-name"])

        self.settings = settings
        self.weather = {}
        self.forecast = {}

        self.icons_path = icons_path
        self.popup_icons = os.path.join(config_dir, "icons_light") if self.settings[
                                                                          "popup-icons"] == "light" else os.path.join(
            config_dir, "icons_dark")

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
        self.forecast_file = os.path.join(tmp_dir, "nwg-openweather-forecast")

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

        # print("Weather request:", self.weather_request)
        # print("Forecast request:", self.forecast_request)

        self.build_box()

        self.refresh()

        if settings["interval"] > 0:
            Gdk.threads_add_timeout_seconds(GLib.PRIORITY_DEFAULT, self.settings["interval"], self.refresh)

    def build_box(self):
        if self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 2)
        self.box.pack_start(self.label, False, False, 2)
        if self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 2)

    def get_data(self):
        self.get_weather()
        self.get_forecast()
        GLib.idle_add(self.update_widget)
        return True

    def refresh(self):
        thread = threading.Thread(target=self.get_data)
        thread.daemon = True
        thread.start()
        return True

    def on_button_press(self, widget, event):
        if event.button == 1:
            self.display_popup()
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
        weather = {}
        if not os.path.isfile(self.weather_file) or int(file_age(self.weather_file) > self.settings["interval"] - 1):
            eprint(hms(), "Requesting weather data")
            try:
                r = requests.get(self.weather_request)
                weather = json.loads(r.text)
                save_json(weather, self.weather_file)
            except Exception as e:
                eprint(e)
        else:
            eprint(hms(), "Loading weather data from file")
            weather = load_json(self.weather_file)

        self.weather = weather

    def get_forecast(self):
        # On widget click we'll load last saved json from file and open the popup window.
        forecast = {}
        if not os.path.isfile(self.forecast_file) or int(file_age(self.forecast_file) > self.settings["interval"] - 1):
            eprint(hms(), "Requesting forecast data")
            try:
                r = requests.get(self.forecast_request)
                forecast = json.loads(r.text)
                save_json(forecast, self.forecast_file)
            except Exception as e:
                eprint(e)
        else:
            eprint(hms(), "Loading forecast data from file")
            forecast = load_json(self.forecast_file)

        self.forecast = forecast

    def update_widget(self):
        if self.weather["cod"] in [200, "200"]:
            # eprint(hms(), "Parsing weather data")
            if "icon" in self.weather["weather"][0]:
                new_path = os.path.join(self.icons_path, "ow-{}.svg".format(self.weather["weather"][0]["icon"]))
                if self.icon_path != new_path:
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                            new_path, self.settings["icon-size"], self.settings["icon-size"])
                        self.image.set_from_pixbuf(pixbuf)
                        self.icon_path = new_path
                    except:
                        print("Failed setting image from {}".format(new_path))
            lbl_content = ""
            if "temp" in self.weather["main"] and self.weather["main"]["temp"]:
                deg = degrees[self.settings["units"]]
                try:
                    val = round(float(self.weather["main"]["temp"]), 1)
                    temp = "{}{}".format(str(val), deg)
                    lbl_content += temp
                except:
                    pass

            if "description" in self.weather["weather"][0]:
                desc = self.weather["weather"][0]["description"].capitalize()
                if self.settings["show-desc"]:
                    lbl_content += " {}".format(desc)

            self.label.set_text(lbl_content)

            mtime = datetime.fromtimestamp(os.stat(self.weather_file)[stat.ST_MTIME])
            self.set_tooltip_text("Update: {}".format(mtime.strftime("%d %b %H:%M:%S")))

        self.show_all()

    def svg2img(self, file_name):
        icon_path = os.path.join(self.popup_icons, file_name)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, self.settings["forecast-icon-size"],
                                                        self.settings["forecast-icon-size"])
        img = Gtk.Image.new_from_pixbuf(pixbuf)

        return img

    def display_popup(self):
        if self.popup.is_visible():
            self.popup.close()
            self.popup.destroy()

        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.popup.set_property("name", self.settings["popup-css-name"])

        GtkLayerShell.init_for_window(self.popup)
        GtkLayerShell.set_layer(self.popup, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.TOP, 1)
        GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.BOTTOM, 1)
        GtkLayerShell.set_anchor(self.popup, GtkLayerShell.Edge.RIGHT, 1)
        self.popup.connect('button-press-event', on_button_press)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        vbox.set_property("margin", 6)
        self.popup.add(vbox)

        # CURRENT WEATHER
        # row 0: Big icon
        if "icon" in self.weather["weather"][0]:
            icon_path = os.path.join(self.icons_path, "ow-{}.svg".format(self.weather["weather"][0]["icon"]))
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 48, 48)
            img = Gtk.Image.new_from_pixbuf(pixbuf)
            hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
            img.set_property("halign", Gtk.Align.END)
            hbox.pack_start(img, True, True, 0)

        if "description" in self.weather["weather"][0]:
            img.set_tooltip_text(self.weather["weather"][0]["description"])

        # row 0: Temperature big label
        if "temp" in self.weather["main"]:
            lbl = Gtk.Label()
            temp = self.weather["main"]["temp"]
            lbl.set_markup(
                '<span size="xx-large">{}{}</span>'.format(str(round(temp, 1)), degrees[self.settings["units"]]))
            lbl.set_property("halign", Gtk.Align.START)
            hbox.pack_start(lbl, True, True, 0)
            vbox.pack_start(hbox, False, False, 0)

        # row 1: Location
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        loc_label = self.weather["name"] if "name" in self.weather and not self.settings["loc-label"] else \
            self.settings[
                "loc-label"]
        country = ", {}".format(self.weather["sys"]["country"]) if "country" in self.weather["sys"] and \
                                                                   self.weather["sys"][
                                                                       "country"] else ""
        lbl = Gtk.Label()
        lbl.set_markup('<span size="x-large"><b>{}{}</b></span>'.format(loc_label, country))
        hbox.pack_start(lbl, True, True, 0)
        vbox.pack_start(hbox, False, False, 0)

        # row 2: Sunrise/sunset
        if self.weather["sys"]["sunrise"] and self.weather["sys"]["sunset"]:
            wbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
            vbox.pack_start(wbox, False, False, 0)
            hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
            wbox.pack_start(hbox, True, False, 0)
            img = Gtk.Image.new_from_icon_name("daytime-sunrise-symbolic", Gtk.IconSize.MENU)
            hbox.pack_start(img, False, False, 0)
            dt = datetime.fromtimestamp(self.weather["sys"]["sunrise"])
            lbl = Gtk.Label.new(dt.strftime("%H:%M"))
            hbox.pack_start(lbl, False, False, 0)
            img = Gtk.Image.new_from_icon_name("daytime-sunset-symbolic", Gtk.IconSize.MENU)
            hbox.pack_start(img, False, False, 0)
            dt = datetime.fromtimestamp(self.weather["sys"]["sunset"])
            lbl = Gtk.Label.new(dt.strftime("%H:%M"))
            hbox.pack_start(lbl, False, False, 0)

        # row 3: Weather details
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        lbl = Gtk.Label()
        lbl.set_property("justify", Gtk.Justification.CENTER)
        feels_like = "Feels like {}°".format(self.weather["main"]["feels_like"]) if "feels_like" in self.weather[
            "main"] else ""
        humidity = " Humidity {}%".format(self.weather["main"]["humidity"]) if "humidity" in self.weather[
            "main"] else ""
        wind_speed, wind_dir, wind_gust = "", "", ""
        if "wind" in self.weather:
            if "speed" in self.weather["wind"]:
                wind_speed = " Wind: {} m/s".format(self.weather["wind"]["speed"])
            if "deg" in self.weather["wind"]:
                wind_dir = " {}".format((direction(self.weather["wind"]["deg"])))
            if "gust" in self.weather["wind"]:
                wind_gust = " (gust {} m/s)".format((self.weather["wind"]["gust"]))
        pressure = " Pressure {} hPa".format(self.weather["main"]["pressure"]) if "pressure" in self.weather[
            "main"] else ""
        clouds = " Clouds {}%".format(self.weather["clouds"]["all"]) if "clouds" in self.weather and "all" in \
                                                                        self.weather[
                                                                            "clouds"] else ""
        visibility = " Visibility {} km".format(
            int(self.weather["visibility"] / 1000)) if "visibility" in self.weather else ""
        lbl.set_text(
            "{}{}{}{}{}\n{}{}{}".format(feels_like, humidity, wind_speed, wind_dir, wind_gust, pressure, clouds,
                                        visibility))
        hbox.pack_start(lbl, True, True, 0)
        vbox.pack_start(hbox, False, False, 6)

        # 5-DAY FORECAST
        if self.forecast["cod"] in [200, "200"]:
            # eprint(hms(), "Parsing forecast data")
            lbl = Gtk.Label()
            lbl.set_markup('<i>5-day forecast</i>')
            vbox.pack_start(lbl, False, False, 6)

            scrolled_window = Gtk.ScrolledWindow.new(None, None)
            scrolled_window.set_propagate_natural_width(True)
            scrolled_window.set_propagate_natural_height(True)

            grid = Gtk.Grid.new()
            grid.set_column_spacing(6)

            scrolled_window.add_with_viewport(grid)
            vbox.pack_start(scrolled_window, True, True, 0)

            for i in range(len(self.forecast["list"])):
                data = self.forecast["list"][i]

                img = self.svg2img("pan-end-symbolic.svg")
                grid.attach(img, 0, i, 1, 1)

                dt = datetime.fromtimestamp(data["dt"]).strftime("%a, %d %b %H:%M")
                box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                lbl = Gtk.Label()
                lbl.set_markup('<span font_size="{}">{}</span>'.format(self.settings["forecast-text-size"], dt))
                box.pack_start(lbl, False, False, 0)
                grid.attach(box, 1, i, 1, 1)

                if "weather" in data and data["weather"][0]:
                    if "icon" in data["weather"][0]:
                        img = self.svg2img("ow-{}.svg".format(data["weather"][0]["icon"]))
                        grid.attach(img, 2, i, 1, 1)

                    if "description" in data["weather"][0]:
                        img.set_tooltip_text(data["weather"][0]["description"])

                if "temp" in data["main"]:
                    lbl = Gtk.Label()
                    lbl.set_markup('<span font_size="{}">{}°</span>'.format(self.settings["forecast-text-size"],
                                                                            str(int(round(data["main"]["temp"], 0)))))
                    grid.attach(lbl, 3, i, 1, 1)

                if "pressure" in data["main"]:
                    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                    box.set_tooltip_text("Pressure")
                    img = self.svg2img("pressure.svg")
                    box.pack_start(img, False, False, 0)
                    lbl = Gtk.Label()
                    lbl.set_markup('<span font_size="{}">{} hPa</span>'.format(self.settings["forecast-text-size"],
                                                                               data["main"]["pressure"]))
                    box.pack_start(lbl, False, False, 0)
                    grid.attach(box, 4, i, 1, 1)

                if "wind" in data:
                    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
                    box.set_tooltip_text("Wind speed, (gusts), direction")
                    img = self.svg2img("wind.svg")
                    box.pack_start(img, False, False, 0)
                    wind_speed = "{} m/s".format(data["wind"]["speed"]) if "speed" in data["wind"] and data["wind"][
                        "speed"] else ""
                    wind_gust = " ({})".format(data["wind"]["gust"]) if "gust" in data["wind"] and data["wind"][
                        "gust"] else ""
                    wind_dir = " {}".format(direction(data["wind"]["deg"])) if "deg" in data["wind"] and data["wind"][
                        "deg"] else ""
                    lbl = Gtk.Label()
                    lbl.set_markup(
                        '<span font_size="{}">{}{}{}</span>'.format(self.settings["forecast-text-size"], wind_speed,
                                                                    wind_gust, wind_dir))
                    box.pack_start(lbl, False, False, 6)
                    grid.attach(box, 5, i, 1, 1)

                if "clouds" in data:
                    if "all" in data["clouds"]:
                        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
                        box.set_tooltip_text("Cloudiness")
                        img = self.svg2img("cloud.svg")
                        box.pack_start(img, False, False, 0)
                        lbl = Gtk.Label()
                        lbl.set_markup('<span font_size="{}">{}%</span>'.format(self.settings["forecast-text-size"],
                                                                                data["clouds"]["all"]))
                        box.pack_start(lbl, False, False, 0)
                        grid.attach(box, 6, i, 1, 1)

                if "visibility" in data:
                    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
                    box.set_tooltip_text("Visibility")
                    img = self.svg2img("eye.svg")
                    box.pack_start(img, False, False, 0)
                    lbl = Gtk.Label()
                    lbl.set_markup('<span font_size="{}">{} km</span>'.format(self.settings["forecast-text-size"],
                                                                              int(data["visibility"] / 1000)))
                    box.pack_start(lbl, False, False, 0)
                    grid.attach(box, 7, i, 1, 1)

                if "pop" in data and data["pop"]:
                    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
                    box.set_tooltip_text("Probability of precipitation")
                    img = self.svg2img("umbrella.svg")
                    box.pack_start(img, False, False, 0)
                    lbl = Gtk.Label()
                    lbl.set_markup('<span font_size="{}">{}%</span>'.format(self.settings["forecast-text-size"],
                                                                            int(round(data["pop"] * 100, 0))))
                    box.pack_start(lbl, False, False, 0)
                    grid.attach(box, 8, i, 1, 1)

            mtime = datetime.fromtimestamp(os.stat(self.forecast_file)[stat.ST_MTIME])
            lbl = Gtk.Label()
            lbl.set_markup(
                '<span font_size="{}">openweathermap.org, {}</span>'.format(self.settings["forecast-text-size"],
                                                                           mtime.strftime("%d %B %H:%M:%S")))
            vbox.pack_start(lbl, False, False, 6)

            """item = forecast["list"][0]
            print("---")
            for key in item:
                print(key, item[key])"""

        self.popup.show_all()
        self.popup.set_size_request(self.popup.get_allocated_width(), self.popup.get_allocated_width())
