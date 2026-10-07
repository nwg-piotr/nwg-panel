import os
import sys
import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

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
    w, h = pixbuf.get_width(), pixbuf.get_height()
    # fit the longer side: scaled on its width, a tall image was higher than the bar and a very wide one 0 px
    factor = icon_size / max(w, h)
    pixbuf = pixbuf.scale_simple(max(1, round(w * factor)), max(1, round(h * factor)), GdkPixbuf.InterpType.BILINEAR)

    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf,
                                                   image.get_scale_factor(),
                                                   image.get_window())
    image.set_from_surface(surface)


def load_icon(image, icon_name: str, icon_size, icon_path=""):
    icon_size *= image.get_scale_factor()
    pixbuf = create_pixbuf(icon_name, icon_size, icon_path)
    resize_pix_buf(image, pixbuf, icon_size)


def load_item_theme_icon(item, icon_name, icon_size):
    """Look the icon up in the item's own IconThemePath, without touching the global icon theme.

    Electron & libappindicator apps give a different temporary IconThemePath on each launch
    (e.g. /tmp/.org.chromium.Chromium.XXXXXX): adding it to Gtk.IconTheme.get_default() made
    the search path grow forever, and every addition rescanned the theme and emptied the
    panel's icon cache."""
    path = item.properties.get("IconThemePath")
    if not path or not os.path.isdir(path):
        return None
    for ext in ("png", "svg", "xpm"):
        file = os.path.join(path, "{}.{}".format(icon_name, ext))
        if os.path.isfile(file):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_size(file, icon_size, icon_size)
            except GLib.Error:
                pass
    if item.icon_theme is None or item.icon_theme_path != path:
        item.icon_theme = Gtk.IconTheme.new()
        item.icon_theme.set_search_path([path])
        item.icon_theme_path = path
    try:
        return item.icon_theme.load_icon(icon_name, icon_size, Gtk.IconLookupFlags.FORCE_SIZE)
    except GLib.Error:
        return None


def update_icon(image, item, icon_size, icon_path):
    icon_size *= image.get_scale_factor()
    icon_name = item.properties["IconName"]
    pixbuf = None if icon_name.startswith("/") else load_item_theme_icon(item, icon_name, icon_size)
    if pixbuf is None:
        # as before: the panel's own icons are for items that give no IconThemePath, not even an empty one
        if "IconThemePath" in item.properties:
            icon_path = ""
        pixbuf = create_pixbuf(icon_name, icon_size, icon_path)
    resize_pix_buf(image, pixbuf, icon_size)


def pixmap_to_pixbuf(pixmaps, icon_size):
    """IconPixmap (ARGB32, network byte order) -> pixbuf, from the smallest image not smaller
    than icon_size (the largest one, often 256x256 or more, was converted pixel by pixel)."""
    if not pixmaps:
        return None
    # sizes and length of the data were checked when the property was read (item.unpack_pixmaps)
    big_enough = [c for c in pixmaps if min(c[0], c[1]) >= icon_size]
    width, height, data = min(big_enough, key=lambda c: c[0] * c[1]) if big_enough \
        else max(pixmaps, key=lambda c: c[0] * c[1])
    argb = bytes(data[:width * height * 4])
    rgba = bytearray(len(argb))
    rgba[0::4] = argb[1::4]
    rgba[1::4] = argb[2::4]
    rgba[2::4] = argb[3::4]
    rgba[3::4] = argb[0::4]
    return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(rgba)), GdkPixbuf.Colorspace.RGB,
                                           True, 8, width, height, 4 * width)


def update_icon_from_pixmap(image, item, icon_size):
    icon_size *= image.get_scale_factor()
    pixmaps = item.properties["IconPixmap"]
    # decoded once per pixmap and size, shared by the trays of all outputs (the cache holds the list
    # itself, not its id(): the address of a freed list can be given to the next one)
    cache = item.pixmap_cache
    if cache is None or cache[0] is not pixmaps or cache[1] != icon_size:
        cache = item.pixmap_cache = (pixmaps, icon_size, pixmap_to_pixbuf(pixmaps, icon_size))
    pixbuf = cache[2]
    if pixbuf is not None:
        resize_pix_buf(image, pixbuf, icon_size)


def markup_or_escaped(text):
    """SNI descriptions may contain markup; anything that does not parse is shown as plain text."""
    try:
        Pango.parse_markup(text, -1, "\0")
        return text
    except GLib.Error:
        return GLib.markup_escape_text(text)


def update_tooltip(image, item):
    value = item.properties["ToolTip"] if "ToolTip" in item.properties else item.properties.get("Tooltip")
    if not value or len(value) < 4:
        return
    icon_name, icon_data, title, description = value
    tooltip = GLib.markup_escape_text(title or "")
    if description:
        tooltip = "<b>{}</b>\n{}".format(tooltip, markup_or_escaped(description))
    image.set_tooltip_markup(tooltip)
    image.set_has_tooltip(True)


