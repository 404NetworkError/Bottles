# importer_row.py
#
# Copyright 2025 The Bottles Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from gettext import gettext as _

from gi.repository import Gtk, Adw

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/importer-row.ui")
class ImporterRow(Adw.ActionRow):
    __gtype_name__ = "ImporterRow"

    # region Widgets
    label_manager = Gtk.Template.Child()
    btn_import = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    img_lock = Gtk.Template.Child()

    # endregion

    def __init__(self, im_manager, prefix, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = im_manager.window
        self.import_manager = im_manager.import_manager
        self.prefix = prefix

        # populate widgets
        self.set_title(prefix.get("Name"))
        self.label_manager.set_text(prefix.get("Manager"))

        if prefix.get("Lock"):
            self.img_lock.set_visible(True)

        self.label_manager.add_css_class("tag-%s" % prefix.get("Manager").lower())

        # connect signals
        self.btn_browse.connect("clicked", self.browse_wineprefix)
        self.btn_import.connect("clicked", self.import_wineprefix)

    def browse_wineprefix(self, widget):
        ManagerUtils.browse_wineprefix(self.prefix)

    def import_wineprefix(self, widget):
        @GtkUtils.run_in_main_loop
        def set_imported(result, error=False):
            self.btn_import.set_visible(result.ok)
            self.img_lock.set_visible(result.ok)

            if result.ok:
                self.window.show_toast(
                    _('"{0}" imported').format(self.prefix.get("Name"))
                )

            self.set_sensitive(True)

        self.set_sensitive(False)

        RunAsync(
            self.import_manager.import_wineprefix,
            callback=set_imported,
            wineprefix=self.prefix,
        )
