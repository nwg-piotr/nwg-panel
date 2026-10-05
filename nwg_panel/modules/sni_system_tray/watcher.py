import multiprocessing
import os
import typing

from gi.repository import GLib

from dasbus.connection import SessionMessageBus
from dasbus.loop import EventLoop
from dasbus.signal import Signal
from dasbus.client.observer import DBusObserver
from dasbus.server.interface import accepts_additional_arguments
import dasbus.typing

from nwg_panel.tools import _die_with_parent, eprint

# items one bus connection (or one proxied connection) may register: well above what any real app does
MAX_ITEMS_PER_SENDER = 32

WATCHER_SERVICE_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_OBJECT_PATH = "/StatusNotifierWatcher"

PARENT_CHECK_DELAY_S = 1

dasbus_event_loop: typing.Union[EventLoop, None] = None


class StatusNotifierWatcherInterface(object):
    __dbus_xml__ = """
        <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        <node>
            <interface name="org.kde.StatusNotifierWatcher">
                <annotation name="org.gtk.GDBus.C.Name" value="Watcher" />

                <method name="RegisterStatusNotifierItem">
                    <annotation name="org.gtk.GDBus.C.Name" value="RegisterItem" />
                    <arg name="service" type="s" direction="in"/>
                </method>

                <method name="RegisterStatusNotifierHost">
                    <annotation name="org.gtk.GDBus.C.Name" value="RegisterHost" />
                    <arg name="service" type="s" direction="in"/>
                </method>

                <property name="RegisteredStatusNotifierItems" type="as" access="read">
                    <annotation name="org.gtk.GDBus.C.Name" value="RegisteredItems" />
                    <annotation name="org.qtproject.QtDBus.QtTypeName.Out0" value="QStringList"/>
                </property>

                <property name="IsStatusNotifierHostRegistered" type="b" access="read">
                    <annotation name="org.gtk.GDBus.C.Name" value="IsHostRegistered" />
                </property>

                <property name="ProtocolVersion" type="i" access="read"/>

                <signal name="StatusNotifierItemRegistered">
                    <annotation name="org.gtk.GDBus.C.Name" value="ItemRegistered" />
                    <arg type="s" direction="out" name="service" />
                </signal>

                <signal name="StatusNotifierItemUnregistered">
                    <annotation name="org.gtk.GDBus.C.Name" value="ItemUnregistered" />
                    <arg type="s" direction="out" name="service" />
                </signal>

                <signal name="StatusNotifierHostRegistered">
                    <annotation name="org.gtk.GDBus.C.Name" value="HostRegistered" />
                </signal>

                <signal name="StatusNotifierHostUnregistered">
                    <annotation name="org.gtk.GDBus.C.Name" value="HostUnregistered" />
                </signal>

            </interface>
        </node>
    """

    PropertiesChanged = Signal()
    StatusNotifierItemRegistered = Signal()
    StatusNotifierItemUnregistered = Signal()
    StatusNotifierHostRegistered = Signal()
    StatusNotifierHostUnregistered = Signal()

    def __init__(self):
        self._statusNotifierItems = []
        self._pending_items = set()  # registered, owner not seen on the bus yet
        self._statusNotifierHosts = []
        self._isStatusNotifierHostRegistered = False
        self._protocolVersion = 0
        self.session_bus = SessionMessageBus()

    def __del__(self):
        self.session_bus.disconnect()

    @accepts_additional_arguments
    def RegisterStatusNotifierItem(self, service, call_info):
        """print(
            "StatusNotifierWatcher -> RegisterStatusNotifierItem\n  service: {}\n  sender: {}".format(
                service,
                call_info["sender"]
            )
        )"""

        sender = call_info["sender"]
        if not isinstance(service, str) or not service:
            eprint("StatusNotifierWatcher: ignoring empty registration from {}".format(sender))
            return

        # libappindicator sends object path, use sender name and object path
        if service[0] == "/":
            owner = sender
            full_service_name = "{}{}".format(sender, service)

        # xembedsniproxy sends item name, use the item from the argument
        elif service[0] == ":":
            owner = service
            full_service_name = "{}{}".format(service, "/StatusNotifierItem")

        else:
            owner = sender
            full_service_name = "{}{}".format(sender, "/StatusNotifierItem")

        if full_service_name in self._statusNotifierItems or full_service_name in self._pending_items:
            return
        # any peer on the bus may call this: bound what one connection can make us track
        if sum(1 for name in self._statusNotifierItems + list(self._pending_items)
               if name.split("/", 1)[0] in (sender, owner)) >= MAX_ITEMS_PER_SENDER:
            eprint("StatusNotifierWatcher: too many items from {}, ignoring {}".format(sender, service))
            return

        self._pending_items.add(full_service_name)
        # watch the connection that actually owns the item: for xembedsniproxy that is `service`, not the
        # caller, otherwise an item whose connection is gone stays registered as long as the proxy lives
        item_service_observer = DBusObserver(
            message_bus=self.session_bus,
            service_name=owner
        )
        item_service_observer.service_available.connect(
            lambda _observer: self.item_available_handler(full_service_name)
        )
        item_service_observer.service_unavailable.connect(
            lambda _observer: self.item_unavailable_handler(full_service_name)
        )
        item_service_observer.connect_once_available()

    @accepts_additional_arguments
    def RegisterStatusNotifierHost(self, service, call_info):
        # print("StatusNotifierWatcher -> RegisterStatusNotifierHost: {}".format(service))
        if call_info["sender"] not in self._statusNotifierHosts:
            host_service_observer = DBusObserver(
                message_bus=self.session_bus,
                service_name=call_info["sender"]
            )
            host_service_observer.service_available.connect(
                self.host_available_handler
            )
            host_service_observer.service_unavailable.connect(
                self.host_unavailable_handler
            )
            host_service_observer.connect_once_available()
        """else:
            print(
                "StatusNotifierWatcher -> RegisterStatusNotifierHost: host already registered\n  service: {}\n  sender: {})".format(
                    service,
                    call_info["sender"]
                )
            )"""

    @property
    def RegisteredStatusNotifierItems(self) -> list:
        # print("StatusNotifierWatcher -> RegisteredStatusNotifierItems")
        return self._statusNotifierItems

    @property
    def IsStatusNotifierHostRegistered(self) -> bool:
        """print(
            "StatusNotifierWatcher -> IsStatusNotifierHostRegistered: {}".format(
                str(len(self._statusNotifierHosts) > 0)
            )
        )"""
        return len(self._statusNotifierHosts) > 0

    @property
    def ProtocolVersion(self) -> int:
        # print("StatusNotifierWatcher -> ProtocolVersion: ".format(str(self._protocolVersion)))
        return self._protocolVersion

    def item_available_handler(self, full_service_name):
        """print(
            "StatusNotifierWatcher -> item_available_handler\n  full_service_name: {}".format(
                full_service_name
            )
        )"""
        self._pending_items.discard(full_service_name)
        if full_service_name in self._statusNotifierItems:
            return
        self._statusNotifierItems.append(full_service_name)
        self.StatusNotifierItemRegistered.emit(full_service_name)
        self.PropertiesChanged.emit(WATCHER_SERVICE_NAME, {
            "RegisteredStatusNotifierItems": dasbus.typing.get_variant(
                dasbus.typing.List[dasbus.typing.Str],
                self._statusNotifierItems
            )
        }, [])

    def item_unavailable_handler(self, full_service_name):
        """print(
            "StatusNotifierWatcher -> item_unavailable_handler\n  full_service_name: {}".format(
                full_service_name
            )
        )"""
        self._pending_items.discard(full_service_name)
        if full_service_name in set(self._statusNotifierItems):
            self._statusNotifierItems.remove(full_service_name)
            self.StatusNotifierItemUnregistered.emit(full_service_name)
            self.PropertiesChanged.emit(WATCHER_SERVICE_NAME, {
                "RegisteredStatusNotifierItems": dasbus.typing.get_variant(
                    dasbus.typing.List[dasbus.typing.Str],
                    self._statusNotifierItems
                )
            }, [])

    def host_available_handler(self, observer):
        self._statusNotifierHosts.append(observer.service_name)
        self.StatusNotifierHostRegistered.emit()
        self.PropertiesChanged.emit(WATCHER_SERVICE_NAME, {
            "IsStatusNotifierHostRegistered": dasbus.typing.get_variant(dasbus.typing.Bool, True)
        }, [])

    def host_unavailable_handler(self, observer):
        self._statusNotifierHosts.remove(observer.service_name)
        self.StatusNotifierHostUnregistered.emit()
        if len(self._statusNotifierHosts) == 0:
            self.PropertiesChanged.emit(WATCHER_SERVICE_NAME, {
                "IsStatusNotifierHostRegistered": dasbus.typing.get_variant(dasbus.typing.Bool, False)
            }, [])
        # Quit once the panel that started us is gone, to avoid an orphan watcher. Any other host
        # leaving (a second nwg-panel instance...) must not take the tray down with it.
        # The bus name of a killed panel can vanish before we are given a new parent: look again
        # in a moment (only matters where _die_with_parent() does nothing).
        quit_if_orphan()
        GLib.timeout_add_seconds(PARENT_CHECK_DELAY_S, quit_if_orphan)