def update_status(event_box, item):
    """Call after show_all(): a Passive item must stay hidden."""
    if "Status" in item.properties:
        status = item.properties["Status"].lower()
        event_box.set_visible(status != "passive")
        event_box_style = event_box.get_style_context()
        for class_name in event_box_style.list_classes():
            event_box_style.remove_class(class_name)
        if status == "needsattention":
            event_box_style.add_class("needs-attention")
        event_box_style.add_class(status)


SNI_CATEGORIES = ["ApplicationStatus", "Communications", "SystemServices", "Hardware"]


def category_rank(item):
    category = item.properties.get("Category", "ApplicationStatus")
    return SNI_CATEGORIES.index(category) if category in SNI_CATEGORIES else 0


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
        check_key(settings, "new-left", False)
        check_key(settings, "sort-by-category", False)

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

            if "Tooltip" in item.properties or "ToolTip" in item.properties:
                update_tooltip(image, item)
            elif "Title" in item.properties:
                image.set_tooltip_markup(GLib.markup_escape_text(item.properties["Title"]))
            image.tooltip_version = item.tooltip_fetched_version

            # tooltip changes are fetched lazily, when the tooltip is about to be shown
            image.set_has_tooltip(True)
            image.connect("query-tooltip", self.on_query_tooltip, item)

            event_box.add(image)
            if self.settings["sort-by-category"]:
                # Applications first, then communications, system services and hardware
                # (network, volume, bluetooth...), each group in order of appearance.
                event_box.category_rank = category_rank(item)
                self.box.pack_start(event_box, False, False, 6)
                position = sum(1 for child in self.box.get_children()
                               if child is not event_box and getattr(child, "category_rank", 0) <= event_box.category_rank)
                self.box.reorder_child(event_box, position)
            elif not self.settings["new-left"]:
                self.box.pack_start(event_box, False, False, 6)
            else:
                self.box.pack_end(event_box, False, False, 6)
            event_box.show_all()
            update_status(event_box, item)
            self.box.show()

            # Clicks and scrolling are handled even without a dbusmenu ("Menu" is optional):
            # Activate / SecondaryActivate / ContextMenu / Scroll are then sent to the item.
            menu = Menu(
                service_name=item.service_name,
                object_path=item.properties.get("Menu"),
                settings=self.settings,
                event_box=event_box,
                item=item
            )

            self.items[full_service_name] = {
                "event_box": event_box,
                "image": image,
                "item": item,
                "menu": menu
            }

    def update_item(self, item: StatusNotifierItem, changed_properties: list[str]):
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        if full_service_name not in self.items:
            return  # not loaded (yet) in this tray
        event_box = self.items[full_service_name]["event_box"]
        image = self.items[full_service_name]["image"]

        def has(prop):
            return prop in item.properties and len(item.properties[prop]) > 0

        icon_changed = any(p in changed_properties for p in ("IconThemePath", "IconName", "IconPixmap"))
        if icon_changed:
            if has("IconName"):
                update_icon(image, item, self.icon_size, self.icons_path)
            elif has("IconPixmap"):
                update_icon_from_pixmap(image, item, self.icon_size)

        if "Tooltip" in changed_properties or "ToolTip" in changed_properties:
            update_tooltip(image, item)
            image.tooltip_version = item.tooltip_fetched_version
        elif "Title" in changed_properties and "Title" in item.properties:
            image.set_tooltip_markup(GLib.markup_escape_text(item.properties["Title"]))
            image.set_has_tooltip(True)

        event_box.show_all()
        update_status(event_box, item)

    @staticmethod
    def on_query_tooltip(image, _x, _y, _keyboard_mode, _tooltip, item):
        if item.tooltip_stale:
            # read it in the background, then let GTK query the tooltip again
            def on_fetched():
                if image.get_parent() is not None:
                    update_tooltip(image, item)
                    image.tooltip_version = item.tooltip_fetched_version
                    image.trigger_tooltip_query()
            item.fetch_tooltip(image, on_fetched)
        elif getattr(image, "tooltip_version", -1) != item.tooltip_fetched_version:
            # fetched for the tray of another output
            update_tooltip(image, item)
            image.tooltip_version = item.tooltip_fetched_version
        return False  # let GTK show the current tooltip markup

    def remove_item(self, item: StatusNotifierItem):
        full_service_name = "{}{}".format(item.service_name, item.object_path)
        entry = self.items.pop(full_service_name, None)
        if entry is None:
            return  # unregistered before it was loaded
        entry["menu"].destroy()
        entry["event_box"].destroy()
