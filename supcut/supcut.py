#
# supcut - Simple Unobtrusive Python Contituous Unit Testing
#
# Copyright (C) 2010 Federico Ceratto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ConfigParser import SafeConfigParser
import gtk
from os import getcwd, makedirs, rename
from os.path import isdir, isfile
import pynotify as osd  # this is Notify (OSD messages)
import pyinotify        # this is Inotify (file alteration)
from shutil import copyfile
from subprocess import Popen, PIPE, STDOUT
from sys import exit

from mailer import send_email

__version__ = '0.5.3'

conf = None

def say(s, newline=True):
    """Print unless in quiet mode"""
    if conf and conf.quiet:
        return
    if newline:
        print s
    else:
        print s,

def whisper(s, newline=True):
    """Print only in verbose mode"""
    if conf.verbose and not conf.quiet:
        say(s, newline=newline)

def dir_setup():
    """Setup .supcut directory"""
    say("""First supcut run: a directory called .supcut should
be created at the root directory of your project.

The current path is: %s""" % getcwd())
    a = raw_input('Create .supcut directory [y/N]? ')
    if a != 'y':
        exit(0)
    makedirs('.supcut')
    say("Creating configuration file")
    copyfile('/usr/share/doc/python-supcut/examples/config.ini',
        '.supcut/config.ini')
    say("Creating email template file")
    copyfile('/usr/share/doc/python-supcut/examples/email.tpl',
        '.supcut/email.tpl')


class Conf(object):
    """Read configuration file, create it as well as .supcut if needed"""

    def __init__(self):
        if not isdir('.supcut'):
            dir_setup()
        for fn in ('.supcut/config.ini', '.supcut/email.tpl'):
            if not isfile(fn):
                say("The file %s is missing." % fn)
                exit(1)
        self.cp = SafeConfigParser()
        self.cp.read('.supcut/config.ini')

    def __getattr__(self, name):
        """Expose a conf variable as an attr"""
        if name in ('verbose', 'quiet', 'send_osd_notifications'):
            return self.cp.getboolean('global', name)
        elif name.startswith('email_'):
            return self.cp.get('email', name[6:])
        return self.cp.get('global', name)


def save(out):
    """Save new output after renaming the previous one"""
    f = open('.supcut/output.new', 'w')
    f.writelines(out)
    f.close()
    if not isfile('.supcut/output'):
        open('.supcut/output', 'w').close()
    rename('.supcut/output', '.supcut/output.old')
    rename('.supcut/output.new', '.supcut/output')


def send_osd(title, s, icon=None):
    """Notify the user using OSD"""
    n = osd.Notification(title, s)
    #n.set_urgency(osd.URGENCY_NORMAL)
    #n.set_timeout(osd.EXPIRES_NEVER)
    #n.add_action("clicked","Button text", callback_function, None)
    helper = gtk.Button()
    #        icon = gtk.gdk.pixbuf_new_from_file(RESOURCES + "audio-x-generic.png")

    if icon == 'success':
        i = helper.render_icon(gtk.STOCK_YES, gtk.ICON_SIZE_DIALOG)
    elif icon == 'failure':
        i = helper.render_icon(gtk.STOCK_NO, gtk.ICON_SIZE_DIALOG)
    elif icon == 'new_test':
        i = helper.render_icon(gtk.STOCK_ADD, gtk.ICON_SIZE_DIALOG)
    else:
        i = helper.render_icon(gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_DIALOG)

    n.set_icon_from_pixbuf(i)
    n.show()

def get_trace(out, name):
    """Extract the test failure trace related to a failing test"""
    trace = None
    for line in out:
        if line == "FAIL: %s\n" % name:
           trace = []
        elif trace != None:
            if line.startswith('=' * 10):
                return trace
            trace.append(line.strip())
    if trace:
        return trace
    return []


class Runner(pyinotify.ProcessEvent):
    """Run nosetests when needed"""

    def _failing(self, out):
        """Get failing tests"""
        failing = [s for s in out if s.startswith('FAIL: ')]
        return frozenset(s.strip()[6:] for s in failing)

    def _tot(self, out):
        """Get total number of tests ran."""
        for last in xrange(6):
            if out[-last].startswith('Ran '):
                li = out[-last].split()
                return int(li[1])

    # FIXME: note is being run two times on each file change
    def _run_nose(self):
        """Run nosetests, collects output"""

        p = Popen(conf.cmd, shell=True, bufsize=4096,
          stdout=PIPE, stderr=STDOUT, close_fds=True)
        out = p.stdout.readlines()
        save(out)

        tot = self._tot(out)
        failing = self._failing(out)
        old = open('.supcut/output.old').readlines()
        failing_old = self._failing(old)
        tot_old = self._tot(old)

        new_failing = failing - failing_old
        fixed = failing_old - failing
        tot_diff = tot - tot_old

        for name in fixed:
            send_email(conf, 'success', name, [])
            send_osd(name, 'Test fixed!', icon='success')

        for name in new_failing:
            trace = get_trace(out, name)
            send_email(conf, 'failure', name, trace)
            send_osd( name, 'Failing test', icon='failure')

        if tot_diff > 0:
            send_osd('New test', "%s test added" % tot_diff, icon='success')
        elif tot_diff < 0:
            send_osd('Test removed', "%s test added" % tot_diff, icon='success')

        whisper('\n')
        whisper(''.join(out))
        say("%d tests ran." % tot)


    def process_IN_CLOSE_WRITE(self, event):
        """Run nose when any monitored file has been modified"""
        whisper("%s has been modified" % event.path)
        say("Running nosetests...", newline=False)
        self._run_nose()


def main():
    """Read conf, setup Inotify watching"""
    global conf
    conf = Conf()
    say("Supcut v. %s" % __version__)

    wm = pyinotify.WatchManager()
    notifier = pyinotify.Notifier(wm, default_proc_fun=Runner())

    watched = []
    for p in conf.files.split(','):
        p = p.strip()
        w = wm.add_watch(p, pyinotify.ALL_EVENTS, rec=False, do_glob=True)
        watched.extend(w)

    say("%d files monitored" % len(watched))
    for fn in watched:
        whisper(" %s" % fn)
    notifier.loop()


if __name__ == '__main__':
    main()
