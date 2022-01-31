import typing
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("DbusmenuGtk3", "0.4")

from gi.repository import Gdk, Gtk, DbusmenuGtk3

from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver


class Menu(object):
    def __init__(self, service_name, object_path, event_box, item):
        self.service_name = service_name
        self.object_path = object_path
        self.event_box = event_box
        self.item = item
        self.session_bus = SessionMessageBus()
        self.menu_widget: typing.Union[None, DbusmenuGtk3.Menu] = None

        self.menu_observer = DBusObserver(
            message_bus=self.session_bus,
            service_name=self.service_name
        )
        self.menu_observer.service_available.connect(
            self.menu_available_handler
        )
        self.menu_observer.service_unavailable.connect(
            self.menu_unavailable_handler
        )
        self.menu_observer.connect_once_available()

    def __del__(self):
        self.menu_observer.disconnect()
        self.session_bus.disconnect()

    def menu_available_handler(self, _observer):
        print(
            "Menu -> menu_available_handler: Connecting to menu over dbus:\n"
            "  service_name: {}\n"
            "  object_path: {}".format(
                self.service_name,
                self.object_path
            )
        )
        self.menu_widget = DbusmenuGtk3.Menu().new(
            dbus_name=self.service_name,
            dbus_object=self.object_path
        )
        self.menu_widget.show()
        self.event_box.connect("button-press-event", self.button_press_event_handler)

    def menu_unavailable_handler(self, _observer):
        self.event_box.disconnect_by_func(self.button_press_event_handler)

    def button_press_event_handler(self, _w, event: Gdk.EventButton):
        if (event.button == 1 and self.item.item_is_menu) or event.button == 3:
            if self.menu_widget is not None:
                self.menu_widget.popup_at_widget(
                    self.event_box,
                    Gdk.Gravity.SOUTH,
                    Gdk.Gravity.NORTH,
                    event
                )
            else:
                self.item.context_menu(event)
        elif event.button == 1:
            self.item.activate(event)
        elif event.button == 2:
            self.item.secondary_action(event)
