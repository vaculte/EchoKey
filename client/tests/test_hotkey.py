"""Tests for hotkey backend selection and evdev key mapping."""

import os
import unittest
from queue import Queue
from unittest import mock

from echokey import hotkey


class TestCreateListener(unittest.TestCase):
    @mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=True)
    @mock.patch.object(hotkey, "_evdev_available", return_value=True)
    def test_uses_evdev_on_wayland_when_available(self, _):
        listener = hotkey.create_listener(Queue())
        self.assertIsInstance(listener, hotkey.EvdevHotkeyListener)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_uses_pynput_on_x11(self):
        listener = hotkey.create_listener(Queue())
        self.assertIsInstance(listener, hotkey.PynputHotkeyListener)

    @mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}, clear=True)
    @mock.patch.object(hotkey, "_evdev_available", return_value=False)
    def test_falls_back_to_pynput_when_evdev_unavailable(self, _):
        listener = hotkey.create_listener(Queue())
        self.assertIsInstance(listener, hotkey.PynputHotkeyListener)


class TestEvdevKeyName(unittest.TestCase):
    def setUp(self):
        self.listener = hotkey.EvdevHotkeyListener(Queue())

    def test_target_keys(self):
        from evdev import ecodes

        self.assertEqual(self.listener._key_name(ecodes.KEY_F12), "f12")
        self.assertEqual(self.listener._key_name(ecodes.KEY_SPACE), "space")
        self.assertEqual(self.listener._key_name(ecodes.KEY_A), "a")

    def test_modifiers(self):
        from evdev import ecodes

        self.assertEqual(self.listener._key_name(ecodes.KEY_LEFTCTRL), "ctrl")
        self.assertEqual(self.listener._key_name(ecodes.KEY_RIGHTCTRL), "ctrl")
        self.assertEqual(self.listener._key_name(ecodes.KEY_LEFTALT), "alt")
        self.assertEqual(self.listener._key_name(ecodes.KEY_RIGHTALT), "alt")
        self.assertEqual(self.listener._key_name(ecodes.KEY_LEFTSHIFT), "shift")
        self.assertEqual(self.listener._key_name(ecodes.KEY_RIGHTSHIFT), "shift")
        self.assertEqual(self.listener._key_name(ecodes.KEY_LEFTMETA), "cmd")
        self.assertEqual(self.listener._key_name(ecodes.KEY_RIGHTMETA), "cmd")


class TestHotkeyParse(unittest.TestCase):
    def test_single_key(self):
        modifiers, target = hotkey._parse_hotkey("f12")
        self.assertEqual(modifiers, set())
        self.assertEqual(target, "f12")

    def test_combo(self):
        modifiers, target = hotkey._parse_hotkey("<cmd>+z")
        self.assertEqual(modifiers, {"cmd"})
        self.assertEqual(target, "z")
