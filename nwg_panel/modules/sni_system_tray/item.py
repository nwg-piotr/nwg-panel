from gi.repository import Gdk, Gio, GLib

from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver

from nwg_panel.tools import eprint

# Properties read from an item, with their D-Bus types ("|": either of them). Every item is another
# application's object: a value of any other type is dropped where it arrives, so that the tray can
# rely on these.
PROPERTIES = {
    "Id": "s",
    "Category": "s",
    "Title": "s",
    "Status": "s",
    "WindowId": "i|u",  # int32 in KDE's interface, uint32 in the freedesktop.org specification
    "IconName": "s",
    "IconPixmap": "a(iiay)",
    "OverlayIconName": "s",
    "OverlayIconPixmap": "a(iiay)",
    "AttentionIconName": "s",
    "AttentionIconPixmap": "a(iiay)",
    "AttentionMovieName": "s",
    "ToolTip": "(sa(iiay)ss)",
    "IconThemePath": "s",
    "ItemIsMenu": "b",
    "Menu": "o"
}

SNI_INTERFACES = ["org.kde.StatusNotifierItem", "org.freedesktop.StatusNotifierItem"]

# Every call to an item is asynchronous: an application that registered a tray icon and is busy (or
# frozen) does not block the panel, so nothing is gained by giving up early. -1: GDBus default, 25 s.
DBUS_TIMEOUT_MS = -1

# A read that got no answer says nothing about the item: what is known of it is kept, and the read is
# done again, a few times on a timer, then whenever the item emits a signal, and once a minute for an
# item that does not (it is still registered: it may have been busy for longer, and answer by now).
RETRY_DELAY_MS = 2000
MAX_RETRIES = 3
SLOW_RETRY_DELAY_S = 60
NO_ANSWER = object()

# Errors that are no answer from the item: its application is busy, frozen or gone, or the bus could
# not carry the call. Any other error reply comes from the application and means "no such interface /
# property here". There is no single name for that: InvalidArgs (GDBus), UnknownInterface /
# UnknownProperty (Qt, sd-bus), Failed (Chromium / Electron),
# org.freedesktop.DBus.Properties.Error.PropertyNotFound (Go's godbus)...
NO_ANSWER_ERRORS = (
    "org.freedesktop.DBus.Error.NoReply",
    "org.freedesktop.DBus.Error.Timeout",
    "org.freedesktop.DBus.Error.TimedOut",
    "org.freedesktop.DBus.Error.ServiceUnknown",
    "org.freedesktop.DBus.Error.NameHasNoOwner",
    "org.freedesktop.DBus.Error.Disconnected",
    "org.freedesktop.DBus.Error.LimitsExceeded",
    "org.freedesktop.DBus.Error.NoMemory",
)

# NewIcon & co. can come in bursts (animated icons): properties are re-read once per burst.
REFRESH_DELAY_MS = 50

# Pixmaps with a longer side are ignored: a peer could send images up to the D-Bus message limit
# (128 MiB), which we copy to convert ARGB -> RGBA. Tray icons are 16-256 px, this leaves a wide margin.
# Nor is more than the beginning of a list looked at: 100 000 images of 1x1 take a second to walk, and
# as many properties half a second (the interface has 16, some implementations a few more).
MAX_PIXMAP_SIDE = 1024
MAX_PIXMAPS = 32
MAX_PROPERTIES = 64

# Signals that only say "something changed": the new value has to be read.
SIGNAL_PROPERTIES = {
    "NewTitle": ["Title"],
    "NewIcon": ["IconName", "IconPixmap", "IconThemePath"],
    "NewAttentionIcon": ["AttentionIconName", "AttentionIconPixmap"],
    "NewOverlayIcon": ["OverlayIconName", "OverlayIconPixmap"],
}


def is_answer(error):
    return Gio.DBusError.is_remote_error(error) and Gio.DBusError.get_remote_error(error) not in NO_ANSWER_ERRORS


