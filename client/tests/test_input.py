"""Tests for text input backend selection."""

import os
import unittest
from unittest import mock

from echokey import input as input_module


class TestTypeText(unittest.TestCase):
    @mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=True)
    @mock.patch.object(input_module, "_wtype_available", return_value=True)
    @mock.patch.object(input_module, "_wl_clipboard_available", return_value=True)
    def test_uses_wayland_clipboard_paste(self, *_):
        with mock.patch("subprocess.run") as mock_run:
            wl_paste_result = mock.Mock()
            wl_paste_result.returncode = 0
            wl_paste_result.stdout = "previous clipboard"
            mock_run.side_effect = [
                wl_paste_result,  # wl-paste
                None,  # wl-copy text
                None,  # wtype Ctrl+V
                None,  # wl-copy restore
            ]
            input_module.type_text("hello")
            self.assertEqual(mock_run.call_count, 4)
            mock_run.assert_any_call(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            mock_run.assert_any_call(["wl-copy", "hello"], check=True, timeout=5)
            mock_run.assert_any_call(["wtype", "-M", "ctrl", "v"], check=True, timeout=5)
            mock_run.assert_any_call(["wl-copy", "previous clipboard"], check=True, timeout=5)

    @mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=True)
    @mock.patch.object(input_module, "_wtype_available", return_value=True)
    @mock.patch.object(input_module, "_wl_clipboard_available", return_value=False)
    @mock.patch("subprocess.run")
    def test_uses_direct_wtype_without_clipboard_tools(self, mock_run, *_):
        input_module.type_text("hello")
        mock_run.assert_called_once_with(["wtype", "hello"], check=True, timeout=30)

    @mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=True)
    @mock.patch.object(input_module, "_wtype_available", return_value=True)
    @mock.patch.object(input_module, "_wl_clipboard_available", return_value=True)
    @mock.patch.object(input_module, "_type_with_pynput")
    @mock.patch("subprocess.run", side_effect=RuntimeError("wtype crashed"))
    def test_falls_back_to_pynput_when_wtype_fails(
        self, _mock_run, mock_pynput, *_
    ):
        input_module.type_text("hello")
        mock_pynput.assert_called_once_with("hello")

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch.object(input_module, "_wtype_available", return_value=False)
    @mock.patch.object(input_module, "_wl_clipboard_available", return_value=False)
    @mock.patch.object(input_module, "_type_with_pynput")
    def test_uses_pynput_on_x11(self, mock_pynput, *_):
        input_module.type_text("hello")
        mock_pynput.assert_called_once_with("hello")
