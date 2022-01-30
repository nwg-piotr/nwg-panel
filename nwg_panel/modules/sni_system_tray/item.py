from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver
from dasbus.client.proxy import disconnect_proxy
from dasbus.error import DBusError

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


class StatusNotifierItem(object):
    def __init__(self, service_name, object_path):
        self.service_name = service_name
        self.object_path = object_path
        self.on_loaded_callback = None
        self.on_updated_callback = None
        self.session_bus = SessionMessageBus()
        self.properties = {
            "ItemIsMenu": True
        }
        self.item_proxy = None

        self.item_observer = DBusObserver(
            message_bus=self.session_bus,
            service_name=self.service_name
        )
        self.item_observer.service_available.connect(
            self.item_available_handler
        )
        self.item_observer.service_unavailable.connect(
            self.item_unavailable_handler
        )
        self.item_observer.connect_once_available()

    def __del__(self):
        if self.item_proxy is not None:
            disconnect_proxy(self.item_proxy)
        self.item_observer.disconnect()
        self.session_bus.disconnect()

    def item_available_handler(self, _observer):
        self.item_proxy = self.session_bus.get_proxy(self.service_name, self.object_path)
        self.item_proxy.PropertiesChanged.connect(
            lambda _if, changed_properties, _invalid: self.change_handler(list(changed_properties))
        )
        self.item_proxy.NewTitle.connect(
            lambda _title: self.change_handler(["Title"])
        )
        self.item_proxy.NewIcon.connect(
            lambda _icon_name, _icon_pixmap: self.change_handler(["IconName", "IconPixmap"])
        )
        self.item_proxy.NewAttentionIcon.connect(
            lambda _icon_name, _icon_pixmap: self.change_handler(["AttentionIconName", "AttentionIconPixmap"])
        )
        if hasattr(self.item_proxy, "NewIconThemePath"):
            self.item_proxy.NewIconThemePath.connect(
                lambda _icon_theme_path: self.change_handler(["IconThemePath"])
            )
        self.item_proxy.NewStatus.connect(
            lambda _status: self.change_handler(["Status"])
        )
        for name in PROPERTIES:
            try:
                self.properties[name] = getattr(self.item_proxy, name)
            except (AttributeError, DBusError):
                # remote StatusNotifierItem object does not support all SNI properties
                pass
        if self.on_loaded_callback is not None:
            self.on_loaded_callback(self)

    def item_unavailable_handler(self, _observer):
        disconnect_proxy(self.item_proxy)
        self.item_proxy = None

    def change_handler(self, changed_properties: list[str]):
        if len(changed_properties) > 0:
            for name, value in changed_properties:
                self.properties[name] = value
            if self.on_updated_callback is not None:
                self.on_updated_callback(self, changed_properties)

    def set_on_loaded_callback(self, callback):
        self.on_loaded_callback = callback

    def set_on_updated_callback(self, callback):
        self.on_updated_callback = callback
