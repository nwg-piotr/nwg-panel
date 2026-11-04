import os
import pathlib
import re
import unittest
from unittest.mock import patch

from nwg_panel import tools

# Hyprland 0.57 made the hl.dsp.* members factories: `hl.dsp.no_op` alone is refused, `hl.dsp.no_op()`
# is the dispatcher. 0.55 and 0.56 accept both forms; hyprlang configs know neither.
HYPRLAND_057 = {"dispatch hl.dsp.no_op()": "ok",
                "dispatch hl.dsp.no_op": "error: hl.dispatch: dispatcher factory supplied instead of a dispatcher"}
HYPRLAND_056 = {"dispatch hl.dsp.no_op()": "ok", "dispatch hl.dsp.no_op": "ok"}
HYPRLANG = {}


def fake_hyprctl(answers):
    return lambda cmd: answers.get(cmd, "Invalid dispatcher")


class CmdThroughHyprlandTest(unittest.TestCase):
    def through(self, answers):
        env = {k: v for k, v in os.environ.items() if k not in ("SWAYSOCK", "NIRI_SOCKET")}
        env["HYPRLAND_INSTANCE_SIGNATURE"] = "test"
        with patch.dict(os.environ, env, clear=True), \
                patch.object(tools, "load_json", return_value={}), \
                patch.object(tools, "hyprctl", side_effect=fake_hyprctl(answers)):
            return tools.cmd_through_compositor("foot")

    def test_lua_dispatchers_of_hyprland_057(self):
        self.assertEqual(self.through(HYPRLAND_057), "hyprctl dispatch 'hl.dsp.exec_cmd(\"foot\")'")

    def test_lua_dispatchers_of_hyprland_056(self):
        self.assertEqual(self.through(HYPRLAND_056), "hyprctl dispatch 'hl.dsp.exec_cmd(\"foot\")'")

    def test_hyprlang_config(self):
        self.assertEqual(self.through(HYPRLANG), "hyprctl dispatch exec foot")


class LuaDispatchersAreCalledTest(unittest.TestCase):
    def test_every_hl_dsp_dispatch_calls_its_factory(self):
        root = pathlib.Path(tools.__file__).parent
        uncalled = []
        for path in root.rglob("*.py"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for name in re.findall(r"dispatch (hl\.dsp\.[\w.]+)(?!\w|\.|\()", line):
                    uncalled.append(f"{path.name}:{n} {name}")
        self.assertEqual(uncalled, [])


if __name__ == "__main__":
    unittest.main()
