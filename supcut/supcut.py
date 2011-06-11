#!/usr/bin/env python
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
import curses
from optparse import OptionParser
from os import getcwd, makedirs, rename
from os.path import isdir, isfile
import pyinotify        # this is Inotify (file alteration)
from shutil import copyfile
from setproctitle import setproctitle
from subprocess import Popen, PIPE, STDOUT
from sys import exit
from threading import Lock
from time import gmtime, strftime

from mailer import send_email

try:
    import gtk
    import pynotify as osd  # this is Notify (OSD messages)
    osd_available = True
except ImportError:
    osd_available = False

__version__ = '0.6-unreleased'

supcut = None
msg = ''

def say(s, newline=True):
    """Print on stdout"""
    if newline:
        print s
    else:
        print s,


class Conf(object):
    """Read configuration file, and create the .supcut directory if needed"""

    def __init__(self):
        if not isdir('.supcut'):
            self._dir_setup()
        for fn in ('.supcut/config.ini', '.supcut/email.tpl'):
            if not isfile(fn):
                say("The file %s is missing." % fn)
                exit(1)
        self.cp = SafeConfigParser()
        self.cp.read('.supcut/config.ini')

    def __getattr__(self, name):
        """Expose a conf variable as an attr"""
        if name in ('verbose', 'send_osd_notifications'):
            return self.cp.getboolean('global', name)
        elif name.startswith('email_'):
            return self.cp.get('email', name[6:])
        return self.cp.get('global', name)

    def _dir_setup(self):
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


