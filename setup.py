#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = 'Rimco'

import sys
import os
import subprocess
import shutil

from ospy.helpers import is_python2

def yes_no(msg):
    response = ''
    while response.lower().strip() not in ['y', 'yes', 'n', 'no']:
        if is_python2():
            response = raw_input('%s [y/yes/n/no]\n' % msg)
        else:
            response = input('%s [y/yes/n/no]\n' % msg)
    return response.lower().strip() in ['y', 'yes']


def install_package(module, easy_install=None, package=None, pip=None, git=None, git_execs=None, zipfile=None, zip_cwd=None, zip_execs=None):
    from ospy.helpers import del_rw
    try:
        print('Checking %s' % module)
        __import__(module)
        print('%s is available' % module)
        return
    except Exception:
        if not yes_no('%s not available, do you want to install it?' % module):
            return

    done = False
    if not done and easy_install is not None:
        try:
            subprocess.check_call([sys.executable, '-m', 'easy_install', easy_install])
            done = True
        except Exception as err:
            print('Failed to use easy_install:', err)

    if sys.platform.startswith('linux'):
        if not done and package is not None:
            try:
                subprocess.check_call(['apt-get', 'install', package])
                done = True
            except Exception as err:
                print('Failed to use apt-get:', err)

        if not done and package is not None:
            try:
                subprocess.check_call(['yum', 'install', package])
                done = True
            except Exception as err:
                print('Failed to use yum:', err)

    if not done and pip is not None:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip])
            done = True
        except Exception as err:
            print('Failed to use pip:', err)

    if not done and git is not None and git_execs is not None:
        try:
            shutil.rmtree('tmp', onerror=del_rw)
            subprocess.check_call(['git', 'clone', git, 'tmp'])
            for exc in git_execs:
                subprocess.check_call(exc, cwd='tmp')
            shutil.rmtree('tmp', onerror=del_rw)
            done = True
        except Exception as err:
            print('Failed to use git:', err)

    if not done and zipfile is not None and zip_cwd is not None and zip_execs is not None:
        try:
            del_rw(None, 'tmp.zip', None)
            shutil.rmtree('tmp', onerror=del_rw)
            if is_python2():
                from urllib import urlretrieve
            else:
                from urllib.request import urlretrieve
            urlretrieve(zipfile, 'tmp.zip')

            import zipfile
            zipfile.ZipFile('tmp.zip').extractall('tmp')
            del_rw(None, 'tmp.zip', None)

            for exc in zip_execs:
                subprocess.check_call(exc, cwd=os.path.join('tmp', zip_cwd))

            shutil.rmtree('tmp', onerror=del_rw)
            done = True
        except Exception as err:
            print('Failed to use zip file:', err)

    if not done:
        print('Failed to install %s.' % module)


def install_service():
    my_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join('/etc', 'init.d', 'ospy')
    if sys.platform.startswith('linux'):
        if yes_no('Do you want to install OSPy as a service?'):

            with open(os.path.join(my_dir, 'service', 'ospy.sh')) as source:
                with open(path, 'w') as target:
                    target.write(source.read().replace('{{OSPY_DIR}}', my_dir))
            os.chmod(path, 0o755)
            subprocess.check_call(['update-rc.d', 'ospy', 'defaults'])
            print('Done installing service.')
    else:
        print('Service installation is only possible on unix systems.')


def uninstall_service():
    if sys.platform.startswith('linux'):
        if os.path.exists(os.path.join('/var', 'run', 'ospy.pid')):
            try:
                subprocess.Popen(['service', 'ospy', 'stop'])
            except Exception:
                print('Could not stop service.')
        else:
            print('OSPy was not running.')

        try:
            subprocess.check_call(['update-rc.d', '-f', 'ospy', 'remove'])
        except Exception:
            print('Could not remove service using update-rc.d')

        import glob
        old_paths = glob.glob(os.path.join('/etc', 'init.d', '*ospy*'))
        for old_path in old_paths:
            os.unlink(old_path)

        if old_paths:
            print('Service removed')
        else:
            print('Service not found')
    else:
        print('Service uninstall is only possible on unix systems.')


