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
Term = namedtuple("Term", ["screen", "stream", "fd"])
terms = {}

def term_render(buffer):
    term = terms[buffer]

    log(term)

    for i, line in enumerate(term.screen.display, 1):
        weechat.prnt_y(buffer, i - 1, line)

def buffer_input_cb(data, buffer, input_data):
    term = terms[buffer]

    log("in" + input_data)
    log(term)

    # weechat.hook_set(term.process, "stdin", input_data + "\n")
    # weechat.hook_set(term.process, "stdin_close", "")  # optional
    term.fd.write(input_data + "\n")
    term_render(buffer)

    return weechat.WEECHAT_RC_OK

def buffer_close_cb(data, buffer):
    return weechat.WEECHAT_RC_OK

def process_cb(data, command, return_code, out, err):
    term = terms[data]

    log(term)

    # if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR:
    #     error(command)
    # elif return_code >= 0:
    #     log("return {}".format(return_code))
    # elif out != "":
    #     log("out" + out)
    #     term.stream.feed(out)
    #     term_render(data)
    # elif err != "":
    #     log("err" + err)
    # else:
    #     error("shit")

    if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR:
        error(command)
        return weechat.WEECHAT_RC_OK
    if return_code >= 0:
        log("return {}".format(return_code))
    if out != "":
        log("out" + out)
        term.stream.feed(out)
        term_render(data)
    if err != "":
        log("err" + err)
        term.stream.feed(err)
        term_render(data)


    return weechat.WEECHAT_RC_OK


def fd_cb(data, fd):
    log("fd")
    return weechat.WEECHAT_RC_OK

def command_cb(data, buffer, args):
    """Handle command hook."""

    global buffer_i

    buffer = weechat.buffer_new("term.{}".format(buffer_i), "buffer_input_cb", "", "buffer_close_cb", "")
    buffer_i += 1
    weechat.buffer_set(buffer, "type", "free")
    weechat.buffer_set(buffer, "display", "1")

    screen = pyte.Screen(80, 24)
    screen.set_mode(pyte.modes.LNM)
    stream = pyte.ByteStream(screen)
    # process = weechat.hook_process_hashtable(args, {"stdin": "1"}, 0, "process_cb", buffer)
    # process = weechat.hook_process("ls", 5000, "process_cb", buffer)

    a = shlex.split(args)
    log(a)

    pid, fd = pty.fork()
    if pid == 0: # child
        os.execvpe(a[0], a, dict(TERM="linux", COLUMNS="80", LINES="24"))

    weechat.hook_fd(fd, 1, 0, 0, "fd_cb", buffer)

    log(pid)
    log(fd)

    fd = os.fdopen(fd, "rw")

    terms[buffer] = Term(screen=screen, stream=stream, fd=fd)

    fd.write("qwerty\n")

    return weechat.WEECHAT_RC_OK

if __name__ == "__main__" and IMPORT_OK:
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        weechat.hook_command(SCRIPT_COMMAND, SCRIPT_DESC,
                             """""",
                             """""",
                             """""",
                             "command_cb", "")


# example with an external command
def my_process_cb(data, command, return_code, out, err):
    if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR:
        weechat.prnt("", "Error with command '%s'" % command)
        return weechat.WEECHAT_RC_OK
    if return_code >= 0:
        weechat.prnt("", "return_code = %d" % return_code)
    if out != "":
        weechat.prnt("", "stdout: %s" % out)
    if err != "":
        weechat.prnt("", "stderr: %s" % err)
    return weechat.WEECHAT_RC_OK

# hook = weechat.hook_process("ls", 5000, "my_process_cb", "")
hook = weechat.hook_process_hashtable("tee test2.txt", {"stdin": "1"}, 20000, "my_process_cb", "")
weechat.hook_set(hook, "stdin", "data sent to stdin of child process")
weechat.hook_set(hook, "stdin_close", "")  # optional