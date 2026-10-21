import unittest
from unittest.mock import patch

from nwg_panel import common, tools


DISPLAY_DEVICE = b"/org/freedesktop/UPower/devices/DisplayDevice\n"


class BatteryDetectionTest(unittest.TestCase):
    def test_ignores_peripheral_battery(self):
        mouse_info = b"  power supply:         no\n  percentage:          10%\n  mouse\n"
        with patch.dict(common.commands, {"upower": True}), \
                patch.object(tools.subprocess, "check_output", side_effect=[DISPLAY_DEVICE, mouse_info]), \
                patch.object(tools, "get_battery_sysfs", return_value=None):
            self.assertIsNone(tools.get_battery())

    def test_uses_system_laptop_battery(self):
        laptop_info = (
            b"  power supply:         yes\n"
            b"  state:                charging\n"
            b"  time to full:         1.2 hours\n"
            b"  percentage:           73%\n"
            b"  battery\n"
        )
        with patch.dict(common.commands, {"upower": True}), \
                patch.object(tools.subprocess, "check_output", side_effect=[DISPLAY_DEVICE, laptop_info]):
            self.assertEqual(tools.get_battery(), (73, "1.2 hours", True))

    def test_ignores_ups_for_laptop_battery_indicator(self):
        ups_info = b"  power supply:         yes\n  percentage:           73%\n  ups\n"
        with patch.dict(common.commands, {"upower": True}), \
                patch.object(tools.subprocess, "check_output", side_effect=[DISPLAY_DEVICE, ups_info]), \
                patch.object(tools, "get_battery_sysfs", return_value=None):
            self.assertIsNone(tools.get_battery())

    def test_uses_system_sysfs_battery_without_upower(self):
        sysfs_battery = (61, "", False)
        with patch.dict(common.commands, {"upower": False}), \
                patch.object(tools, "get_battery_sysfs", return_value=sysfs_battery):
            self.assertEqual(tools.get_battery(), sysfs_battery)


if __name__ == "__main__":
    unittest.main()
