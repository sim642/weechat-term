# -*- coding: utf-8 -*-
#
# Copyright (c) 2017 by Simmo Saan <simmo.saan@gmail.com>
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
# 2017-08-12, Simmo Saan <simmo.saan@gmail.com>
#   version 0.1: initial script
#

"""
Virtual terminal emulator inside WeeChat buffer
"""

from __future__ import print_function, unicode_literals

SCRIPT_NAME = "term"
SCRIPT_AUTHOR = "Simmo Saan <simmo.saan@gmail.com>"
SCRIPT_VERSION = "0.1"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC = "Virtual terminal emulator inside WeeChat buffer"

# SCRIPT_REPO = "https://github.com/sim642/latex_unicode"

SCRIPT_COMMAND = SCRIPT_NAME
SCRIPT_BUFFER = SCRIPT_NAME

IMPORT_OK = True

try:
    import weechat
except ImportError:
    print("This script must be run under WeeChat.")
    print("Get WeeChat now at: http://www.weechat.org/")
    IMPORT_OK = False

from collections import namedtuple
import pyte, pyte.modes
import os, pty
import shlex

def log(string):
    """Log script's message to core buffer."""

    weechat.prnt("", "{}: {}".format(SCRIPT_NAME, string))

def error(string):
    """Log script's error to core buffer."""

    weechat.prnt("", "{}{}: {}".format(weechat.prefix("error"), SCRIPT_NAME, string))


buffer_i = 0
# Term = namedtuple("Term", ["screen", "stream", "fd", "hook_fd"])
terms = {}

class Term:
    def __init__(self, command):
        self.command = command

        self.buffer = self.create_buffer()

        self.screen = pyte.Screen(80, 24)
        self.screen.set_mode(pyte.modes.LNM)
        self.stream = pyte.ByteStream(self.screen)

        self.pid = None
        self.hook_fd = ""
        self.f = None

    def run(self):
        self.pid, fd = self.fork()

        self.hook_fd = weechat.hook_fd(fd, 1, 0, 0, "term_fd_cb", self.buffer)
        self.f = os.fdopen(fd, "w+", 0)

    buffer_index = 0

    @classmethod
    def create_buffer(cls):
        name = "{}.{}".format(SCRIPT_BUFFER, cls.buffer_index)
        cls.buffer_index += 1

        buffer = weechat.buffer_new(name, "term_buffer_input_cb", "", "term_buffer_close_cb", "")
        weechat.buffer_set(buffer, "type", "free")
        weechat.buffer_set(buffer, "display", "1") # switch to buffer

        return buffer

    def fork(self):
        pid, fd = pty.fork()
        if pid == 0: # child
            args = shlex.split(self.command)
            env = self.get_env()
            os.execvpe(args[0], args, env)

        return pid, fd

    def get_env(self):
        env = {}
        env.update(os.environ) # copy to not modify os.environ

        env["TERM"] = "linux"
        env["COLUMNS"] = str(self.screen.columns)
        env["LINES"] = str(self.screen.lines)

        return env

    def render(self):
        for i, line in enumerate(self.screen.display, 1):
            weechat.prnt_y(self.buffer, i - 1, line)

    def input(self, data):
        self.f.write(data + "\n")
        self.render()

    def close(self):
        pass

    def closed(self):
        weechat.unhook(self.hook_fd)
        self.hook_fd = ""

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
    term.input(input_data)

    return weechat.WEECHAT_RC_OK

def term_buffer_close_cb(data, buffer):
    term = terms[buffer]
    term.close()

    return weechat.WEECHAT_RC_OK

def term_fd_cb(data, fd):
    term = terms[data]
    term.output(int(fd))

    return weechat.WEECHAT_RC_OK


def term_command_cb(data, buffer, args):
    """Handle command hook."""

    term = Term(args)
    terms[term.buffer] = term

    term.run()

    return weechat.WEECHAT_RC_OK

if __name__ == "__main__" and IMPORT_OK:
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        weechat.hook_command(SCRIPT_COMMAND, SCRIPT_DESC,
                             """""",
                             """""",
                             """""",
                             "term_command_cb", "")