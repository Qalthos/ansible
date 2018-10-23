# Copyright: (c) 2018, Ansible Project
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re
import json

from itertools import chain

from ansible.module_utils._text import to_text
from ansible.module_utils.common._collections_compat import Mapping
from ansible.module_utils.network.common.utils import to_list
from ansible.plugins.cliconf import CliconfBase


class Cliconf(CliconfBase):

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'edgeos'
        reply = self.get('show version')
        data = to_text(reply, errors='surrogate_or_strict').strip()

        match = re.search(r'Version:\s*v?(\S+)', data)
        if match:
            device_info['network_os_version'] = match.group(1)

        match = re.search(r'HW model:\s*(\S+)', data)
        if match:
            device_info['network_os_model'] = match.group(1)

        reply = self.get('show host name')
        device_info['network_os_hostname'] = to_text(reply, errors='surrogate_or_strict').strip()

        return device_info

    def get_config(self, flags=None, format=None):
        return self.send_command('show configuration commands')

    def edit_config(self, candidate=None, commit=True, replace=None, comment=None):
        resp = {}
        operations = self.get_device_operations()
        self.check_edit_config_capability(operations, candidate, commit, replace, comment)

        results = []
        requests = []
        self.send_command('configure')
        for cmd in to_list(candidate):
            if not isinstance(cmd, Mapping):
                cmd = {'command': cmd}

            results.append(self.send_command(**cmd))
            requests.append(cmd['command'])
        out = self.get('compare')
        out = to_text(out, errors='surrogate_or_strict')
        diff_config = out if not out.startswith('No changes') else None

        if diff_config:
            resp['diff'] = diff_config
            if commit:
                try:
                    self.commit(comment)
                except AnsibleConnectionFailure as e:
                    msg = 'commit failed: %s' % e.message
                    self.discard_changes()
                    raise AnsibleConnectionFailure(msg)
                else:
                    self.send_command('exit')
            else:
                self.discard_changes()
        else:
            self.send_command('exit')

        resp['response'] = results
        resp['request'] = requests
        return resp

    def get(self, command=None, prompt=None, answer=None, sendonly=False, output=None):
        return self.send_command(command, prompt=prompt, answer=answer, sendonly=sendonly)

    def commit(self, comment=None):
        if comment:
            command = 'commit comment "{0}"'.format(comment)
        else:
            command = 'commit'
        self.send_command(command)

    def discard_changes(self):
        self.send_command('exit discard')

    def get_device_operations(self):
        return {
            'supports_diff_replace': False,
            'supports_commit': True,
            'supports_rollback': False,
            'supports_defaults': False,
            'supports_onbox_diff': True,
            'supports_commit_comment': True,
            'supports_multiline_delimiter': False,
            'supports_diff_match': True,
            'supports_diff_ignore_lines': False,
            'supports_generate_diff': False,
            'supports_replace': False
        }

    def get_capabilities(self):
        result = {}
        result['rpc'] = self.get_base_rpc() + ['commit', 'discard_changes']
        result['network_api'] = 'cliconf'
        result['device_info'] = self.get_device_info()
        result['device_operations'] = self.get_device_operations()
        return json.dumps(result)
