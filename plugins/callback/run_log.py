"""Callback plugin aslib.infra.run_log: each playbook run in a log file of its own."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
name: run_log
type: notification
short_description: Write each playbook run to a log file of its own
description:
  - Writes what a playbook run does to C(<log_dir>/<playbook>-<UTC time>.log), for example
    C(logs/deploy-20261003T081502Z.log) - the plays, the tasks, each host's result, the full result of
    every failure, the output of debug tasks and the recap.
  - Results that Ansible hides (C(no_log)) stay hidden. Only the owner can read the files, as failures
    may show settings.
  - Enable it in ansible.cfg with C(callbacks_enabled = aslib.infra.run_log), as the ansible.cfg that
    aslib.infra.node_setup writes does.
requirements:
  - Enabled in ansible.cfg (callbacks_enabled) or with ANSIBLE_CALLBACKS_ENABLED.
options:
  log_dir:
    description: The directory for the log files, relative to the directory ansible-playbook runs in.
      Created when missing.
    type: path
    default: logs
    ini:
      - section: callback_run_log
        key: log_dir
    env:
      - name: ANSIBLE_RUN_LOG_DIR
"""

import os
from datetime import datetime, timezone

from ansible.plugins.callback import CallbackBase
from ansible.release import __version__ as ansible_version

UTC = timezone.utc
DEBUG_ACTIONS = ("debug", "ansible.builtin.debug", "ansible.legacy.debug")


def _parts(result):
    """The host, task and result dictionary of a task result.

    ansible-core 2.19 added public names for them; older versions only have the
    private ones, which newer versions deprecate.
    """
    if hasattr(result, "result"):
        return result.host, result.task, result.result
    return result._host, result._task, result._result


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "notification"
    CALLBACK_NAME = "aslib.infra.run_log"
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display=display)
        self._log = None

    # Writing

    def _write(self, line=""):
        if self._log:
            self._log.write(line + "\n")
            self._log.flush()

    def _open(self, playbook_path):
        self._close()
        name = os.path.splitext(os.path.basename(playbook_path))[0]
        started = datetime.now(UTC)
        directory = self.get_option("log_dir")
        if not os.path.isdir(directory):
            os.makedirs(directory)
        path = os.path.join(directory, "%s-%s.log" % (name, started.strftime("%Y%m%dT%H%M%SZ")))
        # Only the owner may read it; appending keeps two runs within a second.
        self._log = os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a")
        self._write("# ansible-playbook %s, ansible-core %s, started %s" % (
            playbook_path, ansible_version, started.strftime("%Y-%m-%d %H:%M:%S UTC")))

    def _close(self):
        if self._log:
            self._log.close()
            self._log = None

    def _result_line(self, status, result, item=False, details=False):
        host, task, res = _parts(result)
        line = "%s: [%s]" % (status, self.host_label(result))
        if item:
            line += " => (item=%s)" % self._get_item_label(res)
        if details:
            line += " => %s" % self._dump_results(res, indent=4)
        self._write(line)

    # Playbook, plays and tasks

    def v2_playbook_on_start(self, playbook):
        self._open(playbook._file_name)

    def v2_playbook_on_play_start(self, play):
        self._write()
        self._write("PLAY [%s]" % (play.get_name().strip() or "unnamed play"))

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._write()
        self._write("TASK [%s]" % task.get_name().strip())

    def v2_playbook_on_handler_task_start(self, task):
        self._write()
        self._write("RUNNING HANDLER [%s]" % task.get_name().strip())

    def v2_playbook_on_no_hosts_matched(self):
        self._write("skipping: no hosts matched")

    def v2_playbook_on_stats(self, stats):
        self._write()
        self._write("PLAY RECAP")
        for host in sorted(stats.processed.keys()):
            summary = stats.summarize(host)
            self._write("%s : ok=%d changed=%d unreachable=%d failed=%d skipped=%d rescued=%d ignored=%d" % (
                host, summary["ok"], summary["changed"], summary["unreachable"], summary["failures"],
                summary["skipped"], summary["rescued"], summary["ignored"]))
        self._write()
        self._write("# finished %s" % datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))
        self._close()

    # Results, as the default output shows them; failures and debug output in full

    def v2_runner_on_ok(self, result):
        host, task, res = _parts(result)
        if task.loop and "results" in res:
            return  # each item has been written already
        status = "changed" if res.get("changed") else "ok"
        self._result_line(status, result, details=task.action in DEBUG_ACTIONS)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host, task, res = _parts(result)
        # A loop's failed items have been written already.
        self._result_line("fatal", result, details=not (task.loop and "results" in res))
        if ignore_errors:
            self._write("...ignoring")

    def v2_runner_on_skipped(self, result):
        host, task, res = _parts(result)
        if task.loop and "results" in res:
            return
        self._result_line("skipping", result)

    def v2_runner_on_unreachable(self, result):
        self._result_line("unreachable", result, details=True)

    def v2_runner_item_on_ok(self, result):
        host, task, res = _parts(result)
        status = "changed" if res.get("changed") else "ok"
        self._result_line(status, result, item=True, details=task.action in DEBUG_ACTIONS)

    def v2_runner_item_on_failed(self, result):
        self._result_line("failed", result, item=True, details=True)

    def v2_runner_item_on_skipped(self, result):
        self._result_line("skipping", result, item=True)

    def v2_runner_retry(self, result):
        host, task, res = _parts(result)
        self._write("FAILED - RETRYING: [%s]: %s (%d retries left)." % (
            self.host_label(result), task.get_name().strip(), res["retries"] - res["attempts"]))
