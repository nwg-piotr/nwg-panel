import os
import sys
import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from nwg_panel.tools import check_key, create_pixbuf
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
    factor = 1
    w, h = pixbuf.get_width(), pixbuf.get_height()
    if w != icon_size:
        factor = icon_size / w
    elif h != icon_size:
        factor = icon_size / h
    pixbuf = pixbuf.scale_simple(w * factor, h * factor, GdkPixbuf.InterpType.BILINEAR)

    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf,
                                                   image.get_scale_factor(),
                                                   image.get_window())
    image.set_from_surface(surface)


def load_icon(image, icon_name: str, icon_size, icon_path=""):
    icon_size *= image.get_scale_factor()
    pixbuf = create_pixbuf(icon_name, icon_size, icon_path)
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

    # ARGB -> RGBA
    rgba_data = []
    for i in range(0, len(largest_data), 4):
        rgba_data += largest_data[i + 1:i + 4] + [largest_data[i]]

    pixbuf = GdkPixbuf.Pixbuf.new_from_data(
        rgba_data,
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        largest_width,
        largest_height,
        4 * largest_width
    )
    icon_size *= image.get_scale_factor()
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

            if "IconName" in item.properties and len(item.properties['IconName']) > 0:
                update_icon(image, item, self.icon_size, self.icons_path)
            elif "IconPixmap" in item.properties and len(item.properties["IconPixmap"]) != 0:
                update_icon_from_pixmap(image, item, self.icon_size)

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

        if "IconThemePath" in changed_properties or ("IconName" in changed_properties and len(item.properties['IconName']) > 0):
            update_icon(image, item, self.icon_size, self.icons_path)
        elif "IconPixmap" in changed_properties and len(item.properties["IconPixmap"]) != 0:
            update_icon_from_pixmap(image, item, self.icon_size)
            pass

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
