import os
import sys
import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, GdkPixbuf

from nwg_panel.tools import check_key, get_config_dir
from .item import StatusNotifierItem
from .menu import Menu


def resize_pix_buf(image, pixbuf, icon_size):
    # [At least on non-HiDPI system], this value is always in 1 or 2 (output scaled down or not scaled at all
    # / output scaled up), globally, whether one or more displays are scaled - so it seems useless.
    # E.g. if we scale one output * 1.2, we have icons resized * 2 on all outputs. Let's turn it off.
    """
    scaled_icon_size = image.get_scale_factor() * icon_size
    if pixbuf.get_height() != scaled_icon_size:
        width = scaled_icon_size * pixbuf.get_width() / pixbuf.get_height()
        pixbuf = pixbuf.scale_simple(width, scaled_icon_size, GdkPixbuf.InterpType.BILINEAR)
    """
    image.set_from_pixbuf(pixbuf)


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
        """print(
            "tray -> update_icon: icon not found\n  icon_name: {}\n  search_path: {}".format(
                icon_name,
                search_path
            ),
            file=sys.stderr
        )"""
        path = os.path.join(get_config_dir(), "icons_light/icon-missing.svg")
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, icon_size, icon_size)

    resize_pix_buf(image, pixbuf, icon_size)


def update_icon(image, item, icon_size, icon_path):
    if "IconThemePath" in item.properties:
        icon_path = item.properties["IconThemePath"]
    load_icon(image, item.properties["IconName"], icon_size, icon_path)


def update_icon_from_pixmap(image, item, icon_size):
    largest_data = []
    largest_width = 0
    largest_height = 0
    for width, height, data in item.properties["IconPixmap"]:
        if width * height > largest_width * largest_height:
            largest_data = data
            largest_width = width
            largest_height = height
    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes().new(largest_data),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        largest_width,
        largest_height,
        4 * largest_width
    )
    resize_pix_buf(image, pixbuf, icon_size)


def update_tooltip(image, item):
    icon_name, icon_data, title, description = item.properties["Tooltip"]
    tooltip = title
    if description:
        tooltip = "<b>{}</b>\n{}".format(title, description)
    image.set_tooltip_markup(tooltip)


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
    def __init__(self, settings, panel_position, icons_path=""):
        self.menu = None
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)

        check_key(settings, "icon-size", 16)
        check_key(settings, "root-css-name", "tray")
        check_key(settings, "inner-css-name", "inner-tray")
        check_key(settings, "smooth-scrolling-threshold", 0)

        self.set_property("name", settings["root-css-name"])

        self.icon_size = settings["icon-size"]

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        if panel_position in ["left", "right"]:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.box.set_property("name", settings["inner-css-name"])
        self.add(self.box)

        self.items = {}

    def add_item(self, item: StatusNotifierItem):
        # print("Tray -> add_item: {}".format(item.properties))
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        if full_service_name not in self.items:
            event_box = Gtk.EventBox()
            image = Gtk.Image()

            if "IconPixmap" in item.properties:
                update_icon_from_pixmap(image, item, self.icon_size)
            elif "IconName" in item.properties:
                update_icon(image, item, self.icon_size, self.icons_path)

            if "Tooltip" in item.properties:
                update_tooltip(image, item)
            elif "Title" in item.properties:
                image.set_tooltip_markup(item.properties["Title"])

            update_status(event_box, item)

            event_box.add(image)
            self.box.pack_start(event_box, False, False, 6)
            self.box.show_all()

            if "Menu" in item.properties:
                self.menu = Menu(
                    service_name=item.service_name,
                    object_path=item.properties["Menu"],
                    settings=self.settings,
                    event_box=event_box,
                    item=item
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
            update_icon_from_pixmap(image, item, self.icon_size)
            pass
        elif "IconThemePath" in changed_properties or "IconName" in changed_properties:
            update_icon(image, item, self.icon_size, self.icons_path)

        if "Tooltip" in changed_properties:
            update_tooltip(image, item)
        elif "Title" in changed_properties:
            image.set_tooltip_markup(item.properties["Title"])

        update_status(event_box, item)

        event_box.show_all()

    def remove_item(self, item: StatusNotifierItem):
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        self.box.remove(self.items[full_service_name]["event_box"])
        self.items.pop(full_service_name)
        self.box.show_all()
