from gi.repository import Gdk, Gio, GLib

from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver

from nwg_panel.tools import eprint

PROPERTIES = [
    "Id",
    "Category",
    "Title",
    "Status",
    "WindowId",
    "IconName",
    "IconPixmap",
    "OverlayIconName",
    "OverlayIconPixmap",
    "AttentionIconName",
    "AttentionIconPixmap",
    "AttentionMovieName",
    "ToolTip",
    "IconThemePath",
    "ItemIsMenu",
    "Menu"
]

SNI_INTERFACES = ["org.kde.StatusNotifierItem", "org.freedesktop.StatusNotifierItem"]

# Every call to an item is asynchronous and bounded: an application that registered a tray icon
# and then froze (or never answers) must not freeze the panel, which runs this on its GTK main loop.
DBUS_TIMEOUT_MS = 2000

# NewIcon & co. can come in bursts (animated icons): properties are re-read once per burst.
REFRESH_DELAY_MS = 50

# Signals that only say "something changed": the new value has to be read.
SIGNAL_PROPERTIES = {
    "NewTitle": ["Title"],
    "NewIcon": ["IconName", "IconPixmap"],
    "NewAttentionIcon": ["AttentionIconName", "AttentionIconPixmap"],
    "NewOverlayIcon": ["OverlayIconName", "OverlayIconPixmap"],
}


class StatusNotifierItem(object):
    def __init__(self, service_name, object_path):
        self.service_name = service_name
        self.object_path = object_path
        self.on_loaded_callback = None
        self.on_updated_callback = None
        self.connection = SessionMessageBus().connection
        self.interface = SNI_INTERFACES[0]
        self.properties = {
            "ItemIsMenu": True
        }
        self.loaded = False
        self.alive = True

        # Tooltips are fetched lazily, when about to be shown (some items re-emit NewToolTip every
        # second, e.g. qBittorrent with its transfer speeds). Versions let several trays (one per
        # output) each notice that the tooltip they display is out of date.
        self.tooltip_version = 0
        self.tooltip_fetched_version = 0
        self.tooltip_fetching = False
        self.on_tooltip_fetched = []

        # Decoded IconPixmap, shared by all trays: (key, pixbuf)
        self.pixmap_cache = None
        # Item-specific icon theme for IconThemePath (never added to the global theme)
        self.icon_theme = None
        self.icon_theme_path = None

        self._signal_id = 0
        self._pending_properties = set()
        self._pending_source = 0

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
        self.item_observer.disconnect()
        self.on_loaded_callback = None
        self.on_updated_callback = None
        self.on_tooltip_fetched = []

    # --- loading -------------------------------------------------------------------------------

    def item_available_handler(self, _observer):
        if not self.alive or self._signal_id:
            return
        # One subscription for every signal of the item: no introspection, no proxy.
        self._signal_id = self.connection.signal_subscribe(
            self.service_name, None, None, self.object_path, None,
            Gio.DBusSignalFlags.NONE, self._on_signal)
        self._get_all(0)

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
            properties = connection.call_finish(result).unpack()[0]
        except GLib.Error as e:
            if interface_index + 1 < len(SNI_INTERFACES):
                self._get_all(interface_index + 1)
                return
            eprint(f"Tray: can't read properties of {self.service_name}{self.object_path}: {e.message}")
            properties = {}
        self.interface = SNI_INTERFACES[interface_index]
        for name in PROPERTIES:
            if name in properties:
                self.properties[name] = properties[name]
        self.loaded = True
        if self.on_loaded_callback is not None:
            self.on_loaded_callback(self)

    def item_unavailable_handler(self, _observer):
        # The host removes the item (StatusNotifierItemUnregistered) and calls destroy()
        pass

    # --- changes -------------------------------------------------------------------------------

    def _on_signal(self, _connection, _sender, _path, interface, member, parameters):
        if not self.alive:
            return
        if member == "PropertiesChanged" and interface == "org.freedesktop.DBus.Properties":
            iface, changed, invalidated = parameters.unpack()
            if iface not in SNI_INTERFACES:
                return
            # the new values come with the signal: no need to read them again
            names = [name for name in changed if name in PROPERTIES]
            for name in names:
                self.properties[name] = changed[name]
            for name in invalidated:
                self.properties.pop(name, None)
            if "ToolTip" in names:
                self.tooltip_version += 1
                self.tooltip_fetched_version = self.tooltip_version
            self._notify(names)
        elif member == "NewToolTip":
            self.tooltip_version += 1
        elif member == "NewStatus":
            self.properties["Status"] = parameters.unpack()[0]
            self._notify(["Status"])
        elif member == "NewIconThemePath":
            self.properties["IconThemePath"] = parameters.unpack()[0]
            self._notify(["IconThemePath"])
        elif member in SIGNAL_PROPERTIES:
            self._pending_properties.update(SIGNAL_PROPERTIES[member])
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
        if value is not None:
            self.properties[name] = value
            state["changed"].append(name)
        else:
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
                value = connection.call_finish(result).unpack()[0]
            except GLib.Error:
                value = None
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

    def fetch_tooltip(self, callback):
        """Read the tooltip asynchronously; callback() runs once it is up to date."""
        self.on_tooltip_fetched.append(callback)
        if self.tooltip_fetching:
            return
        self.tooltip_fetching = True
        requested_version = self.tooltip_version

        def on_tooltip(_name, value):
            self.tooltip_fetching = False
            if value is not None:
                self.properties["ToolTip"] = value
            self.tooltip_fetched_version = max(self.tooltip_fetched_version, requested_version)
            callbacks, self.on_tooltip_fetched = self.on_tooltip_fetched, []
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
            return False

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
        self._call("SecondaryAction", GLib.Variant("(ii)", (int(event.x), int(event.y))))

    def scroll(self, distance, direction):
        self._call("Scroll", GLib.Variant("(is)", (int(distance), direction)))