class Screen(object):
    """Handle ncurses screen"""

    def __init__(self, parent=None):
        """Setup curses screen"""
        self._supcut = parent
        self._menu = [
            ['Monitored files', self._supcut.watched,
                self._supcut.watched_selected],
            ['Test files', self._supcut.test_files,
                self._supcut.test_files_selected],
            ['Failing tests',self._supcut.failing_tests,
                self._supcut.failing_tests_selected],
            ['Test output']
        ]

        self._current_menu = 0
        self._y = 0
        self._scroll = 0
        self._cursor = 1
        self._overflow = False


        screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        screen.keypad(1)
        screen.border(0)
        screen.refresh()
        self._screen = screen

    def _blank(self):
        """Erase the screen"""
        self._screen.erase()
        self._screen.border(0)
        self._cursor = 1
        self._overflow = False

    def addstr(self, row, col, s, bold=False):
        """Proxy for curses screen.addstr,
        ignore exceptions to prevent crashing on small terminals
        """
        try:
            if bold:
                self._screen.addstr(row, col, s, curses.A_BOLD)
            else:
                self._screen.addstr(row, col, s)
        except:
            pass

    def _print(self, s, bold=None):
        """Print on curses screen"""
        max_y, max_x = self._screen.getmaxyx()

        if s == None or s.strip() == '':
            self._cursor += 1

        s = s.rstrip()
        w = max_x - 4
        chunks = (s[i:i+w] for i in xrange(0, len(s), w))
        for line in chunks:
            try:
                if self._cursor == max_y - 2:
                    self.addstr(self._cursor, 4, "vvv")
                    self._overflow = True
                    return
                elif self._cursor > max_y - 2:
                    return
                self.addstr(self._cursor, 2, line, bold=bold)
            except:
                pass
            self._cursor += 1

    def _print_column(self):
        """Print items in a column flagging the selected ones,
        highlighting one of them"""
        self._menu = (
            ['Monitored files', self._supcut.watched,
                self._supcut.watched_selected],
            ['Test files', self._supcut.test_files,
                self._supcut.test_files_selected],
            ['Failing tests',self._supcut.failing_tests,
                self._supcut.failing_tests_selected],
            ['Test output']
        )
        title, li, selected = self._menu[self._current_menu]
        if self._scroll:
            self._print("   ^^^")
        for n, item in enumerate(li[self._scroll:]):
            sel = item in selected
            sel = "+" if sel else " "
            bold = (n == self._y)
            self._print(" %s %s" % (sel, item), bold=bold)

    def _print_footer(self, s=None):
        """Print footer message"""
        global msg
        max_y, max_x = self._screen.getmaxyx()
        if s is None:
            s = msg
        s = s.center(max_x - 16)
        s = "-%s-" % s
        self.addstr(max_y - 1, 7, s)

    def _print_failing_test(self):
        """Print the output of a failing test"""
        try:
            test_name = self._supcut.failing_tests[self._y]
        except IndexError:
            self._current_menu = 2
            return

        self._print("     -- %s --" % test_name)
        for line in self._supcut.failing_tests_dict[test_name][self._scroll:]:
            self._print(line)

    def refresh(self):
        """Refresh curses screen"""
        global msg
        self._blank()

        sup = self._supcut
        with sup.lock:
            #self._print("Watched: %3d  Tot: %3d  Failed: %3d"
            #    " Last run: %8s Len: %7s Running: [%s]" % (
            #    len(sup.watched_selected),
            #    sup.total_tests_n,
            #    len(sup.failing_tests),
            #    sup.last_run,
            #    sup.last_run_duration,
            #    "*" if sup.currently_running.locked() else " "
            #))
            if sup.currently_running.locked():
                msg = "Running..."
            else:
                msg = "Tot: %d Failed: %d Last run: %s Len: %s" % (
                    sup.total_tests_n,
                    len(sup.failing_tests),
                    sup.last_run,
                    sup.last_run_duration,
                )

        s = self._screen
        col = 2
        for n in xrange(4):
            title = self._menu[n][0]
            bold = (n == self._current_menu)
            self.addstr(1, col, title, bold=bold)
            col += len(title) + 2
        self._cursor = 4
        if self._current_menu < 3:
            self._print_column()
        elif self._current_menu == 3:
            self._print_failing_test()

        self._print_footer()
        s.refresh()

    def handle_keypress(self):
        """Handle user input"""
        c = self._screen.getch()

        # quit
        if c == ord('q'):
            self._supcut.terminate()
            raise KeyboardInterrupt

        # move between menus
        elif c == curses.KEY_LEFT:
            if self._current_menu:
                self._current_menu -=1
            else:
                self._current_menu = 2
            self._y = 0
            self._scroll = 0
        elif c == curses.KEY_RIGHT:
            if self._current_menu < len(self._menu) - 2:
                self._current_menu +=1
            else:
                self._current_menu = 0
            self._y = 0
            self._scroll = 0

        # move up/down
        elif c == curses.KEY_DOWN:
            # test output tab
            if self._current_menu == 3:
                if self._overflow:
                    self._scroll += 1
                return
            max_y, max_x = self._screen.getmaxyx()
            depth = len(self._menu[self._current_menu][1]) - self._scroll
            if self._y < max_y - 7 and self._y < depth - 1:
                self._y +=1

        elif c == curses.KEY_UP:
            # test output tab
            if self._current_menu == 3:
                if self._scroll:
                    self._scroll -= 1
                return
            if self._scroll and self._y == 0:
                self._scroll -= 1
            if self._y:
                self._y -=1

        # space: toggle item
        elif c == ord(' '):
            if self._current_menu < 3:
                self._toggle()

        # enter
        elif c == ord('\n'):
            if self._current_menu == 2:
                self._current_menu = 3

        # run test now
        elif c == ord('r'):
            self._supcut.run_test_now()



    def _toggle(self):
        """Toggle a menu item"""
        title, li, selected = self._menu[self._current_menu]
        try:
            item = li[self._y]
            selected = selected.symmetric_difference([item])
            if self._current_menu == 0:
                if item in self._supcut.watched_selected:
                    self._supcut.watched_selected.remove(item)
                    #FIXME
                    self._supcut.remove_watch(item)
                else:
                    self._supcut.watched_selected.add(item)
                    self._supcut.add_watch(item)

            elif self._current_menu == 1:
                self._supcut.test_files_selected = selected
            elif self._current_menu == 2:
                self._supcut.failing_tests_selected = selected
        except IndexError:
            pass


    def _print_list(self):
        """Print connections list"""
        screen = self._screen
        traffic = self.traffic
        screen.erase()
        screen.border(0)

        self.addstr(2, 2, "Total: %d Parsed: %d" % \
            (self._stats['total'], self._stats['parsed']))
        ln = 4
        for pid in sorted(traffic):
            self.addstr(ln, 4, pid)
            ln += 1
            for src in sorted(traffic[pid]):
                s = " %s %s" % (src, traffic[pid][src])
                self.addstr(ln, 4, s)
                ln += 1
            self.addstr(ln, 4, '  ')
            ln += 1
        screen.refresh()

    def terminate(self):
        """Terminate curses screen"""
        curses.nocbreak()
        self._screen.keypad(0)
        curses.echo()
        curses.endwin()






