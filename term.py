# -*- coding: utf-8 -*-
#
# Copyright (c) 2017-2019 by Simmo Saan <simmo.saan@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

#
# History:
#
# 2019-04-07, Simmo Saan <simmo.saan@gmail.com>
#   version 0.3: window resizing, only dirty rendering and pyte 0.8.0 support
# 2017-08-13, Simmo Saan <simmo.saan@gmail.com>
#   version 0.2: process cleanup, colors and attributes support
# 2017-08-13, Simmo Saan <simmo.saan@gmail.com>
#   version 0.1: initial script
#

"""
Virtual terminal emulator inside WeeChat buffer
"""

from __future__ import print_function, unicode_literals

SCRIPT_NAME = "term"
SCRIPT_AUTHOR = "Simmo Saan <simmo.saan@gmail.com>"
SCRIPT_VERSION = "0.3"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC = "Virtual terminal emulator inside WeeChat buffer"

SCRIPT_REPO = "https://github.com/sim642/weechat-term"

SCRIPT_COMMAND = SCRIPT_NAME
SCRIPT_BUFFER = SCRIPT_NAME

IMPORT_OK = True

try:
    import weechat
except ImportError:
    print("This script must be run under WeeChat.")
    print("Get WeeChat now at: http://www.weechat.org/")
    IMPORT_OK = False

import pyte, pyte.modes
import os, pty, signal
import shlex
import pyte.screens, pyte.graphics
import fcntl, termios, struct

def log(string):
    """Log script's message to core buffer."""

    weechat.prnt("", "{}: {}".format(SCRIPT_NAME, string))

def error(string):
    """Log script's error to core buffer."""

    weechat.prnt("", "{}{}: {}".format(weechat.prefix("error"), SCRIPT_NAME, string))

terms = {}

class Term:
    def __init__(self, command):
        self.command = command

        self.buffer = self.create_buffer()

        self.screen = pyte.Screen(80, 24)
        # self.screen.set_mode(pyte.modes.LNM)
        self.screen.write_process_input = lambda data: self.input(data.encode("charmap"))
        self.stream = pyte.ByteStream(self.screen)

        self.pid = None
        self.hook_fd = ""
        self.f = None

    def run(self):
        self.pid, fd = self.fork()

        self.hook_fd = weechat.hook_fd(fd, 1, 0, 0, "term_fd_cb", self.buffer)
        self.f = os.fdopen(fd, "w+b", 0)

        weechat.buffer_set(self.buffer, "display", "1") # switch to buffer

    buffer_index = 0

    @classmethod
    def create_buffer(cls):
        name = "{}.{}".format(SCRIPT_BUFFER, cls.buffer_index)
        cls.buffer_index += 1

        buffer = weechat.buffer_new(name, "term_buffer_input_cb", "", "term_buffer_close_cb", "")
        weechat.buffer_set(buffer, "type", "free")

        return buffer

    def get_fit_size(self):
        widths = []
        heights = []

        infolist = weechat.infolist_get("window", "", "")
        while weechat.infolist_next(infolist):
            buffer = weechat.infolist_pointer(infolist, "buffer")
            if buffer == self.buffer:
                width = weechat.infolist_integer(infolist, "chat_width")
                height = weechat.infolist_integer(infolist, "chat_height")

                widths.append(width)
                heights.append(height)
        weechat.infolist_free(infolist)

        if widths and heights:
            return (min(heights), min(widths))
        else:
            return None

    def resize(self, lines, columns):
        if not self.pid: # not running
            return

        self.screen.resize(lines, columns)
        fcntl.ioctl(self.f.fileno(), termios.TIOCSWINSZ, struct.pack("HHHH", lines, columns, 0, 0)) # crazy kernel magic
        os.kill(self.pid, signal.SIGWINCH)
        self.render()

    def resized(self):
        size = self.get_fit_size()
        if size:
            self.resize(*size)

    def fork(self):
        pid, fd = pty.fork()
        if pid == 0: # child
            args = shlex.split(self.command)
            env = self.get_env()
            try:
                os.execvpe(args[0], args, env)
            except OSError as e: # args[0] not found
                os._exit(1)


        return pid, fd

    def get_env(self):
        env = {}
        env.update(os.environ) # copy to not modify os.environ

        env["TERM"] = "xterm-256color"
        # env["COLUMNS"] = str(self.screen.columns)
        # env["LINES"] = str(self.screen.lines)

        return env

    def display_line(self, line):
        # copied from pyte.Screen

        wcwidth = pyte.screens.wcwidth

        is_wide_char = False
        for x in range(self.screen.columns):
            if is_wide_char:  # Skip stub
                is_wide_char = False
                continue
            char = line[x].data
            assert sum(map(wcwidth, char[1:])) == 0
            is_wide_char = wcwidth(char[0]) == 2
            yield line[x]

    @classmethod
    def color2weechat(cls, color):
        if color in pyte.graphics.FG_BG_256:
            return str(pyte.graphics.FG_BG_256.index(color))
        elif color in pyte.graphics.FG_ANSI.values():
            return color
        else:
            raise RuntimeError("invalid color: '{}'".format(color))

    @classmethod
    def render_char(cls, char):
        attrs = {
            "*": char.bold,
            "/": char.italics,
            "_": char.underscore,
            "!": char.reverse
        }
        attrs_str = "".join([attr for attr, b in attrs.items() if b])

        return weechat.color("{attrs}{fg},{bg}".format(
            attrs=attrs_str,
            fg=cls.color2weechat(char.fg),
            bg=cls.color2weechat(char.bg)
        )) + char.data

    @classmethod
    def render_line(cls, line):
        return "".join(map(cls.render_char, line))

    def render(self):
        for y in self.screen.dirty:
            line = self.display_line(self.screen.buffer[y])
            message = self.render_line(line) + weechat.color("reset")
            weechat.prnt_y(self.buffer, y, message.encode("utf-8"))
            
        self.screen.dirty.clear()

        # weechat.prnt("", "\n".join([line.encode("utf-8").rstrip() for line in self.screen.display]).rstrip())

    def input(self, data):
        if self.pid:
            self.f.write(data)
            self.render()
        else:
            error("cannot write to ended process")

    def close(self):
        self.closed()

    def closed(self):
        if not self.pid: # already closed
            return

        weechat.unhook(self.hook_fd)
        self.hook_fd = ""

        self.f.close()
        self.f = None

        os.kill(self.pid, signal.SIGTERM)
        os.waitpid(self.pid, 0)
        self.pid = None

    def output(self, fd):
        try:
            data = os.read(fd, 1024)
        except OSError:
            data = bytes()

        if len(data) > 0:
            self.stream.feed(data)
            self.render()
        else:
            self.closed()


