from __future__ import print_function, unicode_literals

SCRIPT_NAME = "tee"
SCRIPT_AUTHOR = "Simmo Saan <simmo.saan@gmail.com>"
SCRIPT_VERSION = "0.1"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC = ""

SCRIPT_COMMAND = SCRIPT_NAME

IMPORT_OK = True

try:
    import weechat
except ImportError:
    print("This script must be run under WeeChat.")
    print("Get WeeChat now at: http://www.weechat.org/")
    IMPORT_OK = False


# example with an external command
def my_process_cb(data, command, return_code, out, err):
    if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR:
        weechat.prnt("", "Error with command '%s'" % command)
        # return weechat.WEECHAT_RC_OK
    if return_code >= 0:
        weechat.prnt("", "return_code = %d" % return_code)
    if out != "":
        weechat.prnt("", "stdout: %s" % out)
    if err != "":
        weechat.prnt("", "stderr: %s" % err)
    return weechat.WEECHAT_RC_OK


if __name__ == "__main__" and IMPORT_OK:
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        hook = weechat.hook_process_hashtable("tee test2.txt", {"stdin": "1", "buffer_flush": "1"}, 0, "my_process_cb", "")
        weechat.hook_set(hook, "stdin", "data sent to stdin of child process\n")
        # weechat.hook_set(hook, "stdin_close", "")  # optional
