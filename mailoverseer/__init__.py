import imaplib
import logging
import re
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime, timedelta

from .__version__ import __version__

__all__ = ['__version__', 'MailOverseer']


class MailOverseer:

    def __init__(self, config):
        self._running = False

        self._connection = None
        self._server = config.get('imap', 'server')
        self._login = config.get('imap', 'login')
        self._password = config.get('imap', 'password')

        self._last_unseen_stats = None
        self._last_unseen_count = None
        self._unseen_stats_delta = timedelta(seconds=int(config.get('overseer', 'unseen_stats_delay', fallback=60)))

        self._unseen_command = config.get('overseer', 'unseen_command', fallback=None)
        self._mailbox_blacklist = config.get('overseer', 'mailbox_blacklist', fallback=None)
        if self._mailbox_blacklist and isinstance(self._mailbox_blacklist, str):
            self._mailbox_blacklist = [mb.strip() for mb in self._mailbox_blacklist.split(';')]

        self._logger = logging.getLogger()
        self._logger.setLevel(logging.DEBUG)
        log_handler = logging.StreamHandler(sys.stdout)
        log_handler.setLevel(getattr(logging, config.get('overseer', 'log_level', fallback='DEBUG')))
        log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self._logger.addHandler(log_handler)

        self._mailboxes = []

        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGQUIT, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGABRT, self.stop)

    def run(self):
        if self._running:
            return

        self._running = True
        while self._running:
            try:
                self._tick()
            except imaplib.IMAP4.error:
                self._logger.exception('IMAP error !')
                self._disconnect()

            time.sleep(1)

        self._disconnect()

        if self._unseen_command:
            subprocess.run([self._unseen_command, '0'])

    def stop(self, *_, **__):
        self._logger.info('Stopping...')
        self._running = False

    def _disconnect(self):
        if self.connected:
            self._connection.logout()
            self._connection = None

    @property
    def connected(self):
        return self._connection is not None

    def _tick(self):
        if self.connected:
            now = datetime.now()

            if self._last_unseen_stats is None or self._last_unseen_stats < (now - self._unseen_stats_delta):
                self._last_unseen_stats = now
                unseen = self._get_total_unseen_count()
                if unseen != self._last_unseen_count:
                    self._last_unseen_count = unseen
                    self._logger.debug('New unseen count: {}'.format(unseen))

                    if self._unseen_command:
                        self._logger.debug('Calling: {}'.format(self._unseen_command))
                        subprocess.run([self._unseen_command, str(unseen)])
        else:
            self._connect()

    def _connect(self):
        """
        Connexion au serveur IMAP
        """
        assert self._connection is None

        self._logger.info('Connecting to {}...'.format(self._server))

        self._connection = imaplib.IMAP4_SSL(self._server)
        err_code, err_message = self._connection.login(self._login, self._password)
        if err_code != 'OK':
            self._logger.error('Failed to connect to {}: {}'.format(self._server, err_message))
            self._connection = None
            return

        self._on_connection_success()

    def _on_connection_success(self):
        self._logger.info('Connection succeeded!')
        self._list_mailboxes()

    def _get_message_headers(self, msg_num):
        err_code, raw_msg_headers = self._connection.fetch(msg_num, '(BODY[HEADER])')
        msg_headers = raw_msg_headers[0][1].decode().split('\r\n')
        headers = OrderedDict()
        for header in msg_headers:
            splitted = header.split(': ', 1)
            if len(splitted) > 1:
                headers[splitted[0].strip()] = splitted[1].strip()

        return headers

    def _get_message_count(self, mailbox):
        """
        Retourne le nombre de messages non lus dans une boite spécifique
        :param mailbox: boite mail
        :return: le nombre de messages non lus
        """
        unseen_msg_count = 0
        total_msg_count = 0

        err_code, msg_count = self._connection.select(mailbox, readonly=True)
        if err_code == 'OK':
            total_msg_count = int(msg_count[0])
            err_code, msg_list = self._connection.search(None, '(UNSEEN)')
            if err_code == 'OK':
                msg_list = msg_list[0].decode()
                if msg_list:
                    unseen_msg_count = len(msg_list.split(' '))

        return total_msg_count, unseen_msg_count

    def _get_total_unseen_count(self):
        total_unseen = 0
        for mb in self._mailboxes:
            mb_name = mb['name']
            if mb_name in self._mailbox_blacklist:
                self._logger.debug('Mailbox "{}" is blacklisted'.format(mb_name))
                continue

            unseen = self._get_unseen_count(mb_name)
            self._logger.debug('Mailbox "{}" has {} unseen mails'.format(mb_name, unseen))
            total_unseen += unseen
        return total_unseen

    def _get_unseen_count(self, mailbox):
        """
        Nombre de message non lus sur une boite mail
        :param mailbox: boite mail
        """
        err_code, data = self._connection.status('"{}"'.format(mailbox), '(UNSEEN)')
        if err_code == 'OK':
            status_data = data[0].decode().strip()
            rmatch = re.match(r'.* \(UNSEEN (\d+)\)', status_data)
            if rmatch:
                return int(rmatch.group(1))

        return 0

    def _list_mailboxes(self):
        err_code, mailboxes = self._connection.list()
        if err_code != 'OK':
            self._logger.error('Failed to list mailboxes!')
            exit(1)

        mailboxes = [mb.decode() for mb in mailboxes]
        self._mailboxes = []
        for mb in mailboxes:
            match = re.match(r'\((.*?)\) ".*" (.*)', mb)
            if match:
                self._mailboxes.append({
                    'name': match.group(2).strip('"'),
                    'flags': match.group(1)
                })
