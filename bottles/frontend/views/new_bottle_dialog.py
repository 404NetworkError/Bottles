# new_bottle_dialog.py
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
from typing import Any, Optional
from gi.repository import Gtk, Adw, Pango, Gio, Xdp, GObject

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.threading import RunAsync
from bottles.backend.models.result import Result
from bottles.frontend.utils.filters import add_yaml_filters, add_all_filters
from bottles.frontend.utils.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/check-row.ui")
class BottlesCheckRow(Adw.ActionRow):
    """An `AdwActionRow` with a designated `GtkCheckButton` as prefix."""

    __gtype_name__ = "BottlesCheckRow"

    check_button = Gtk.Template.Child()

    active = GObject.Property(type=bool, default=False)

    # Add row’s check button to the group
    group = GObject.Property(
        # FIXME: Supposed to be a BottlesCheckRow widget type.
        type=Adw.ActionRow,
        default=None,
        setter=lambda self, group: self.check_button.set_group(group.check_button),
    )


@Gtk.Template(resource_path="/com/usebottles/bottles/new-bottle-dialog.ui")
class BottlesNewBottleDialog(Adw.Dialog):
    __gtype_name__ = "BottlesNewBottleDialog"

    # region Widgets
    application = Gtk.Template.Child()
    gaming = Gtk.Template.Child()
    custom = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_choose_env = Gtk.Template.Child()
    btn_choose_env_reset = Gtk.Template.Child()
    label_choose_env = Gtk.Template.Child()
    status_page_status = Gtk.Template.Child()
    btn_choose_path = Gtk.Template.Child()
    btn_choose_path_reset = Gtk.Template.Child()
    label_choose_path = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    scrolled_output = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_arch = Gtk.Template.Child()
    str_list_arch = Gtk.Template.Child()
    str_list_runner = Gtk.Template.Child()
    menu_duplicate = Gtk.Template.Child()

    # endregion

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # common variables and references
        self.window = GtkUtils.get_parent_window()
        if not self.window or not Xdp.Portal.running_under_sandbox():
            return

        self.app = self.window.get_application()
        self.manager = self.window.manager
        self.new_bottle_config = BottleConfig()
        self.env_recipe_path = None
        self.custom_path = ""
        self.runner = None
        self.default_string = _("(Default)")

        self.arch = {"win64": "64-bit", "win32": "32-bit"}

        # connect signals
        self.btn_cancel.connect("clicked", self.__close_dialog)
        self.btn_close.connect("clicked", self.__close_dialog)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_choose_env.connect("clicked", self.__choose_env_recipe)
        self.btn_choose_env_reset.connect("clicked", self.__reset_env_recipe)
        self.btn_choose_path.connect("clicked", self.__choose_path)
        self.btn_choose_path_reset.connect("clicked", self.__reset_path)
        self.entry_name.connect("changed", self.__check_entry_name)

        # Populate widgets
        self.label_choose_env.set_label(self.default_string)
        self.label_choose_path.set_label(self.default_string)
        self.str_list_runner.splice(0, 0, self.manager.runners_available)
        self.str_list_arch.splice(0, 0, list(self.arch.values()))

    def __check_entry_name(self, *_args: Any) -> None:
        is_duplicate = self.entry_name.get_text() in self.manager.local_bottles
        is_invalid = is_duplicate or self.entry_name.get_text() == ""
        self.btn_create.set_sensitive(not is_invalid)
        self.menu_duplicate.set_visible(is_duplicate)

        if is_invalid:
            self.entry_name.add_css_class("error")
        else:
            self.entry_name.remove_css_class("error")

    def __choose_env_recipe(self, *_args: Any) -> None:
        """
        Opens a file chooser dialog to select the configuration file
        in yaml format.
        """

        def set_path(_dialog, response: Gtk.ResponseType):
            if response == Gtk.ResponseType.ACCEPT:
                self.btn_choose_env_reset.set_visible(True)
                self.env_recipe_path = dialog.get_file().get_path()
                self.label_choose_env.set_label(dialog.get_file().get_basename())
                self.label_choose_env.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select a Configuration File"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.window,
        )

        add_yaml_filters(dialog)
        add_all_filters(dialog)
        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __choose_path(self, *_args: Any) -> None:
        """Opens a file chooser dialog to select the directory."""

        def set_path(_dialog, response: Gtk.ResponseType) -> None:
            if response == Gtk.ResponseType.ACCEPT:
                self.btn_choose_path_reset.set_visible(True)
                self.custom_path = dialog.get_file().get_path()
                self.label_choose_path.set_label(dialog.get_file().get_basename())
                self.label_choose_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Bottle Directory"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.window,
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def create_bottle(self, *_args: Any) -> None:
        """Starts creating the bottle."""
        # set widgets states
        self.set_can_close(False)
        self.stack_create.set_visible_child_name("page_creating")

        if self.custom.active:
            self.runner = self.manager.runners_available[
                self.combo_runner.get_selected()
            ]

        RunAsync(
            task_func=self.manager.create_bottle,
            callback=self.finish,
            name=self.entry_name.get_text(),
            path=self.custom_path,
            environment=self.__radio_get_active(),
            runner=self.runner,
            arch=list(self.arch)[self.combo_arch.get_selected()],
            dxvk=self.manager.dxvk_available[0],
            fn_logger=self.update_output,
            custom_environment=self.env_recipe_path,
        )

    @GtkUtils.run_in_main_loop
    def update_output(self, text: str) -> None:
        """
        Updates label_output with the given text by concatenating
        with the previous text.
        """
        current_text = self.label_output.get_text()
        text = f"{current_text}{text}\n"
        self.label_output.set_text(text)

    @GtkUtils.run_in_main_loop
    def finish(self, result: Optional[Result], error=None) -> None:
        """Updates widgets based on whether it succeeded or failed."""

        def send_notification(notification: Gio.Notification) -> None:
            """Sends notification if out of focus."""
            if not self.window.is_active():
                self.app.send_notification(None, notification)

        self.set_can_close(True)
        self.stack_create.set_visible_child_name("page_completed")
        notification = Gio.Notification()

        # Show error if bottle unsuccessfully builds
        if not result or not result.status or error:
            title = _("Unable to Create Bottle")
            notification.set_title(title)
            notification.set_body(_("Bottle failed to create with one or more errors."))
            self.status_page_status.set_title(title)
            self.btn_close.get_style_context().add_class("destructive-action")
            send_notification(notification)

            # Display error logs in the result page
            self.scrolled_output.unparent()
            box = self.status_page_status.get_child()
            box.prepend(self.scrolled_output)

            return

        # Show success
        title = _("Bottle Created")
        description = _('"{0}" was created successfully.').format(
            self.entry_name.get_text()
        )

        notification.set_title(title)
        notification.set_body(description)

        self.new_bottle_config = result.data.get("config")
        self.btn_close.get_style_context().add_class("suggested-action")
        self.status_page_status.set_icon_name("selection-mode-symbolic")
        self.status_page_status.set_title(title)
        self.status_page_status.set_description(description)
        send_notification(notification)

        # Ask the manager to check for new bottles,
        # then update the user bottles' list.
        self.manager.check_bottles()
        self.window.page_list.update_bottles_list()
        self.window.page_list.show_page(self.new_bottle_config.get("Path"))

    def __radio_get_active(self) -> str:
        # TODO: Remove this ugly zig zag and find a better way to set the environment
        # https://docs.gtk.org/gtk4/class.CheckButton.html#grouping
        if self.application.active:
            return "application"
        if self.gaming.active:
            return "gaming"
        return "custom"

    def __reset_env_recipe(self, *_args: Any) -> None:
        self.btn_choose_env_reset.set_visible(False)
        self.env_recipe_path = None
        self.label_choose_env.set_label(self.default_string)

    def __reset_path(self, *_args: Any) -> None:
        self.btn_choose_path_reset.set_visible(False)
        self.custom_path = ""
        self.label_choose_path.set_label(self.default_string)

    def __close_dialog(self, *_args: Any) -> None:
        # TODO: Implement AdwMessageDialog to prompt the user if they are
        # SURE they want to cancel creation. For now, the window will not
        # react if the user attempts to close the window while a bottle
        # is being created in a feature update
        self.close()