class Runner(pyinotify.ProcessEvent):
    """Run nosetests when needed"""

    # nosetest related methods

    def _failing(self, out):
        """Build failing tests set and dict"""
        d = {}
        title = None
        for line in out:
            if line.startswith('FAIL: '):
                title = line.strip()[6:]
                d[title] = []
            elif title:
                d[title].append(line)
        #FIXME: line containing '============' should be removed
        #FIXME: spurious "FAIL: " in the test output will break this
        return frozenset(d.keys()), d

    def _tot(self, out):
        """Get total number of tests ran.
        Returns (total, execution_time)
        """
        # example: "Ran 74 tests in 3.215s"
        for line in reversed(out):
            if line.startswith('Ran '):
                li = line.split()
                return (int(li[1]), li[4])
            elif line.startswith('----'):
                return (None, None)
        return (None, None)

    def _save_output(self, out):
        """Save new output after renaming the previous one"""
        f = open('.supcut/output.new', 'w')
        f.writelines(out)
        f.close()
        if not isfile('.supcut/output'):
            open('.supcut/output', 'w').close()
        rename('.supcut/output', '.supcut/output.old')
        rename('.supcut/output.new', '.supcut/output')

    def _get_trace(self, out, name):
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


    # FIXME: note is being run two times on each file change
    def run_nose(self):
        """Run nosetests, collects output"""
        global supcut
        supcut.currently_running.acquire()
        supcut.screen.refresh()

        cmd = "nosetests %s %s" % (
            supcut.conf.nose_opts,
            ' '.join(supcut.test_files_selected),
        )
        p = Popen(cmd, shell=True, bufsize=4096,
            stdout=PIPE, stderr=STDOUT, close_fds=True)
        out = p.stdout.readlines()
        self._save_output(out)

        tot, run_time = self._tot(out)
        failing, failing_dict = self._failing(out)

        old = open('.supcut/output.old').readlines()
        failing_old, failing_old_dict = self._failing(old)
        tot_old, old_run_time = self._tot(old)

        new_failing = failing - failing_old
        fixed = failing_old - failing
        tot_diff = tot - tot_old

        for name in fixed:
#            send_email(conf, 'success', name, []) FIXME
            self._send_osd(name, 'Test fixed!', icon='success')

        for name in new_failing:
            trace = self._get_trace(out, name)
#            send_email(conf, 'failure', name, trace)
            self._send_osd( name, 'Failing test', icon='failure')

        if tot_diff > 0:
            self._send_osd('New test', "%s test added" % tot_diff, icon='success')
        elif tot_diff < 0:
            self._send_osd('Test removed', "%s test removed" % -tot_diff, icon='success')

        tstamp = strftime("%H:%M:%S", gmtime())

        with supcut.lock:
            supcut.failing_tests = list(failing)
            supcut.failing_tests_dict = failing_dict
            supcut.failing_tests_selected = set(failing)
            supcut.total_tests_n = tot
            supcut.last_run = tstamp
            supcut.last_run_duration = run_time

        supcut.currently_running.release()
        supcut.screen.refresh()




    def process_IN_CLOSE_WRITE(self, event):
        """Run nose when any monitored file has been modified"""
        self.run_nose()


    # OSD related methods

    def _send_osd(self, title, s, icon=None):
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




class Supcut(object):

    def __init__(self):
        """Read configuration, setup Inotify watching"""
        # shared test attrs
        self.currently_running = Lock()
        self.watched = []
        self.total_tests_n = 0
        self.failing_tests = []
        self.failing_tests_selected = set()
        self.last_run = '--:--:--'
        self.last_run_duration = '--.---s'
        self.test_files = []

        self.lock = Lock()
        self.conf = Conf()

        if self.conf.send_osd_notifications and not osd_available:
            print "send_osd_notifications is set to True in the configuration " \
            "but the gtk and/or pynotify modules are not available." \
            "\nPlease ensure that the modules are installed."
            exit(1)

        self.test_files = self.conf.test_files.split(' ')
        self.test_files_selected = set(self.test_files)
        self.cli_opts = self._parse_args()

        self._wm = pyinotify.WatchManager()
        self._notifier = pyinotify.ThreadedNotifier(self._wm, default_proc_fun=Runner())

        self.watched = []
        for glob in map(str.strip, self.conf.files.split(' ')):
            li = self._wm.add_watch(glob, pyinotify.ALL_EVENTS,
                rec=False, do_glob=True)
            self.watched.extend(li)

        self.watched_selected = set(self.watched)

        self.screen = Screen(parent=self)

    def add_watch(self, p):
        self._wm.add_watch(p, pyinotify.ALL_EVENTS, rec=False)

    def remove_watch(self, p):
        self._wm.add_watch(p, pyinotify.ALL_EVENTS, rec=False)



    def _parse_args(self):
        """Parse command-line args"""
        parser = OptionParser()
        parser.add_option("-n", "--now",
            action="store_true", dest="run_now", default=False,
            help="run nosetests immediately")
        parser.add_option("-o", "--noseopts",
            dest="noseopts", help="command to be run")

        options, args = parser.parse_args()
        return options

    def run(self):
        """Start notifier loop"""
        self.screen.refresh()

        if self.cli_opts.run_now:
            Runner().run_nose()

        self._notifier.start()

        while True:
            self.screen.handle_keypress()
            self.screen.refresh()

    def run_test_now(self):
        Runner().run_nose()

    def terminate(self):
        self.screen.terminate()
        try:
            self._notifier.stop()
        except RuntimeError:
            pass
        except OSError:
            pass


def main():
    global supcut
    setproctitle('supcut')

    try:
        supcut = Supcut()
        supcut.run()
    except KeyboardInterrupt:
        if supcut:
            supcut.terminate()
    except Exception, e:
        if supcut:
            supcut.terminate()
        import traceback
        print traceback.format_exc()


if __name__ == '__main__':
    main()
