#!/usr/bin/python
#
# (c) 2015 Peter Sprygada, <psprygada@ansible.com>
#
# Copyright (c) 2016 Dell Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '1.0'}

DOCUMENTATION = """
---
module: dellos9_command
version_added: "2.2"
author: "Dhivya P (@dhivyap)"
short_description: Run commands on remote devices running Dell OS9
description:
  - Sends arbitrary commands to a Dell OS9 node and returns the results
    read from the device. This  module includes an
    argument that will cause the module to wait for a specific condition
    before returning or timing out if the condition is not met.
  - This module does not support running commands in configuration mode.
    Please use M(dellos9_config) to configure Dell OS9 devices.
extends_documentation_fragment: dellos9
options:
  commands:
    description:
      - List of commands to send to the remote dellos9 device over the
        configured provider. The resulting output from the command
        is returned. If the I(wait_for) argument is provided, the
        module is not returned until the condition is satisfied or
        the number of retries has expired.
    required: true
  wait_for:
    description:
      - List of conditions to evaluate against the output of the
        command. The task will wait for each condition to be true
        before moving forward. If the conditional is not true
        within the configured number of I(retries), the task fails.
        See examples.
    required: false
    default: null
  retries:
    description:
      - Specifies the number of retries a command should be tried
        before it is considered failed. The command is run on the
        target device every retry and evaluated against the
        I(wait_for) conditions.
    required: false
    default: 10
  interval:
    description:
      - Configures the interval in seconds to wait between retries
        of the command. If the command does not pass the specified
        conditions, the interval indicates how long to wait before
        trying the command again.
    required: false
    default: 1

notes:
  - This module requires Dell OS9 version 9.10.0.1P13 or above.

  - This module requires to increase the ssh connection rate limit.
    Use the following command I(ip ssh connection-rate-limit 60)
    to configure the same. This can be done via M(dellos9_config) module
    as well.

"""

EXAMPLES = """
# Note: examples below use the following provider dict to handle
#       transport and authentication to the node.
vars:
  cli:
    host: "{{ inventory_hostname }}"
    username: admin
    password: admin
    transport: cli

tasks:
  - name: run show version on remote devices
    dellos9_command:
      commands: show version
      provider: "{{ cli }}"

  - name: run show version and check to see if output contains OS9
    dellos9_command:
      commands: show version
      wait_for: result[0] contains OS9
      provider: "{{ cli }}"

  - name: run multiple commands on remote nodes
    dellos9_command:
      commands:
        - show version
        - show interfaces
      provider: "{{ cli }}"

  - name: run multiple commands and evaluate the output
    dellos9_command:
      commands:
        - show version
        - show interfaces
      wait_for:
        - result[0] contains OS9
        - result[1] contains Loopback
      provider: "{{ cli }}"
"""

RETURN = """
stdout:
  description: The set of responses from the commands
  returned: always
  type: list
  sample: ['...', '...']

stdout_lines:
  description: The value of stdout split into a list
  returned: always
  type: list
  sample: [['...', '...'], ['...'], ['...']]

failed_conditions:
  description: The list of conditionals that have failed
  returned: failed
  type: list
  sample: ['...', '...']

warnings:
  description: The list of warnings (if any) generated by module based on arguments
  returned: always
  type: list
  sample: ['...', '...']
"""

from ansible.module_utils.basic import get_exception
from ansible.module_utils.netcli import CommandRunner, FailedConditionsError
from ansible.module_utils.network import NetworkModule, NetworkError
import ansible.module_utils.dellos9


def to_lines(stdout):
    for item in stdout:
        if isinstance(item, basestring):
            item = str(item).split('\n')
        yield item


def main():
    spec = dict(
        commands=dict(type='list', required=True),
        wait_for=dict(type='list'),
        retries=dict(default=10, type='int'),
        interval=dict(default=1, type='int')
    )

    module = NetworkModule(argument_spec=spec,
                           connect_on_load=False,
                           supports_check_mode=True)

    commands = module.params['commands']
    conditionals = module.params['wait_for'] or list()

    warnings = list()

    runner = CommandRunner(module)

    for cmd in commands:
        if module.check_mode and not cmd.startswith('show'):
            warnings.append('only show commands are supported when using '
                            'check mode, not executing `%s`' % cmd)
        else:
            if cmd.startswith('conf'):
                module.fail_json(msg='dellos9_command does not support running '
                                     'config mode commands.  Please use '
                                     'dellos9_config instead')
            runner.add_command(cmd)

    for item in conditionals:
        runner.add_conditional(item)

    runner.retries = module.params['retries']
    runner.interval = module.params['interval']

    try:
        runner.run()
    except FailedConditionsError:
        exc = get_exception()
        module.fail_json(msg=str(exc), failed_conditions=exc.failed_conditions)
    except NetworkError:
        exc = get_exception()
        module.fail_json(msg=str(exc))

    result = dict(changed=False)

    result['stdout'] = list()
    for cmd in commands:
        try:
            output = runner.get_command(cmd)
        except ValueError:
            output = 'command not executed due to check_mode, see warnings'
        result['stdout'].append(output)

    result['warnings'] = warnings
    result['stdout_lines'] = list(to_lines(result['stdout']))

    module.exit_json(**result)


if __name__ == '__main__':
    main()