def term_buffer_input_cb(data, buffer, input_data):
    term = terms[buffer]
    term.input((input_data + "\n").encode("utf-8"))

    return weechat.WEECHAT_RC_OK

def term_buffer_close_cb(data, buffer):
    term = terms[buffer]
    term.close()

    return weechat.WEECHAT_RC_OK

def term_fd_cb(data, fd):
    term = terms[data]
    term.output(int(fd))

    return weechat.WEECHAT_RC_OK

def term_buffer_resize_cb(data, signal, signal_data):
    if signal_data in terms:
        term = terms[signal_data]
        term.resized()

    return weechat.WEECHAT_RC_OK

def term_window_resize_cb(data, signal, signal_data):
    infolist = weechat.infolist_get("window", signal_data, "")
    if weechat.infolist_next(infolist):
        buffer = weechat.infolist_pointer(infolist, "buffer")
        if buffer in terms:
            term = terms[buffer]
            term.resized()
    weechat.infolist_free(infolist)

    return weechat.WEECHAT_RC_OK


def term_command_cb(data, buffer, args):
    """Handle command hook."""

    term = Term(args)
    terms[term.buffer] = term

    term.run()

    return weechat.WEECHAT_RC_OK

def term_shutdown_cb():
    for term in terms.values():
        term.closed()

    return weechat.WEECHAT_RC_OK

if __name__ == "__main__" and IMPORT_OK:
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "term_shutdown_cb", ""):
        weechat.hook_command(SCRIPT_COMMAND, SCRIPT_DESC,
"""<command>""",
"""command: the command to execute""",
"""""", # TODO: bash completion
                             "term_command_cb", "")

        weechat.hook_signal("buffer_switch", "term_buffer_resize_cb", "")
        weechat.hook_signal("window_zoomed", "term_window_resize_cb", "")
        weechat.hook_signal("window_unzoomed", "term_window_resize_cb", "")