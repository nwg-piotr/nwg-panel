import typing

from dasbus.connection import SessionMessageBus
from dasbus.loop import EventLoop
from dasbus.signal import Signal
from dasbus.client.observer import DBusObserver
from dasbus.server.interface import accepts_additional_arguments
import dasbus.typing

WATCHER_SERVICE_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_OBJECT_PATH = "/StatusNotifierWatcher"

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

        # libappindicator sends object path, use sender name and object path
        if service[0] == "/":
            full_service_name = "{}{}".format(call_info["sender"], service)

        # xembedsniproxy sends item name, use the item from the argument
        elif service[0] == ":":
            full_service_name = "{}{}".format(service, "/StatusNotifierItem")

        else:
            full_service_name = "{}{}".format(call_info["sender"], "/StatusNotifierItem")

        if full_service_name not in self._statusNotifierItems:
            item_service_observer = DBusObserver(
                message_bus=self.session_bus,
                service_name=call_info["sender"]
            )
            item_service_observer.service_available.connect(
                lambda _observer: self.item_available_handler(full_service_name)
            )
            item_service_observer.service_unavailable.connect(
                lambda _observer: self.item_unavailable_handler(full_service_name)
            )
            item_service_observer.connect_once_available()
        else:
            """print(
                (
                    "StatusNotifierWatcher -> RegisterStatusNotifierItem: item already registered\n"
                    "  full_service_name: {}"
                ).format(full_service_name, service)
            )"""

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
        # deinit on host (parent process) unavailable to avoid becoming zombie process
        deinit()


def init():
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
