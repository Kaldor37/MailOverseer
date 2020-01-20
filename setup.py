from setuptools import setup, find_packages

from mailoverseer import __version__


_PACKAGE_NAME = 'mailoverseer'

setup(
    name=_PACKAGE_NAME,
    version='{}'.format(__version__),
    description='Gestionnaire de mails',
    author='Davy Gabard',
    author_email='davy.gabard@gmail.com',
    packages=find_packages(),
    install_requires=[
        'PyQt5>=5.14'
    ],
    include_pacakge_data=True,
    package_data={
        'mailoverseer': ['icons/*.png']
    }
)
