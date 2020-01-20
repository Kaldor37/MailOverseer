import configparser
import os
import pathlib
import sys

from mailoverseer import MailOverseer


def main():
    home_dir = pathlib.Path.home()

    config_file = os.path.join(str(home_dir), '.config', 'mail-overseer.conf')
    if not os.path.isfile(config_file):
        print('Missing configuration file: {}'.format(config_file), file=sys.stderr)
        exit(1)

    config = configparser.RawConfigParser()
    config.read(config_file)

    overseer = MailOverseer(config)
    exit(overseer.run())


if __name__ == '__main__':
    main()
