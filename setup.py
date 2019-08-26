from setuptools import setup, find_packages

from mailoverseer import __version__


_PACKAGE_NAME = 'mailoverseer'

setup(
    name=_PACKAGE_NAME,
    version='{}'.format(__version__),
    description='Gestionnaire de mails',
    author='Davy Gabard',
    author_email='davy.gabard@gmail.com',
    packages=find_packages()
)
