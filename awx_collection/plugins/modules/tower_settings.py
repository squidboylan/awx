#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2018, Nikhil Jain <nikjain@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: tower_settings
author: "Nikhil Jain (@jainnikhil30)"
version_added: "2.7"
short_description: Modify Ansible Tower settings.
description:
    - Modify Ansible Tower settings. See
      U(https://www.ansible.com/tower) for an overview.
options:
    name:
      description:
        - Name of setting to modify
      required: False
      type: str
    value:
      description:
        - Value to be modified for given setting.
      required: False
      type: str
    settings:
      description:
        - A data structure to be sent into the settings endpoint
      required: False
      type: dict
    tower_oauthtoken:
      description:
        - The Tower OAuth token to use.
      required: False
      type: str
extends_documentation_fragment: awx.awx.auth
'''

RETURN = ''' # '''

EXAMPLES = '''
- name: Set the value of AWX_PROOT_BASE_PATH
  tower_settings:
    name: AWX_PROOT_BASE_PATH
    value: "/tmp"
  register: testing_settings

- name: Set the value of AWX_PROOT_SHOW_PATHS
  tower_settings:
    name: "AWX_PROOT_SHOW_PATHS"
    value: "'/var/lib/awx/projects/', '/tmp'"
  register: testing_settings

- name: Set the LDAP Auth Bind Password
  tower_settings:
    name: "AUTH_LDAP_BIND_PASSWORD"
    value: "Password"
  no_log: true

- name: Set all the LDAP Auth Bind Params
  tower_settings:
    settings:
      AUTH_LDAP_BIND_PASSWORD: "password"
      AUTH_LDAP_USER_ATTR_MAP:
        email: "mail"
        first_name: "givenName"
        last_name: "surname"
'''

from ..module_utils.tower_api import TowerModule
from json import loads
import re


def main():
    # Any additional arguments that are not fields of the item can be added here
    argument_spec = dict(
        name=dict(required=False),
        value=dict(required=False),
        settings=dict(required=False, type='dict'),
    )

    # Create a module for ourselves
    module = TowerModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['name', 'settings']],
        mutually_exclusive=[['name', 'settings']],
        required_if=[['name', 'present', ['value']]]
    )

    # Extract our parameters
    name = module.params.get('name')
    value = module.params.get('value')
    new_settings = module.params.get('settings')

    # If we were given a name/value pair we will just make settings out of that and proceed normally
    if new_settings is None:
        new_value = value
        try:
            new_value = loads(value)
        except ValueError:
            # JSONDecodeError only available on Python 3.5+
            # Attempt to deal with old tower_cli array types
            if ',' in value:
                new_value = re.split(r",\s+", new_value)

        new_settings = {name: new_value}

    # Load the existing settings
    existing_settings = module.get_endpoint('settings/all')['json']

    # Begin a json response
    json_response = {'changed': False, 'old_values': {}}

    # Check any of the settings to see if anything needs to be updated
    needs_update = False
    for a_setting in new_settings:
        if a_setting not in existing_settings or existing_settings[a_setting] != new_settings[a_setting]:
            # At least one thing is different so we need to patch
            needs_update = True
            json_response['old_values'][a_setting] = existing_settings[a_setting]

    # If nothing needs an update we can simply exit with the response (as not changed)
    if not needs_update:
        module.exit_json(**json_response)

    # Make the call to update the settings
    response = module.patch_endpoint('settings/all', **{'data': new_settings})

    if response['status_code'] == 200:
        # Set the changed response to True
        json_response['changed'] = True

        # To deal with the old style values we need to return 'value' in the response
        new_values = {}
        for a_setting in new_settings:
            new_values[a_setting] = response['json'][a_setting]

        # If we were using a name we will just add a value of a string, otherwise we will return an array in values
        if name is not None:
            json_response['value'] = new_values[name]
        else:
            json_response['values'] = new_values

        module.exit_json(**json_response)
    elif 'json' in response and '__all__' in response['json']:
        module.fail_json(msg=response['json']['__all__'])
    else:
        module.fail_json(**{'msg': "Unable to update settings, see response", 'response': response})


if __name__ == '__main__':
    main()
