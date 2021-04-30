# This file is part of nvitop, the interactive NVIDIA-GPU process viewer.
# License: GNU GPL version 3.

# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import curses
import threading
import time
import shutil
import sys

from .displayable import DisplayableContainer
from .keybinding import ALT_KEY, KeyBuffer, KeyMaps
from .mouse import MouseEvent
from .panels import DevicePanel, ProcessPanel


class BreakLoop(Exception):
    pass


class Top(DisplayableContainer):
    def __init__(self, devices, mode='auto', win=None):
        super().__init__(win, root=self)
        self.width = max(79, shutil.get_terminal_size(fallback=(79, 24)).columns)
        if not sys.stdout.isatty():
            self.width = 1024
        self.termsize = None

        assert mode in ('auto', 'full', 'compact')
        compact = (mode == 'compact')
        self._mode = mode
        self._compact = compact

        self.devices = devices
        self.device_count = len(self.devices)

        self.lock = threading.RLock()

        self.device_panel = DevicePanel(self.devices, compact, win=win, root=self)
        self.device_panel.focused = False
        self.add_child(self.device_panel)

        self.process_panel = ProcessPanel(self.devices, win=win, root=self)
        self.process_panel.focused = False
        self.add_child(self.process_panel)

        self.device_panel.y = 1
        self.process_panel.y = self.device_panel.y + self.device_panel.height + 1
        self.height = 1 + self.device_panel.height + 1 + self.process_panel.height

        if win is not None:
            self.keybuffer = KeyBuffer()
            self.keymaps = KeyMaps(self.keybuffer)
            self.last_input_time = time.time()
            self.init_keybindings()

    @property
    def compact(self):
        return self._compact

    @compact.setter
    def compact(self, value):
        if self._compact != value:
            self.need_redraw = True
            self._compact = value

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        if self._mode != value:
            self._mode = value
            self.update_size()

    def init_keybindings(self):
        # pylint: disable=multiple-statements

        def quit(top): raise BreakLoop  # pylint: disable=redefined-builtin

        def auto_mode(top): top.mode = 'auto'
        def full_mode(top): top.mode = 'full'
        def compact_mode(top): top.mode = 'compact'

        def host_left(top): top.process_panel.host_offset -= 1
        def host_right(top): top.process_panel.host_offset += 1
        def host_begin(top): top.process_panel.host_offset = -1
        def host_end(top): top.process_panel.host_offset = 1024

        def select_up(top): top.process_panel.selected.move(direction=-1)
        def select_down(top): top.process_panel.selected.move(direction=+1)
        def select_clear(top): top.process_panel.selected.clear()

        def terminate(top): top.process_panel.selected.terminate()
        def kill(top): top.process_panel.selected.kill()
        def interrupt(top): top.process_panel.selected.interrupt()

        self.keymaps.bind('root', 'q', quit)
        self.keymaps.copy('root', 'q', 'Q')
        self.keymaps.bind('root', 'a', auto_mode)
        self.keymaps.bind('root', 'f', full_mode)
        self.keymaps.bind('root', 'c', compact_mode)

        self.keymaps.bind('root', '<Left>', host_left)
        self.keymaps.copy('root', '<Left>', '[')
        self.keymaps.bind('root', '<Right>', host_right)
        self.keymaps.copy('root', '<Right>', ']')
        self.keymaps.bind('root', '<Home>', host_begin)
        self.keymaps.copy('root', '<Home>', '<C-a>')
        self.keymaps.copy('root', '<Home>', '^')
        self.keymaps.bind('root', '<End>', host_end)
        self.keymaps.copy('root', '<End>', '<C-e>')
        self.keymaps.copy('root', '<End>', '$')
        self.keymaps.bind('root', '<Up>', select_up)
        self.keymaps.copy('root', '<Up>', '<S-Tab>')
        self.keymaps.bind('root', '<Down>', select_down)
        self.keymaps.copy('root', '<Down>', '<Tab>')
        self.keymaps.bind('root', '<Esc>', select_clear)

        self.keymaps.bind('root', 'T', terminate)
        self.keymaps.bind('root', 'K', kill)
        self.keymaps.bind('root', '<C-c>', interrupt)
        self.keymaps.copy('root', '<C-c>', 'I')

        self.keymaps.use_keymap('root')

    def update_size(self):
        curses.update_lines_cols()  # pylint: disable=no-member
        n_term_lines, self.width = termsize = self.win.getmaxyx()
        if self.mode == 'auto':
            self.compact = (n_term_lines < 1 + self.device_panel.full_height + 1 + self.process_panel.height)
        else:
            self.compact = (self.mode == 'compact')
        self.device_panel.compact = self.compact
        self.process_panel.y = self.device_panel.y + self.device_panel.height + 1
        self.height = 1 + self.device_panel.height + 1 + self.process_panel.height
        self.process_panel.width = self.width
        if self.termsize != termsize:
            self.termsize = termsize
            self.need_redraw = True

    def poke(self):
        super().poke()

        if self.termsize is None or self.height != self.device_panel.height + 1 + self.process_panel.height:
            self.update_size()

    def draw(self):
        if self.need_redraw:
            self.win.erase()
            self.addstr(self.y, self.x + 62, '(Press q to quit)')
            self.color_at(self.y, self.x + 69, width=1, fg='magenta', attr='bold | italic')
        time_string = time.strftime('%a %b %d %H:%M:%S %Y')
        self.addstr(self.y, self.x, '{:<62}'.format(time_string))
        self.color_at(self.y, self.x + len(time_string) - 11, width=1, attr='blink')
        self.color_at(self.y, self.x + len(time_string) - 8, width=1, attr='blink')

        super().draw()

    def finalize(self):
        super().finalize()
        self.win.refresh()

    def redraw(self):
        self.poke()
        self.draw()
        self.finalize()

    def loop(self):
        if self.win is None:
            return

        while True:
            try:
                self.redraw()
                self.handle_input()
                if time.time() - self.last_input_time > 1.0:
                    time.sleep(0.25)
            except BreakLoop:
                break

    def print(self):
        print(time.strftime('%a %b %d %H:%M:%S %Y'))
        self.device_panel.print()
        print()
        self.process_panel.print()

    def handle_mouse(self):
        """Handles mouse input"""

        try:
            event = MouseEvent(curses.getmouse())
        except curses.error:
            return
        else:
            super().click(event)

    def handle_key(self, key):
        """Handles key input"""

        if key < 0:
            self.keybuffer.clear()
        elif not super().press(key):
            self.keymaps.use_keymap('root')
            self.press(key)

    def handle_keys(self, *keys):
        for key in keys:
            self.handle_key(key)

    def press(self, key):
        keybuffer = self.keybuffer

        keybuffer.add(key)
        if keybuffer.result is not None:
            try:
                keybuffer.result(self)
            finally:
                if keybuffer.finished_parsing:
                    keybuffer.clear()
        elif keybuffer.finished_parsing:
            keybuffer.clear()
            return False
        return True

    def handle_input(self):  # pylint: disable=too-many-branches
        key = self.win.getch()
        if key == curses.ERR:
            return

        self.last_input_time = time.time()
        if key == curses.KEY_ENTER:
            key = ord('\n')
        if key == 27 or (128 <= key < 256):
            # Handle special keys like ALT+X or unicode here:
            keys = [key]
            for _ in range(4):
                getkey = self.win.getch()
                if getkey != -1:
                    keys.append(getkey)
            if len(keys) == 1:
                keys.append(-1)
            elif keys[0] == 27:
                keys[0] = ALT_KEY
            self.handle_keys(*keys)
            curses.flushinp()
        elif key >= 0:
            # Handle simple key presses, CTRL+X, etc here:
            curses.flushinp()
            if key == curses.KEY_MOUSE:
                self.handle_mouse()
            elif key == curses.KEY_RESIZE:
                self.update_size()
            else:
                self.handle_key(key)
