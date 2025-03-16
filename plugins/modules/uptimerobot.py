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

API_ACTIONS = dict(
    status='getMonitors?',
    editMonitor='editMonitor?'
)

API_FORMAT = 'json'
API_NOJSONCALLBACK = 1
CHANGED_STATE = False
SUPPORTS_CHECK_MODE = False


class uptimeRobot(object):
    
    def __init__(self, module, params):
        
        # initialize class
        self.changed = False

        self.module = module
        self.params = params

        self.ur_types = {
            'http': 1,
            'keyword': 2,
            'ping': 3,
            'port': 4,
        }
        self.ur_statuses = {
            'present': 1,
            'paused': 0,
            'absent': 0,
        }

    def _up_get_monitors(self):
        
        # 
        
        headers = {
                    'content-type': "application/x-www-form-urlencoded",
                    'cache-control': "no-cache"
                  }
        #data = "api_key="+self.apikey+"&format=json&logs=1"
        data = {
            'api_key': self.params['apikey'],
            'format': 'json',
            'logs': '1',
        }

        resp, info = fetch_url(self.module,
                               API_BASE+'getMonitors',
                               headers=headers,
                               data=urlencode(data),
                               method='POST')
        
        return resp
    

    def _up_edit_monitor(self):

        # This method allows for editing of an existing monitor.

        headers = {
                    'content-type': "application/x-www-form-urlencoded",
                    'cache-control': "no-cache"
                  }
        data = {
            'api_key': self.params['apikey'],
            'format': 'json',
        }
        payload = "api_key=enterYourAPIKeyHere&format=json&id=777712827&friendly_name=newFriendlyName"

        # Add monitor specific data
        data['id'] = self.current_monitor['id'] # Required
        data['friendly_name'] = self.params['name']
        data['status'] = self.ur_statuses[self.params['state']]

        resp, info = fetch_url(self.module,
                               API_BASE+'editMonitor',
                               headers=headers,
                               data=urlencode(data),
                               method='POST')

        self.changed = True


    def _up_new_monitor(self):

        # Create a new monitor

        headers = {
                    'content-type': "application/x-www-form-urlencoded",
                    'cache-control': "no-cache"
                  }
        data = {
            'api_key': self.apikey,
            'format': 'json',
        }

        # Add monitor specific data
        data['friendly_name'] = self.params['name']
        data['url'] = self.params['url']
        data['type'] = self.ur_types[self.params['type']] # <- This resolves the type id
        #data['sub_type'] = self.params['sub_type'] if 'sub_type' in self.params else None
        #data['port'] = self.params['port'] if 'port' in self.params else None
        #data['keyword_type'] = self.params['keyword_type'] if 'keyword_type' in self.params else None
        #data['keyword_value'] = self.params['keyword_value'] if 'keyword_value' in self.params else None
        # TODO: add support for more data

        resp, info = fetch_url(self.module,
                               API_BASE+'newMonitor',
                               headers=headers,
                               data=urlencode(data),
                               method='POST')
        
        return resp


    def _find_monitor(self):

        # This will get a list of all monitors and then parse the data into the class instance object.
    
        current_monitors = self._up_get_monitors()
        data = json.loads(current_monitors.read().decode('utf-8'))

        # Loop through the list of monitors and check unique criteria
        self.matched_monitors = [
            monitor for monitor in data['monitors']
            if monitor['type'] == self.ur_types[self.params['type']] and monitor['url'] == self.params['url']
        ]

        #print(json.dumps(self.matched_monitors))
        self.current_monitor = self.matched_monitors[0]
        
        

        #monitors = list(filter(lambda monitor: monitor['friendly_name'] == friendly_name, data['monitors']))
        #self.current_monitor = monitors[0] if monitors else None
        

    def ensure_monitor(self):
        
        # This module will allow you to ensure a specific monitor
        
        # If a monitor already exists, then get that data
        self._find_monitor()

        #
        # - CONDITIONS FOR CREATING A NEW MONITOR -
        #
        # Since "type" cannot be edited on a monitor, we need to create a new monitor if the type does in dead change.
        if len(self.matched_monitors) == 0:
            resp = self._up_new_monitor()
            if resp.status == '200':
                self.changed = True
                return json.dumps({'changed': self.changed})
        #check_diff_new = [
        #    {
        #        'proposed_monitor': self.ur_types[self.type],
        #        'current_monitor': self.current_monitor['type'],
        #    },
        #]
        #for diff in check_diff_new:
        #    if diff['proposed_monitor'] != diff['current_monitor']:
        #        if self._up_new_monitor().status == '200':
        #            self.changed = True



        #
        # - CONDITIONS FOR EDITING AN EXISTING MONITOR -
        #
        check_diff_edit = [
            {
                'proposed_monitor': self.ur_statuses[self.params['state']],
                'current_monitor': self.current_monitor['status'],
            },
        ]
        for diff in check_diff_edit:

            if diff['proposed_monitor'] != diff['current_monitor']:

                # The proposed monitor is different and needs to be altered.
                self._up_edit_monitor()

        return json.dumps({'changed': self.changed})



        


def checkID(module, params):

    data = urlencode(params)
    full_uri = API_BASE + API_ACTIONS['status'] + data
    req, info = fetch_url(module, full_uri)
    result = to_text(req.read())
    jsonresult = json.loads(result)
    req.close()
    return jsonresult


def startMonitor(module, params):

    params['monitorStatus'] = 1
    data = urlencode(params)
    full_uri = API_BASE + API_ACTIONS['editMonitor'] + data
    req, info = fetch_url(module, full_uri)
    result = to_text(req.read())
    jsonresult = json.loads(result)
    req.close()
    return jsonresult['stat']


def pauseMonitor(module, params):

    params['monitorStatus'] = 0
    data = urlencode(params)
    full_uri = API_BASE + API_ACTIONS['editMonitor'] + data
    req, info = fetch_url(module, full_uri)
    result = to_text(req.read())
    jsonresult = json.loads(result)
    req.close()
    return jsonresult['stat']


def main():

    module = AnsibleModule(
        argument_spec=dict(
            apikey=dict(required=True, type=str, no_log=True),
            state=dict(required=False, type=str, default='present', choices=['present', 'absent']),
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
    resp = uR._up_get_monitors()

    ur_return = uR.ensure_monitor()

    print(ur_return)

    module.exit_json(changed=True, **ur_return)

    #check_result = checkID(module, params)
#
    #if check_result['stat'] != "ok":
    #    module.fail_json(
    #        msg="failed",
    #        result=check_result['message']
    #    )
#
    #if module.params['state'] == 'started':
    #    monitor_result = startMonitor(module, params)
    #else:
    #    monitor_result = pauseMonitor(module, params)
#
    #module.exit_json(
    #    msg="success",
    #    result=monitor_result
    #)


if __name__ == '__main__':
    main()
