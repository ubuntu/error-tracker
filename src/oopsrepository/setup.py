#!/usr/bin/env python
from distutils.core import setup
import os.path

import oopsrepository

def get_version():
    return '.'.join(
        str(component) for component in oopsrepository.__version__[0:3])


def get_long_description():
    manual_path = os.path.join(
        os.path.dirname(__file__), 'README')
    return open(manual_path).read()


setup(name='oopsrepository',
      author='Launchpad Developers',
      author_email='launchpad-dev@lists.launchpad.net',
      url='https://launchpad.net/oopsrepository',
      description=('OOPS (Server fault report) repository.'),
      long_description=get_long_description(),
      version=get_version(),
      classifiers=["License :: OSI Approved :: GNU Affero General Public License v3"],
      packages=['oopsrepository', 'oopsrepository.tests', 'oopsrepository.testing'],
      )
