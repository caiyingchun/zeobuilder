# Zeobuilder is an extensible GUI-toolkit for molecular model construction.
# Copyright (C) 2005 Toon Verstraelen
#
# This file is part of Zeobuilder.
#
# Zeobuilder is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# --



from base import Single
from mixin import ambiguous, insensitive

import gtk


class Optional(Single):
    def __init__(self, slave):
        Single.__init__(self)
        self.slave = slave
        slave.parent = self
        self.check_button = None

    def init_widgets(self, instance):
        self.slave.init_widgets(instance)
        Single.init_widgets(self, instance)

    def init_widgets_multiplex(self, instances):
        self.slave.init_widgets_multiplex(instances)
        Single.init_widgets_multiplex(self, instances)

    def get_active(self):
        return self.slave.get_active()

    def applicable(self, instance):
        return self.slave.get_active()

    def changed_names(self):
        if not self.get_active():
            return []
        else:
            return self.slave.changed_names()

    def create_widgets(self):
        Single.create_widgets(self)
        self.high_widget = self.slave.high_widget
        self.check_button = gtk.CheckButton()
        self.check_button.connect("toggled", self.check_button_toggled)
        if self.slave.label_text is not None:
            self.check_button.add(gtk.Label(self.slave.label_text))

    def destroy_widgets(self):
        if self.check_button is not None:
            self.check_button.destroy()
            self.check_button = None
        self.slave.destroy_widgets()
        Single.destroy_widgets(self)

    def get_widgets_separate(self):
        label, data_widget, bu_popup = self.slave.get_widgets_separate()
        return self.check_button, data_widget, bu_popup

    def read(self):
        if self.get_active():
            self.slave.read()
            self.check_button.set_active(self.slave.get_sensitive())

    def read_multiplex(self):
        if self.get_active():
            self.slave.read_multiplex()
            self.check_button.set_active(self.slave.get_sensitive())

    def write(self):
        if self.get_active():
            self.slave.write()

    def write_multiplex(self):
        if self.get_active():
            self.slave.write_multiplex()

    def check(self):
        if self.get_active():
            self.slave.check()

    def grab_focus(self):
        self.slave.grab_focus()

    def check_button_toggled(self, check_button):
        self.slave.set_sensitive(check_button.get_active())

    def get_sensitive(self):
        return self.slave.get_sensitive()

    def set_sensitive(self, sensitive):
        self.check_button.set_sensitive(sensitive)
        self.slave.set_sensitive(sensitive)
