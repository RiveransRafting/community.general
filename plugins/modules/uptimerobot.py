#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function
__metaclass__ = type


# TODO: re-write documentation
DOCUMENTATION = r"""
module: uptimerobot
short_description: Pause and start Uptime Robot monitoring
description:
  - This module lets you start and pause Uptime Robot Monitoring.
author: "Nate Kingsley (@nate-kingsley)"
requirements:
  - Valid Uptime Robot API Key
extends_documentation_fragment:
  - community.general.attributes
attributes:
  check_mode:
    support: none
  diff_mode:
    support: none
options:
  state:
    type: str
    description:
      - Define whether or not the monitor should be running or paused.
    required: true
    choices: ["started", "paused"]
  monitorid:
    type: str
    description:
      - ID of the monitor to check.
    required: true
  apikey:
    type: str
    description:
      - Uptime Robot API key.
    required: true
notes:
  - Support for adding and removing monitors and alert contacts has not yet been implemented.
"""

# TODO: re-write examples
EXAMPLES = r"""
- name: Pause the monitor with an ID of 12345
  community.general.uptimerobot:
    monitorid: 12345
    apikey: 12345-1234512345
    state: paused

- name: Start the monitor with an ID of 12345
  community.general.uptimerobot:
    monitorid: 12345
    apikey: 12345-1234512345
    state: started
"""

# TODO: write a section for responses

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlencode
from ansible.module_utils.urls import fetch_url
from ansible.module_utils.common.text.converters import to_text


API_BASE = "https://api.uptimerobot.com/v2/"

API_FORMAT = 'json'
API_NOJSONCALLBACK = 1
CHANGED_STATE = False
SUPPORTS_CHECK_MODE = False


class uptimeRobot(object):
    
    def __init__(self, module, params):
        
        # initialize class
        self.changed = False
        self.failed = False

        self.module = module
        self.params = params

        self.ur_types = {
            'http': 1,
            'keyword': 2,
            'ping': 3,
            'port': 4,
        }


    def _return(self):

        # This data will be returned

        data = {}
        data['changed'] = self.changed
        if hasattr(self, 'msg'): data['msg'] = self.msg
        if hasattr(self, 'failed'): data['failed'] = self.failed

        return data
    

    def _up_make_api_call(self, url, data):

        # Status code for rate limit: 429
        headers = {
                    'content-type': "application/x-www-form-urlencoded",
                    'cache-control': "no-cache"
                  }

        resp, info = fetch_url(self.module,
                               url,
                               headers=headers,
                               data=urlencode(data),
                               method='POST')
        
        # Check HTTP status
        if resp.status != 200:
            self.failed = True
            self.msg = f'HTTP Status {resp.status} - {resp.reason}'
        
        return resp, info


    def _up_get_monitors(self):
        
        # Used to fetch a list of all monitors
        
        data = {
            'api_key': self.params['apikey'],
            'format': 'json',
            'logs': '1',
        }

        resp, info = self._up_make_api_call(API_BASE+'getMonitors', data)
        
        return resp
    

    def _up_edit_monitor(self):

        # This method allows for editing of an existing monitor.

        data = {
            'api_key': self.params['apikey'],
            'format': 'json',
        }

        # Add monitor specific data
        data['id'] = self.current_monitor['id'] # Required
        data['friendly_name'] = self.params['name']
        data['status'] = 1 if self.params['state'] == 'present' else 0

        # Send REST request
        resp, info = self._up_make_api_call(API_BASE+'editMonitor', data)

        self.changed = True
        self.msg = 'Existing monitor updated.'

        return resp


    def _up_new_monitor(self):

        # Create a new monitor

        data = {
            'api_key': self.params['apikey'],
            'format': 'json',
        }

        # Add monitor specific data
        data['friendly_name'] = self.params['name']
        data['url'] = self.params['url']
        data['type'] = self.ur_types[self.params['type']] # <- This resolves the type id
        # TODO: add support for more data

        resp, info = self._up_make_api_call(API_BASE+'newMonitor', data)
        
        self.changed = True
        self.msg = 'New monitor created.'
        
        return resp
    
    
    def _up_delete_monitor(self):

        # Delete a monitor

        data = {
            'api_key': self.params['apikey'],
            'id': self.current_monitor['id'], # Required
            'format': 'json',
        }

        resp, info = self._up_make_api_call(API_BASE+'deleteMonitor', data)
        
        self.changed = True
        self.msg = 'Monitor deleted.'

        return resp


    def _find_monitor(self):

        # This will get a list of all monitors and then parse the data into the class instance object.
    
        current_monitors = self._up_get_monitors()
        if self.failed: return
        data = json.loads(current_monitors.read().decode('utf-8'))

        # Loop through the list of monitors and check unique criteria
        self.matched_monitors = [
            monitor for monitor in data['monitors']
            if monitor['type'] == self.ur_types[self.params['type']] and monitor['url'] == self.params['url']
        ]

        if len(self.matched_monitors) > 0:
            self.current_monitor = self.matched_monitors[0]


    def ensure_monitor(self):
        
        # This module will allow you to ensure a specific monitor
        
        # If a monitor already exists, then get that data
        self._find_monitor()

        if self.failed: return self._return()

        if self.params['state'] == 'present':

            #
            # - CONDITIONS FOR CREATING A NEW MONITOR -
            #
            # Since "type" cannot be edited on a monitor, we need to create a new monitor if the type does in dead change.
            if len(self.matched_monitors) == 0:
                resp = self._up_new_monitor()
                if resp.status == '200':
                    self.changed = True
                    return self._return()

            #
            # - CONDITIONS FOR EDITING AN EXISTING MONITOR -
            #
            if self.current_monitor['status'] == 0:
                self._up_edit_monitor()
        
        elif self.params['state'] == 'paused':

            #
            # - CONDITIONS FOR CREATING A NEW MONITOR -
            #
            # Since "type" cannot be edited on a monitor, we need to create a new monitor if the type does in dead change.
            if len(self.matched_monitors) == 0:
                resp = self._up_new_monitor()
                if resp.status == '200':
                    self.changed = True
                    return self._return()

            #
            # - CONDITIONS FOR EDITING AN EXISTING MONITOR -
            #
            if self.current_monitor['status'] != 0:
                self._up_edit_monitor()
        
        elif len(self.matched_monitors) != 0:
            
            self._up_delete_monitor()

        return self._return()



        

def main():

    module = AnsibleModule(
        argument_spec=dict(
            apikey=dict(required=True, type=str, no_log=True),
            state=dict(required=False, type=str, default='present', choices=['present', 'absent', 'paused']),
            name=dict(required=True, type=str),
            type=dict(required=False, type=str, default='http', choices=['http', 'keyword', 'ping', 'port']),
            url=dict(required=True, type=str),
            sub_type=dict(required=False),
            port=dict(required=False),
        ),
        required_if=[
          ('type', 'keyword', ('keyword_type', 'keyword_value'), False),
          ('type', 'port', ('sub_type', 'port'), False),
        ],
        supports_check_mode=SUPPORTS_CHECK_MODE,
    )

    params = dict(
        apikey=module.params['apikey'],
        state=module.params['state'],
        name=module.params['name'],
        type=module.params['type'],
        url=module.params['url'],
        sub_type=module.params['sub_type'],
        port=module.params['port'],
        format=API_FORMAT,
        noJsonCallback=API_NOJSONCALLBACK,
    )

    uR = uptimeRobot(module, params)
    ur_return = uR.ensure_monitor()

    module.exit_json(**ur_return)



if __name__ == '__main__':
    main()
