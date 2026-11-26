import unittest

from nwg_panel import tools

# Hyprland 0.57 omits "id" on special workspaces. The helper gives them the negative id that older versions used.
SPECIAL_WORKSPACE = {"address": "special:magic", "type": "special", "name": "special:magic", "monitor": "eDP-1"}
NORMAL_WORKSPACE = {"address": "1", "id": 1, "type": "normal", "name": "1", "monitor": "eDP-1"}


class HyprlandSpecialIdsTest(unittest.TestCase):
    def test_special_workspace_gets_negative_id(self):
        self.assertEqual(tools._h_with_special_ids(SPECIAL_WORKSPACE)["id"], -99)

    def test_normal_workspace_keeps_its_id(self):
        self.assertEqual(tools._h_with_special_ids(NORMAL_WORKSPACE)["id"], 1)

    def test_nested_special_workspace_in_client_gets_negative_id(self):
        client = {"address": "0x1", "workspace": SPECIAL_WORKSPACE}
        self.assertEqual(tools._h_with_special_ids(client)["workspace"]["id"], -99)

    def test_list_of_replies_is_converted_item_by_item(self):
        result = tools._h_with_special_ids([[SPECIAL_WORKSPACE, NORMAL_WORKSPACE]])
        self.assertEqual([ws["id"] for ws in result[0]], [-99, 1])


if __name__ == "__main__":
    unittest.main()