def check_password():
    from ospy.options import options
    from ospy.helpers import test_password, password_salt, password_hash
    if not options.no_password and test_password('opendoor'):
        if yes_no('You are still using the default password, you should change it! Do you want to change it now?'):
            from getpass import getpass
            pw1 = pw2 = ''
            while True:
                pw1 = getpass('New password: ')
                pw2 = getpass('Repeat password: ')
                if pw1 != '' and pw1 == pw2:
                    break
                print('Invalid input!')

            options.password_salt = password_salt()  # Make a new salt
            options.password_hash = password_hash(pw1, options.password_salt)


def start():
    if yes_no('Do you want to start OSPy now?'):
        if sys.platform.startswith('linux'):
            try:
                subprocess.Popen(['service', 'ospy', 'restart'])
            except Exception:
                subprocess.Popen([sys.executable, 'run.py'])

        else:
            subprocess.check_call(['cmd.exe', '/c', 'start', sys.executable, 'run.py'])


if __name__ == '__main__':
    # On unix systems we need to be root:
    if sys.platform.startswith('linux'):
        if not os.getuid() == 0:
            sys.exit("This script needs to be run as root.")

    if len(sys.argv) == 2 and sys.argv[1] == 'install':
        pkg = False
        try:
            import setuptools
            pkg = True
        except ImportError:
            if yes_no('Could not find setuptools which is needed to install packages, do you want to install it now?'):
                if is_python2():
                    from urllib import urlretrieve
                else:
                    from urllib.request import urlretrieve
                from ospy.helpers import del_rw
                shutil.rmtree('tmp', onerror=del_rw)
                os.mkdir('tmp')
                urlretrieve('https://bootstrap.pypa.io/ez_setup.py', 'tmp/ez_setup.py')
                subprocess.check_call([sys.executable, 'ez_setup.py'], cwd='tmp')
                shutil.rmtree('tmp', onerror=del_rw)
                pkg = True

        if not pkg:
            print('Cannot install packages without setuptools.')
        else:
            # Check if packages are available:
            install_package('web', 'web.py[cheroot]==0.51', 'python-webpy', 'web.py[cheroot]==0.51',
                            'https://github.com/webpy/webpy.git',
                            [[sys.executable, 'setup.py', 'install']],
                            'https://github.com/webpy/webpy/archive/master.zip', 'webpy-master',
                            [[sys.executable, 'setup.py', 'install']])

            if is_python2():
                install_package('mdx_partial_gfm', None, None, 'py-gfm==0.1.1',
                                'https://github.com/Zopieux/py-gfm.git',
                                [[sys.executable, 'setup.py', 'install']],
                                'https://github.com/Zopieux/py-gfm/archive/master.zip', 'py-gfm-master',
                                [[sys.executable, 'setup.py', 'install']])

                install_package('pygments', 'pygments==2.5.2', 'python-pygments', 'pygments==2.5.2',
                                'http://bitbucket.org/birkenfeld/pygments-main',
                                [[sys.executable, 'setup.py', 'install']],
                                'https://bitbucket.org/birkenfeld/pygments-main/get/0fb2b54a6e10.zip', 'birkenfeld-pygments-main-0fb2b54a6e10',
                                [[sys.executable, 'setup.py', 'install']])
            else:
                install_package('cmarkgfm', None, None, 'cmarkgfm',
                                'https://github.com/theacodes/cmarkgfm',
                                [[sys.executable, 'setup.py', 'install']],
                                'https://github.com/Zopieux/cmarkgfm/archive/master.zip', 'cmarkgfm-master',
                                [[sys.executable, 'setup.py', 'install']])
                if sys.platform.startswith('linux'):
                    install_package('smbus', None, 'python3-smbus', 'smbus',
                                    None, None, None, None, None)

        install_service()

        check_password()

        start()

        print('Done')

    elif len(sys.argv) == 2 and sys.argv[1] == 'uninstall':
        uninstall_service()

    else:
        sys.exit("Usage:\n"
                 "setup.py install:   Interactive install.\n"
                 "setup.py uninstall: Removes the service if installed.")