def unpack_pixmaps(variant):
    """a(iiay) -> [(width, height, bytes)]. Variant.unpack() would make one Python int per byte, which
    froze the panel for half a second per 256x256 image: the sizes are read first, and the data is
    taken as bytes, only if they are sensible and it is as long as they say."""
    pixmaps = []
    for i in range(min(variant.n_children(), MAX_PIXMAPS)):
        pixmap = variant.get_child_value(i)
        width, height = pixmap.get_child_value(0).get_int32(), pixmap.get_child_value(1).get_int32()
        data = pixmap.get_child_value(2)
        size = width * height * 4
        if 0 < width <= MAX_PIXMAP_SIDE and 0 < height <= MAX_PIXMAP_SIDE and data.n_children() >= size:
            # the image and no more: the array can be far longer than the sizes say
            pixmaps.append((width, height, data.get_data_as_bytes().new_from_bytes(0, size).get_data()))
    return pixmaps


def unpack_property(name, variant):
    """Value of a property read from an item, None if it is not of the expected type."""
    signature = variant.get_type_string()
    if signature not in PROPERTIES[name].split("|"):
        return None
    if signature == "a(iiay)":
        return unpack_pixmaps(variant)
    if name == "ToolTip":
        # (icon name, icon pixmaps, title, description)
        return (variant.get_child_value(0).get_string(), unpack_pixmaps(variant.get_child_value(1)),
                variant.get_child_value(2).get_string(), variant.get_child_value(3).get_string())
    return variant.unpack()


def unpack_properties(variant):
    """a{sv} -> {name: value}, without the properties we don't read or can't use."""
    properties = {}
    for i in range(min(variant.n_children(), MAX_PROPERTIES)):
        entry = variant.get_child_value(i)
        name = entry.get_child_value(0).get_string()
        if name in PROPERTIES:
            value = unpack_property(name, entry.get_child_value(1).get_variant())
            if value is not None:
                properties[name] = value
    return properties


