#!/usr/bin/env python3

import os
import subprocess
import signal
import threading
import time

import gi
from gi.repository import GLib

from nwg_panel.tools import check_key, update_image, create_background_task, cmd_through_compositor, eprint

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

# seconds a timed out script gets to clean up after SIGTERM, before its process group gets SIGKILL
KILL_GRACE = 2


class Executor(Gtk.EventBox):
    def __init__(self, settings, icons_path, executor_name):
        self.name = executor_name
        self.settings = settings
        self.icons_path = icons_path
        Gtk.EventBox.__init__(self)
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(self.box)
        self.image = Gtk.Image()
        self.label = Gtk.Label.new("")
        self.icon_path = None
        self.icon_mtime = None
        self.dynamic_tooltip = False
        self.tooltip_state = None  # dynamic tooltip last set: (markup, image path, image mtime)
        self.loop_started = False
        self.run_lock = threading.Lock()
        self.rerun_pending = False  # a refresh requested while the script was running
        self.tooltip_image_path = None
        self.tooltip_image_key = None
        self.tooltip_box = None

        check_key(settings, "script", "")
        check_key(settings, "interval", 0)
        # "timeout" (optional): seconds after which a running script is terminated, see script_timeout()
        check_key(settings, "root-css-name", "root-executor")
        check_key(settings, "css-name", "")
        check_key(settings, "icon-placement", "left")
        check_key(settings, "icon-size", 16)
        check_key(settings, "tooltip-text", "")
        check_key(settings, "on-left-click", "")
        check_key(settings, "on-right-click", "")
        check_key(settings, "on-middle-click", "")
        check_key(settings, "on-scroll-up", "")
        check_key(settings, "on-scroll-down", "")
        check_key(settings, "angle", 0.0)
        check_key(settings, "sigrt", signal.SIGRTMIN)
        check_key(settings, "use-sigrt", False)

        self.label.set_angle(settings["angle"])

        # refresh signal in range SIGRTMIN+1 - SIGRTMAX
        self.sigrt = settings["sigrt"]
        self.use_sigrt = settings["use-sigrt"]

        if settings["angle"] != 0.0:
            self.box.set_orientation(Gtk.Orientation.VERTICAL)

        update_image(self.image, "view-refresh-symbolic", self.settings["icon-size"], self.icons_path)

        self.set_property("name", settings["root-css-name"])

        # reverting #57, as check_key only adds keys if MISSING, not if empty
        if settings["css-name"]:
            self.label.set_property("name", settings["css-name"])
        else:
            self.label.set_property("name", "executor-label")

        if settings["tooltip-text"]:
            self.set_tooltip_text(settings["tooltip-text"])

        if settings["on-left-click"] or settings["on-right-click"] or settings["on-middle-click"] or settings[
            "on-scroll-up"] or settings["on-scroll-down"]:
            self.connect('button-release-event', self.on_button_release)
            self.add_events(Gdk.EventMask.SCROLL_MASK)
            self.connect('scroll-event', self.on_scroll)

            self.connect('enter-notify-event', self.on_enter_notify_event)
            self.connect('leave-notify-event', self.on_leave_notify_event)

        self.build_box()
        self.refresh()

    def update_widget(self, output):
        # parse output
        label = new_path = tip = tip_image = None
        if output:
            output = [o.strip() for o in output]
            if len(output) == 1:
                if os.path.splitext(output[0])[1] in ('.svg', '.png'):
                    new_path = output[0]
                else:
                    label = output[0]
            elif len(output) == 2:
                new_path, label = output
            else:
                # 3+ lines: icon path (may be empty), label, then a tooltip (Pango markup, may span several lines)
                new_path, label = output[0], output[1]
                tip = output[2:]
                # optional image on top of the tooltip: 1st tooltip line = path to a .svg / .png file
                if os.path.splitext(tip[0])[1] in ('.svg', '.png') and os.path.isfile(tip[0]):
                    tip_image = tip[0]
                    tip = tip[1:]
                tip = "\n".join(tip)

        if tip_image or (tip and tip.strip()):
            self.set_dynamic_tooltip(tip, tip_image)
        elif self.dynamic_tooltip:
            # the script stopped providing a tooltip (or only blank lines): restore the static one (if any)
            self.set_tooltip_image(None)
            self.set_tooltip_text(self.settings["tooltip-text"] or None)
            self.dynamic_tooltip = False
            self.tooltip_state = None

        # update widget contents
        # A script may rewrite the same image file on each run (e.g. a generated graph):
        # reload it when the path OR the file modification time changed.
        new_mtime = None
        if new_path:
            try:
                new_mtime = os.path.getmtime(new_path)
            except OSError:
                pass  # icon name, not a file
        if new_path and (new_path != self.icon_path or new_mtime != self.icon_mtime):
            try:
                update_image(self.image,
                             new_path,
                             self.settings["icon-size"],
                             self.icons_path,
                             fallback=False)
                self.icon_path = new_path
                self.icon_mtime = new_mtime
            except:
                print("Failed setting image from {}".format(new_path))
                new_path = None

        if label:
            self.label.set_markup(label)

        # update widget visibility
        if new_path:
            if not self.image.get_visible():
                self.image.show()
        else:
            if self.image.get_visible():
                self.image.hide()

        if label:
            if not self.label.get_visible():
                self.label.show()
        else:
            if self.label.get_visible():
                self.label.hide()

        return False

    def set_dynamic_tooltip(self, markup, image):
        try:
            Pango.parse_markup(markup, -1, "\0")
        except GLib.Error:
            # not valid Pango markup: GTK would refuse it and show the text of the previous tooltip
            markup = GLib.markup_escape_text(markup)
        try:
            mtime = os.path.getmtime(image) if image else None
        except OSError:
            mtime = None
        # Setting a tooltip makes GTK query the tooltip under the pointer again, which restarts its delay,
        # whatever widget it belongs to. Don't do it on each run of the script, only when something changed.
        state = (markup, image, mtime)
        if state != self.tooltip_state:
            self.set_tooltip_image(image)
            self.set_tooltip_markup(markup or " ")
            self.tooltip_state = state
        self.dynamic_tooltip = True

    def set_tooltip_image(self, path):
        if path and self.tooltip_box is None:
            # built once, on first use: image above the Pango markup
            self.tooltip_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.tooltip_img = Gtk.Image()
            self.tooltip_img.set_halign(Gtk.Align.START)
            self.tooltip_lbl = Gtk.Label()
            self.tooltip_lbl.set_xalign(0)
            self.tooltip_box.pack_start(self.tooltip_img, False, False, 0)
            self.tooltip_box.pack_start(self.tooltip_lbl, False, False, 0)
            self.tooltip_box.show_all()
            self.connect("query-tooltip", self.on_query_tooltip)
        self.tooltip_image_path = path

    def load_tooltip_pixbuf(self, path):
        # A large picture would give a tooltip larger than the screen: fit it into half of the monitor
        # the widget is on. Smaller pictures keep their size.
        try:
            geometry = self.get_display().get_monitor_at_window(self.get_window()).get_geometry()
            max_width, max_height = geometry.width // 2, geometry.height // 2
        except Exception:
            max_width, max_height = 960, 540
        _, width, height = GdkPixbuf.Pixbuf.get_file_info(path)
        if width > max_width or height > max_height:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, max_width, max_height, True)
        return GdkPixbuf.Pixbuf.new_from_file(path)

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        path = self.tooltip_image_path
        if not path:
            return False  # default markup tooltip
        try:
            key = (path, os.path.getmtime(path))
            if key != self.tooltip_image_key:  # reload only when the file changed
                self.tooltip_img.set_from_pixbuf(self.load_tooltip_pixbuf(path))
                self.tooltip_image_key = key
        except Exception as e:
            print("Failed loading tooltip image {}: {}".format(path, e))
            return False
        markup = (self.get_tooltip_markup() or "").strip()
        self.tooltip_lbl.set_markup(markup)
        self.tooltip_lbl.set_visible(bool(markup))
        tooltip.set_custom(self.tooltip_box)
        return True

    def run_script(self):
        """
        Runs the script and returns its output; raises like subprocess.check_output() did.
        The script is started in its own session, i.e. as the leader of its own process group: when it times out,
        the commands it started (curl, ping...) are terminated with it instead of staying around as orphans.
        """
        timeout = script_timeout(self.settings)
        proc = subprocess.Popen(self.settings["script"].split(), stdout=subprocess.PIPE, start_new_session=True)
        try:
            output = proc.communicate(timeout=timeout)[0]
        except subprocess.TimeoutExpired as e:
            self.kill_script(proc)
            e.timeout = timeout  # communicate() may report what was left of it instead
            raise
        finally:
            proc.stdout.close()
        if proc.returncode:
            raise subprocess.CalledProcessError(proc.returncode, proc.args, output=output)
        return output

    def kill_script(self, proc):
        # SIGTERM, up to KILL_GRACE s to clean up, SIGKILL to what is left of the group. The script is only reaped
        # afterwards: until then its PID, which is also the ID of its process group, can't be given to another
        # process. Hence the poll with WNOWAIT, which sees the script exit without reaping it.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            deadline = time.monotonic() + KILL_GRACE
            while time.monotonic() < deadline:
                try:
                    if os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                        break
                except ChildProcessError:
                    break  # already reaped elsewhere: still SIGKILL the group, a child may have survived
                time.sleep(0.05)
            # also when the script is gone: a child of it may have survived SIGTERM
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError as e:
            eprint("Executor '{}': {}".format(self.name, e))
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # not ours to kill (sudo), or in uninterruptible sleep (dead network mount): don't wait for it
            eprint("Executor '{}': could not kill the script (PID {})".format(self.name, proc.pid))

    def get_output(self):
        if "script" in self.settings and self.settings["script"]:
            # Serialize runs: a signal-triggered refresh must not overlap the periodic one. The request is noted
            # before the lock is tried, so whoever holds the lock runs the script once more for it: requests that
            # arrive while the script runs are merged into one rerun, and no thread waits behind the lock.
            self.rerun_pending = True
            while self.rerun_pending and self.run_lock.acquire(blocking=False):
                self.rerun_pending = False
                try:
                    # a script that never returns used to hold the lock (and a thread) forever
                    output = self.run_script().decode("utf-8", errors="replace").splitlines()
                    GLib.idle_add(self.update_widget, output)
                except subprocess.TimeoutExpired as e:
                    eprint("Executor '{}': script timed out after {:g} s".format(self.name, e.timeout))
                except Exception as e:
                    print(e)
                finally:
                    self.run_lock.release()

    def refresh(self):
        # The periodic loop is started once; later calls (RT signal) run the script once.
        # Starting a new loop on each call would multiply the script executions (#67).
        if self.loop_started:
            thread = create_background_task(self.get_output, 0)
        else:
            self.loop_started = True
            thread = create_background_task(self.get_output, self.settings["interval"])
        thread.start()

    def build_box(self):
        if self.settings["icon-placement"] == "left":
            self.box.pack_start(self.image, False, False, 2)
        self.box.pack_start(self.label, False, False, 2)
        if self.settings["icon-placement"] != "left":
            self.box.pack_start(self.image, False, False, 2)

    def on_enter_notify_event(self, widget, event):
        widget.set_state_flags(Gtk.StateFlags.DROP_ACTIVE, clear=False)
        widget.set_state_flags(Gtk.StateFlags.SELECTED, clear=False)

    def on_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.DROP_ACTIVE)
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)

    def on_button_release(self, widget, event):
        if event.button == 1 and self.settings["on-left-click"]:
            self.launch(self.settings["on-left-click"])
        elif event.button == 2 and self.settings["on-middle-click"]:
            self.launch(self.settings["on-middle-click"])
        elif event.button == 3 and self.settings["on-right-click"]:
            self.launch(self.settings["on-right-click"])

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP and self.settings["on-scroll-up"]:
            self.launch(self.settings["on-scroll-up"])
        elif event.direction == Gdk.ScrollDirection.DOWN and self.settings["on-scroll-down"]:
            self.launch(self.settings["on-scroll-down"])
        else:
            print("No command assigned")

    def launch(self, cmd):
        cmd = cmd_through_compositor(cmd)

        print(f"Executing: {cmd}")
        subprocess.Popen('{}'.format(cmd), shell=True)


def to_number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def script_timeout(settings):
    """
    Seconds after which a running script is considered stuck and terminated: the "timeout" setting, by default
    max(interval, 300), and none with "interval": 0 (a one-shot or signal-driven script may legitimately run long).
    None = never. The config file may have been edited by hand: a value that is not a number ("5 min", null) is
    treated as missing.
    """
    timeout = to_number(settings.get("timeout"), None)
    if timeout is None:
        interval = to_number(settings.get("interval"), 0)
        timeout = max(300, interval) if interval > 0 else 0
    # 0 = no timeout. There can't be one longer than poll() is able to wait either: 2**31 ms, 24 days.
    return timeout if 0 < timeout < 2 ** 31 // 1000 else None
