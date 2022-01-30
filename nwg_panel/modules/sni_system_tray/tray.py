import os
import sys
import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, GdkPixbuf

from nwg_panel.tools import check_key, get_config_dir
from .item import StatusNotifierItem
from .menu import Menu


def load_icon(image, icon_name: str, icon_size, icons_path=""):
    icon_theme = Gtk.IconTheme.get_default()
    search_path = icon_theme.get_search_path()
    try:
        if icons_path:
            search_path.append(icons_path)
            icon_theme.set_search_path(search_path)

        if icon_theme.has_icon(icon_name):
            pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
        elif icon_theme.has_icon(icon_name.lower()):
            pixbuf = icon_theme.load_icon(icon_name.lower(), icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
        elif icon_name.startswith("/"):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_name, icon_size, icon_size)
        else:
            pixbuf = icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)

    except GLib.GError:
        print(
            "tray -> update_icon: icon not found\n  icon_name: {}\n  search_path: {}".format(
                icon_name,
                search_path
            ),
            file=sys.stderr
        )
        path = os.path.join(get_config_dir(), "icons_light/icon-missing.svg")
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, icon_size, icon_size)

    # TODO: if image height is different to icon_size, resize to match, while maintaining
    #  aspect ratio. Width can be ignored.

    image.set_from_pixbuf(pixbuf)


def update_icon(image, item, icon_size, icon_path):
    if "IconThemePath" in item.properties:
        icon_path = item.properties["IconThemePath"]
    load_icon(image, item.properties["IconName"], icon_size, icon_path)


def update_status(event_box, item):
    if "Status" in item.properties:
        status = item.properties["Status"].lower()
        event_box.set_visible(status != "passive")
        event_box_style = event_box.get_style_context()
        for class_name in event_box_style.list_classes():
            event_box_style.remove_class(class_name)
        if status == "needsattention":
            event_box_style.add_class("needs-attention")
        event_box_style.add_class(status)


class Tray(Gtk.EventBox):
    def __init__(self, settings, icons_path=""):
        self.menu = None
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)

        check_key(settings, "icon-size", 16)
        check_key(settings, "root-css-name", "tray")

        self.set_property("name", settings["root-css-name"])

        self.icon_size = settings["icon-size"]

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)

        self.items = {}

    def add_item(self, item: StatusNotifierItem):
        print("Tray -> add_item: {}".format(item.properties))
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        if full_service_name not in self.items:
            event_box = Gtk.EventBox()
            image = Gtk.Image()

            if "IconPixmap" in item.properties:
                # TODO: handle loading pixbuf from dbus
                pass
            else:
                update_icon(image, item, self.icon_size, self.icons_path)

            if "Tooltip" in item.properties:
                # TODO: handle tooltip variant type
                pass

            if "Title" in item.properties:
                image.set_tooltip_markup(item.properties["Title"])

            update_status(event_box, item)

            event_box.add(image)
            self.box.pack_start(event_box, False, False, 6)
            self.box.show_all()

            if "Menu" in item.properties:
                self.menu = Menu(
                    service_name=item.service_name,
                    object_path=item.properties["Menu"],
                    parent_widget=event_box
                )

            self.items[full_service_name] = {
                "event_box": event_box,
                "image": image,
                "item": item
            }

    def update_item(self, item: StatusNotifierItem, changed_properties: list[str]):
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        event_box = self.items[full_service_name]["event_box"]
        image = self.items[full_service_name]["image"]

        if "IconPixmap" in changed_properties:
            # TODO: handle loading pixbuf from dbus
            pass
        elif "IconThemePath" in changed_properties or "IconName" in changed_properties:
            update_icon(image, item, self.icon_size, self.icons_path)

        if "Tooltip" in changed_properties:
            # handle tooltip variant type
            pass

        if "Title" in changed_properties:
            image.set_tooltip_markup(item.properties["Title"])

        update_status(event_box, item)

        event_box.show_all()

    def remove_item(self, item: StatusNotifierItem):
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        self.box.remove(self.items[full_service_name]["event_box"])
        self.items.pop(full_service_name)
        self.box.show_all()