class StatusNotifierItem(object):
    def __init__(self, service_name, object_path):
        self.service_name = service_name
        self.object_path = object_path
        self.on_loaded_callback = None
        self.on_updated_callback = None
        self.connection = SessionMessageBus().connection
        self.interface = SNI_INTERFACES[0]
        self.properties = {}
        self.loaded = False
        self.alive = True

        # Tooltips are fetched lazily, when about to be shown (some items re-emit NewToolTip every
        # second, e.g. qBittorrent with its transfer speeds). Versions let several trays (one per
        # output) each notice that the tooltip they display is out of date.
        self.tooltip_version = 0
        self.tooltip_fetched_version = 0
        self.tooltip_fetching = False
        self.on_tooltip_fetched = {}

        # Decoded IconPixmap, shared by all trays: (pixmaps, icon size, pixbuf)
        self.pixmap_cache = None
        # Item-specific icon theme for IconThemePath (never added to the global theme)
        self.icon_theme = None
        self.icon_theme_path = None

        self._signal_id = 0
        self._pending_properties = set()
        self._pending_source = 0
        self._loading = False
        self._signal_while_loading = False
        self._retries = 0
        self._slow_retry_source = 0

        self.item_observer = DBusObserver(
            message_bus=SessionMessageBus(),
            service_name=self.service_name
        )
        self.item_observer.service_available.connect(
            self.item_available_handler
        )
        self.item_observer.service_unavailable.connect(
            self.item_unavailable_handler
        )
        self.item_observer.connect_once_available()

    def destroy(self):
        """Release everything held for this item: D-Bus subscriptions, name watch, timers."""
        self.alive = False
        if self._signal_id:
            self.connection.signal_unsubscribe(self._signal_id)
            self._signal_id = 0
        if self._pending_source:
            GLib.source_remove(self._pending_source)
            self._pending_source = 0
        if self._slow_retry_source:
            GLib.source_remove(self._slow_retry_source)
            self._slow_retry_source = 0
        self.item_observer.disconnect()
        self.on_loaded_callback = None
        self.on_updated_callback = None
        self.on_tooltip_fetched = {}

    # --- loading -------------------------------------------------------------------------------

    def item_available_handler(self, _observer):
        if not self.alive or self._signal_id:
            return
        # One subscription for every signal of the item: no introspection, no proxy.
        self._signal_id = self.connection.signal_subscribe(
            self.service_name, None, None, self.object_path, None,
            Gio.DBusSignalFlags.NONE, self._on_signal)
        self._load()

    def _load(self):
        self._pending_source = 0
        self._loading = True
        self._signal_while_loading = False
        self._get_all(0)
        return False

    def _get_all(self, interface_index):
        interface = SNI_INTERFACES[interface_index]
        self.connection.call(
            self.service_name, self.object_path, "org.freedesktop.DBus.Properties", "GetAll",
            GLib.Variant("(s)", (interface,)), GLib.VariantType("(a{sv})"),
            Gio.DBusCallFlags.NONE, DBUS_TIMEOUT_MS, None, self._on_get_all, interface_index)

    def _on_get_all(self, connection, result, interface_index):
        if not self.alive:
            return
        try:
            properties = unpack_properties(connection.call_finish(result).get_child_value(0))
            answered, reason = True, "it has none"
        except GLib.Error as e:
            properties = {}
            answered, reason = is_answer(e), e.message
        if not properties:
            if answered and interface_index + 1 < len(SNI_INTERFACES):
                self._get_all(interface_index + 1)
                return
            # Nothing is concluded from a read that failed: the item is not shown (an icon with no
            # properties would be blank, and deaf to clicks) until one succeeds.
            if not self._retries:
                eprint(f"Tray: can't read properties of {self.service_name}{self.object_path}: {reason}")
            self._loading = False
            self._retry_later(self._load)
            if self._signal_while_loading and not self._pending_source:
                # no retry is left to bring what the item announced during this read: one more for it
                self._load()
            return
        self._loading = False
        self._retries = 0
        self.interface = SNI_INTERFACES[interface_index]
        self.properties.update(properties)
        self.loaded = True
        if self.on_loaded_callback is not None:
            self.on_loaded_callback(self)

    def _retry_later(self, function):
        if self._pending_source:
            return
        if self._retries < MAX_RETRIES:
            self._retries += 1
            self._pending_source = GLib.timeout_add(RETRY_DELAY_MS, function)
        elif not self._slow_retry_source:
            self._slow_retry_source = GLib.timeout_add_seconds(SLOW_RETRY_DELAY_S, self._retry_slowly)

    def _retry_slowly(self):
        self._slow_retry_source = 0
        # only what no signal has made us read in the meantime
        if not self._loading and not self._pending_source:
            if not self.loaded:
                self._load()
            elif self._pending_properties:
                self._fetch_pending()
        return False

    def item_unavailable_handler(self, _observer):
        # The host removes the item (StatusNotifierItemUnregistered) and calls destroy()
        pass

    # --- changes -------------------------------------------------------------------------------

    def _on_signal(self, _connection, _sender, _path, interface, member, parameters):
        if not self.alive:
            return
        if not self.loaded:
            # Not read yet. If the application had not answered and we gave up, it is back: ask again.
            # What this signal announces will be in the reply, if there is one.
            if self._loading:
                self._signal_while_loading = True
            elif not self._pending_source:
                self._load()
            return
        if member == "PropertiesChanged" and interface == "org.freedesktop.DBus.Properties":
            if parameters.get_type_string() != "(sa{sv}as)" \
                    or parameters.get_child_value(0).get_string() not in SNI_INTERFACES:
                return
            # the new values come with the signal: no need to read them again
            changed = unpack_properties(parameters.get_child_value(1))
            names = list(changed)
            self.properties.update(changed)
            if "ToolTip" in names:
                self.tooltip_version += 1
                self.tooltip_fetched_version = self.tooltip_version
            self._notify(names)
            # Invalidated: changed, value not sent. Read again, as for NewIcon & co. (the old value is
            # kept meanwhile; one no longer exposed is dropped when the answer says so).
            invalidated_names = parameters.get_child_value(2)
            invalidated = [invalidated_names.get_child_value(i).get_string()
                           for i in range(min(invalidated_names.n_children(), MAX_PROPERTIES))]
            invalidated = [name for name in invalidated if name in PROPERTIES]
            if "ToolTip" in invalidated:
                invalidated.remove("ToolTip")
                self.tooltip_version += 1  # read lazily, as for NewToolTip
            self._schedule_fetch(invalidated)
        elif member == "NewToolTip":
            self.tooltip_version += 1
        elif member in ("NewStatus", "NewIconThemePath"):
            # the new value comes with the signal; anything but one string is ignored
            if parameters.get_type_string() == "(s)":
                name = member[len("New"):]
                self.properties[name] = parameters.unpack()[0]
                self._notify([name])
        elif member in SIGNAL_PROPERTIES:
            self._schedule_fetch(SIGNAL_PROPERTIES[member])

    def _schedule_fetch(self, names):
        if not names:
            return
        self._pending_properties.update(names)
        if not self._pending_source:
            self._pending_source = GLib.timeout_add(REFRESH_DELAY_MS, self._fetch_pending)

    def _fetch_pending(self):
        self._pending_source = 0
        names = sorted(self._pending_properties)
        self._pending_properties.clear()
        state = {"left": len(names), "changed": []}
        for name in names:
            self._get(name, self._on_pending_property, state)
        return False

    def _on_pending_property(self, name, value, state):
        if value is NO_ANSWER:
            self._pending_properties.add(name)
            self._retry_later(self._fetch_pending)
        elif value is not None:
            self._retries = 0
            self.properties[name] = value
            state["changed"].append(name)
        else:
            self._retries = 0
            # the item no longer exposes this property (e.g. icon given by name now, not pixmap)
            if self.properties.pop(name, None) is not None:
                state["changed"].append(name)
        state["left"] -= 1
        if state["left"] == 0:
            self._notify(state["changed"])

    def _get(self, name, callback, *args):
        def on_result(connection, result, _data):
            if not self.alive:
                return
            try:
                value = unpack_property(name, connection.call_finish(result).get_child_value(0).get_variant())
            except GLib.Error as e:
                value = None if is_answer(e) else NO_ANSWER
            callback(name, value, *args)

        self.connection.call(
            self.service_name, self.object_path, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (self.interface, name)), GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE, DBUS_TIMEOUT_MS, None, on_result, None)

    def _notify(self, changed_properties):
        if changed_properties and self.loaded and self.on_updated_callback is not None:
            self.on_updated_callback(self, changed_properties)

    # --- tooltip -------------------------------------------------------------------------------

    @property
    def tooltip_stale(self):
        return self.tooltip_fetched_version < self.tooltip_version

    def fetch_tooltip(self, image, callback):
        """Read the tooltip asynchronously; callback() runs once it is up to date. One callback is kept
        per image that shows it: GTK asks again on every pointer motion while the answer is awaited."""
        self.on_tooltip_fetched[image] = callback
        if self.tooltip_fetching:
            return
        self.tooltip_fetching = True
        requested_version = self.tooltip_version

        def on_tooltip(_name, value):
            self.tooltip_fetching = False
            callbacks, self.on_tooltip_fetched = list(self.on_tooltip_fetched.values()), {}
            if value is NO_ANSWER:
                return  # still stale: read again the next time it is about to be shown
            if value is not None:
                self.properties["ToolTip"] = value
            self.tooltip_fetched_version = max(self.tooltip_fetched_version, requested_version)
            for cb in callbacks:
                cb()

        self._get("ToolTip", on_tooltip)

    # --- actions -------------------------------------------------------------------------------

    def set_on_loaded_callback(self, callback):
        self.on_loaded_callback = callback

    def set_on_updated_callback(self, callback):
        self.on_updated_callback = callback

    @property
    def item_is_menu(self):
        if "ItemIsMenu" in self.properties:
            return self.properties["ItemIsMenu"]
        else:
            # Not said (libappindicator): an item with a menu shows it on left click, as before.
            # Without a menu the specification's default applies, false: the left click is Activate.
            return "Menu" in self.properties

    def _call(self, method, parameters):
        def on_result(connection, result, _data):
            try:
                connection.call_finish(result)
            except GLib.Error as e:
                eprint(f"Tray: {method} on {self.service_name} failed: {e.message}")

        self.connection.call(
            self.service_name, self.object_path, self.interface, method, parameters, None,
            Gio.DBusCallFlags.NONE, DBUS_TIMEOUT_MS, None, on_result, None)

    def context_menu(self, event: Gdk.EventButton):
        self._call("ContextMenu", GLib.Variant("(ii)", (int(event.x), int(event.y))))

    def activate(self, event: Gdk.EventButton):
        self._call("Activate", GLib.Variant("(ii)", (int(event.x), int(event.y))))

    def secondary_action(self, event: Gdk.EventButton):
        self._call("SecondaryActivate", GLib.Variant("(ii)", (int(event.x), int(event.y))))

    def scroll(self, distance, direction):
        self._call("Scroll", GLib.Variant("(is)", (int(distance), direction)))
