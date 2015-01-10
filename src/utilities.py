# encoding: utf-8

from __future__ import unicode_literals
from lpvaultmanager import DEFAULT_LPASS_PATH
from workflow import MATCH_ALL, MATCH_ALLCHARS
from workflow.background import run_in_background, is_running

import lpvaultmanager as lpvm
import subprocess


####################################################################
# Alfred Commands
####################################################################
ALFRED_AS_LOGIN = 'tell application "Alfred 2" to search ">{} login {} && exit"'

####################################################################
# Browsers
####################################################################
BROWSER_CHROME = 1
BROWSER_FIREFOX = 2
BROWSER_SAFARI = 3


class LpvmUtilitiesError(Exception):
    """
    Raised by method :meth:`LpvmUtilities.__init__` when some generic error
    occurs.
    """


class NotLoggedInError(LpvmUtilitiesError):
    """
    Raised by method :meth:`LastPassVaultManager.__init__` when lastpass-cli
    isn't logged into LastPass.
    """


class LpvmUtilities:

    def __init__(self, wf):
        """
        Initialize an instance of the class (primarily so that we can use the
        same Workflow() and pass it aroud once).
        """
        self.wf = wf
        self.log = wf.logger
        self.set_config_defaults()

        self.lpvm = lpvm.LastPassVaultManager(wf.settings['lastpass']['path'])

    def copy_value_to_clipboard(self, string):
        """
        Copies a string to the OS X clipboard.
        """
        process = subprocess.Popen(
            'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
        process.communicate(string.encode('utf-8'))

    def download_data(self):
        """
        Download data from LastPass and coerce it to Unicode:
        """
        try:
            data = self.lpvm.download_data()
            self.log.debug('Downloaded data: {}'.format(data))
            return [{k: self.wf.decode(v) for k, v in i.iteritems()}
                    for i in data]
        except lpvm.LastPassVaultManagerError, e:
            self.log.error('There was an issue with LastPass: {}'.format(e))
            return []

    def generate_passwords(self):
        """
        Generates a selection of passwords (based on the requested settings) and
        returns them.
        """
        pw_len = self.wf.settings['passwords']['length']
        pw_num = self.wf.settings['passwords']['number']
        pw_uppercase = self.wf.settings['passwords']['use_uppercase']
        pw_lowercase = self.wf.settings['passwords']['use_lowercase']
        pw_digits = self.wf.settings['passwords']['use_digits']
        pw_symbols = self.wf.settings['passwords']['use_symbols']
        pw_ambiguous = self.wf.settings['passwords']['avoid_ambigious']

        self.log.debug('Password generation settings: {}'.format(
            self.wf.settings['passwords'])
        )

        return self.lpvm.generate_passwords(pw_num, pw_len, pw_uppercase,
                                            pw_lowercase, pw_digits, pw_symbols,
                                            pw_ambiguous)

    def get_item_details(self, hostname):
        """
        Returns all the fields stored by LastPass for a particular hostname.
        """
        try:
            details = self.lpvm.get_details(hostname)
            return [self.wf.decode(i) for i in details][1:]
        except lpvm.HostnameNotFoundError, e:
            self.log.error('Could not find hostname: "{}".'.format(hostname))
            return None
        except lpvm.MultipleHostnamesError, e:
            self.log.error('Multiple matches for "{}".'.format(hostname))
            return None
        except lpvm.LastPassVaultManagerError, e:
            self.log.error('There was an issue with LastPass: {}'.format(e))
            return None

    def get_value_from_field(self, hostname, field_name):
        """
        Retrieves a specific field for a specific hostname from the LastPass
        vault.
        """
        try:
            return self.wf.decode(
                self.lpvm.get_field_value(hostname, field_name)
            )
        except lpvm.HostnameNotFoundError, e:
            self.log.error('Hostname not found: {}'.format(hostname))
            return None
        except lpvm.MultipleHostnamesError, e:
            self.log.error('Multiple matches for "{}".'.format(hostname))
            return None
        except lpvm.LastPassVaultManagerError, e:
            self.log.error('There was an issue with LastPass: {}'.format(e))
            return None

    def login_to_lastpass(self):
        """
        Uses a special Alfred search to initiate a LastPass login.
        """
        cmd = ALFRED_AS_LOGIN.format(
            self.wf.settings['lastpass']['path'],
            self.wf.settings['lastpass']['username'])

        self.log.debug('Executing Applescript: {}'.format(cmd))
        subprocess.call([
            'osascript',
            '-e',
            cmd
        ])

    def logout_from_lastpass(self):
        """
        Logs the user out from LastPass.
        """
        subprocess.call(
            [self.wf.settings['lastpass']['path'],
             'logout',
             '--force']
        )

    def print_utf8_error(self, string):
        """
        Prints a UTF-8 encoded string with some standard error text.
        """
        self.print_utf8(string + ' Check the debug log for more info.')

    def print_utf8(self, string):
        """
        Prints a UTF-8 encoded string (necessary for OS X).
        """
        print(string.encode('utf-8'))

    def search_item_fields(self, item):
        """
        The function used to search individual lastpass vault items.
        """
        elements = []
        elements.append(item['hostname'])
        elements.append(item['url'])
        return ' '.join(elements)

    def search_vault_for_query(self, query):
        """
        Search the LastPass vault for an optional passed query.
        """
        results = self.wf.cached_data('vault_items', None, max_age=0)

        # Start updae script if cache is too old or doesn't exist:
        age = int(self.wf.settings['general']['cache_bust'])
        if not self.wf.cached_data_fresh('vault_items', age):
            cmd = ['python', self.wf.workflowfile('update.py')]
            run_in_background('update', cmd)

        # Notify the user if the cache is being updated:
        if is_running('update'):
            self.wf.add_item(
                'Getting new data from LastPass.',
                'Wait a few moments and then continue your query.',
                valid=False,
                icon='icons/loading.png'
            )

        # If a query is passed, filter the results:
        if query and results:
            results = self.wf.filter(
                query,
                results,
                self.search_item_fields,
                match_on=MATCH_ALL ^ MATCH_ALLCHARS
            )

        self.log.debug('Search results: {}'.format(results))
        return results

    def set_config_defaults(self):
        """
        Configure some default options (unless they already exist).
        """
        self.wf.settings.setdefault('general', {})
        self.wf.settings['general'].setdefault('cache_bust', 300)
        self.wf.settings['general'].setdefault('browser', BROWSER_CHROME)

        self.wf.settings.setdefault('lastpass', {})
        self.wf.settings['lastpass'].setdefault('path', DEFAULT_LPASS_PATH)
        self.wf.settings['lastpass'].setdefault('username', '')

        self.wf.settings.setdefault('passwords', {})
        self.wf.settings['passwords'].setdefault('length', 20)
        self.wf.settings['passwords'].setdefault('number', 10)
        self.wf.settings['passwords'].setdefault('use_uppercase', True)
        self.wf.settings['passwords'].setdefault('use_lowercase', True)
        self.wf.settings['passwords'].setdefault('use_digits', True)
        self.wf.settings['passwords'].setdefault('use_symbols', True)
        self.wf.settings['passwords'].setdefault('avoid_ambigious', True)

        self.wf.settings.save()
