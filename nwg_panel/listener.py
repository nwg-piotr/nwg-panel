#!/usr/bin/python3

import zmq

from i3ipc import Connection, Event

context = zmq.Context()
print("Connecting to hello world server…")
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")


def send_message(i3, e):
    print("i3ipc event")
    socket.send(b"Hello")
    socket.recv()
    # print("Received reply %s" % (message))


def main():
    i3 = Connection()
    i3.on(Event.WINDOW_FOCUS, send_message)
    i3.on(Event.WORKSPACE_FOCUS, send_message)
    i3.main()


if __name__ == "__main__":
    main()
