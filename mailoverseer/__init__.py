import imaplib
import logging
import os
import re
import signal
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime, timedelta
from os.path import dirname

from PyQt5.QtCore import QTimer, Qt, QRect
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QPen
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction

from .__version__ import __version__

__all__ = ['__version__', 'MailOverseer']

# Path des icons
ICONS_PATH = os.path.join(dirname(__file__), 'icons')


class MailOverseer:

    def __init__(self, config):
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
        log_handler.setLevel(getattr(logging, config.get('overseer', 'log_level', fallback='INFO')))
        log_handler.setFormatter(logging.Formatter('[MailOverseer] [%(levelname)s] %(message)s'))
        self._logger.addHandler(log_handler)

        self._mailboxes = []

        # Unix stop signal bindings
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGQUIT, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGABRT, self.stop)

        # Qt components
        self._app = QApplication([])

        # System tray icon menu
        self._systray_menu = QMenu()
        self._systray_menu.addAction(QAction('Refresh', self._app, triggered=self._on_refresh_clicked))
        self._systray_menu.addSeparator()
        self._systray_menu.addAction(QAction('Exit', self._app, triggered=self.stop))

        # System tray icon
        tray_icon_path = os.path.join(ICONS_PATH, 'tray.png')
        self._default_icon = QIcon(tray_icon_path)
        self._unseen_mails_pixmap = QPixmap(tray_icon_path)
        self._current_unseen_mails_pixmap = None

        self._icon_max_unseen_count = config.get('tray', 'icon_max_unseen_count', fallback=99)
        icon_max_unseen_count_rect = config.get('tray', 'icon_max_unseen_count_rect', fallback='40, 28, 100, 100')
        self._icon_unseen_count_rect = QRect(*[int(coord.strip()) for coord in icon_max_unseen_count_rect.split(',')])
        self._icon_unseen_count_font = QFont()
        self._icon_unseen_count_font_size_1d = int(config.get('tray', 'icon_unseen_count_font_size_1d', fallback=100))
        self._icon_unseen_count_font_size_2d = int(config.get('tray', 'icon_unseen_count_font_size_2d', fallback=75))
        self._icon_unseen_count_color = QColor(config.get('tray', 'icon_unseen_count_color', fallback='white'))
        self._icon_unseen_count_bubble_color = QColor(
            config.get('tray', 'icon_unseen_count_bubble_color', fallback='#f53a86')
        )
        self._icon_unseen_count_bubble_border_pen = QPen(QColor(
            config.get('tray', 'icon_unseen_count_bubble_border_color', fallback='black')
        ))
        self._icon_unseen_count_bubble_border_pen.setWidth(
            int(config.get('tray', 'icon_unseen_count_bubble_border_width', fallback=8))
        )

        self._tray_icon = QSystemTrayIcon(self._default_icon)
        self._tray_icon.setContextMenu(self._systray_menu)
        self._tray_icon.activated.connect(self._on_tray_icon_activated)
        self._systray_click_command = config.get('tray', 'on_click_command', fallback=None)

        # Timer running unseen mail checks
        self._main_timer = QTimer()
        self._main_timer.timeout.connect(self._check_unseen_mails)

    def run(self):
        self._tray_icon.show()
        self._main_timer.start(500)

        return_code = self._app.exec_()

        self._disconnect()
        if self._unseen_command:
            subprocess.run([self._unseen_command, '0'])

        return return_code

    def stop(self, *_, **__):
        """
        Received stop request (Qt / Unix Signal / etc.)
        """
        self._logger.info('Stopping...')
        self._main_timer.stop()

        self._app.quit()

    def _disconnect(self):
        """
        Close SMTP connection
        """
        if self.connected:
            self._connection.logout()
            self._connection = None

    def _on_tray_icon_activated(self, activation_reason: int):
        """
        Clicked on the tray icon
        """
        # Activation via simple click
        if activation_reason != QSystemTrayIcon.Context:

            # Call external command if defined in the configuration
            if self._systray_click_command:
                self._logger.debug('Calling: {}'.format(self._systray_click_command))
                subprocess.run(self._systray_click_command.split(' '))

            # Refresh mails
            self._check_unseen_mails(True)

    def _on_refresh_clicked(self):
        """
        Clicked on refresh button
        """
        self._check_unseen_mails(True)

    @property
    def connected(self):
        return self._connection is not None

    def _check_unseen_mails(self, force=False):
        try:
            if self.connected:
                now = datetime.now()

                if (
                    self._last_unseen_stats is None
                    or self._last_unseen_stats < (now - self._unseen_stats_delta)
                    or force
                ):
                    self._last_unseen_stats = now
                    unseen = self._get_total_unseen_count()
                    if unseen != self._last_unseen_count:
                        self._last_unseen_count = unseen
                        self._logger.info('New unseen count: {}'.format(unseen))

                        if self._unseen_command:
                            self._logger.debug('Calling: {}'.format(self._unseen_command))
                            subprocess.run([self._unseen_command, str(unseen)])

                        self._tray_icon.setIcon(self._gen_unseen_icon(unseen) if unseen > 0 else self._default_icon)

            else:
                self._connect()

        except imaplib.IMAP4.error:
            self._logger.exception('IMAP error !')
            self._disconnect()

    def _connect(self):
        """
        Initiate IMAP connection
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
        """
        IMAP connection succeeded
        """
        self._logger.info('Connection succeeded!')
        self._list_mailboxes()

    def _get_message_headers(self, msg_num):
        """
        Fetch headers for the required message number
        """
        err_code, raw_msg_headers = self._connection.fetch(msg_num, '(BODY[HEADER])')
        msg_headers = raw_msg_headers[0][1].decode().split('\r\n')
        headers = OrderedDict()
        for header in msg_headers:
            splitted = header.split(': ', 1)
            if len(splitted) > 1:
                headers[splitted[0].strip()] = splitted[1].strip()

        return headers

    def _get_total_unseen_count(self):
        """
        Returns the total amount of unseen messages
        """
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
        Returns the amount of unseen messages in the specified mailbox
        :param mailbox: mailbox to check for unseen messages
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

    def _gen_unseen_icon(self, unseen_count: int):
        """
        Generates unseen mails icon

        :param unseen_count: amount of uneen mails
        """
        # Pixmap must be kept in memory for later repaint
        self._current_unseen_mails_pixmap = self._unseen_mails_pixmap.copy()

        painter = QPainter(self._current_unseen_mails_pixmap)

        # Fill count bubble
        painter.setBrush(self._icon_unseen_count_bubble_color)
        painter.drawEllipse(self._icon_unseen_count_rect)

        # Draw count bubble border
        painter.setPen(self._icon_unseen_count_bubble_border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(self._icon_unseen_count_rect)

        # Write unread count
        count = str(self._icon_max_unseen_count if unseen_count > self._icon_max_unseen_count else unseen_count)
        self._icon_unseen_count_font.setPixelSize(
            self._icon_unseen_count_font_size_2d if len(count) > 1 else self._icon_unseen_count_font_size_1d
        )
        painter.setFont(self._icon_unseen_count_font)
        painter.setPen(self._icon_unseen_count_color)
        painter.drawText(self._icon_unseen_count_rect, Qt.AlignCenter, count)
        return QIcon(self._current_unseen_mails_pixmap)