_parent_pid = os.getppid()


def quit_if_orphan():
    if os.getppid() != _parent_pid:
        deinit()
    return False


def init():
    global _parent_pid
    # the pid of the panel as it knows it: os.getppid() is already another one if it died meanwhile
    parent = multiprocessing.parent_process()
    _parent_pid = parent.pid if parent is not None else os.getppid()
    # Linux: SIGTERM as soon as the panel dies, however it dies (as for the helpers of popen_watcher)
    _die_with_parent()
    if os.getppid() != _parent_pid:
        return  # the panel died before the line above
    session_bus = SessionMessageBus()
    session_bus.publish_object(WATCHER_OBJECT_PATH, StatusNotifierWatcherInterface())
    session_bus.register_service(WATCHER_SERVICE_NAME)
    # print("watcher.init(): published {}{} on dbus.".format(WATCHER_SERVICE_NAME, WATCHER_OBJECT_PATH))

    global dasbus_event_loop
    if dasbus_event_loop is None:
        # print("watcher.init(): running dasbus.EventLoop")
        dasbus_event_loop = EventLoop()
        dasbus_event_loop.run()


def deinit():
    global dasbus_event_loop
    if dasbus_event_loop is not None:
        # print("watcher.deinit(): quitting dasbus.EventLoop")
        dasbus_event_loop.quit()
        dasbus_event_loop = None
