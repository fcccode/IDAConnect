# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import datetime
import logging
import uuid
from functools import partial

import ida_kernwin
import idaapi
import idautils
import idc

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import qApp, QProgressDialog, QMessageBox

from ..shared.commands import (GetRepositories, GetBranches,
                               NewRepository, NewBranch,
                               DownloadDatabase, UploadDatabase,
                               Subscribe)
from ..shared.models import Repository, Branch
from ..utilities.misc import local_resource
from .dialogs import OpenDialog, SaveDialog

logger = logging.getLogger('IDAConnect.Interface')


class Action(object):
    """
    This is a base class for all the actions of the interface module.
    """
    _ACTION_ID = None

    def __init__(self, menu, text, tooltip, icon, handler):
        """
        Initialize the action.

        :param menu: the menu to attach to
        :param text: the text to display
        :param tooltip: the tooltip to show
        :param icon: the path to the icon
        :param handler: the action handler
        """
        super(Action, self).__init__()
        self._menu = menu
        self._text = text
        self._tooltip = tooltip
        self._icon = icon
        self._handler = handler

        self._iconId = idaapi.BADADDR

    def install(self):
        """
        Install the action into the IDA UI.

        :return: did the install succeed
        """
        # Read and load the icon file
        iconData = str(open(self._icon, 'rb').read())
        self._iconId = idaapi.load_custom_icon(data=iconData)

        # Create the action description
        actionDesc = idaapi.action_desc_t(self._ACTION_ID, self._text,
                                          self._handler, None, self._tooltip,
                                          self._iconId)

        # Register the action using its description
        result = idaapi.register_action(actionDesc)
        if not result:
            raise RuntimeError("Failed to register action")

        # Attach the action to the chosen menu
        result = idaapi.attach_action_to_menu(self._menu, self._ACTION_ID,
                                              idaapi.SETMENU_APP)
        if not result:
            raise RuntimeError("Failed to attach action")

        logger.debug("Installed the action")
        return True

    def uninstall(self):
        """
        Uninstall the action from the IDA UI.

        :return: did the uninstall succeed
        """
        # Detach the action from the chosen menu
        result = idaapi.detach_action_from_menu(self._menu, self._ACTION_ID)
        if not result:
            return False

        # Un-register the action using its id
        result = idaapi.unregister_action(self._ACTION_ID)
        if not result:
            return False

        # Free the custom icon using its id
        idaapi.free_custom_icon(self._iconId)
        self._iconId = idaapi.BADADDR

        logger.debug("Uninstalled the action")
        return True

    def update(self):
        """
        Force to update the action's state (enabled/disabled).
        """
        ida_kernwin.update_action_state(self._ACTION_ID,
                                        self._handler.update(None))


class ActionHandler(idaapi.action_handler_t):
    """
    This is the base class for all action handlers of the interface module.
    """

    def __init__(self, plugin):
        """
        Initialize the action handler.

        :param plugin: the plugin instance
        """
        super(ActionHandler, self).__init__()
        self._plugin = plugin

    def update(self, ctx):
        """
        Update the state of the associated action.

        :param ctx: the context
        :return: should the action be enabled or not
        """
        if self._plugin.network.connected:
            return idaapi.AST_ENABLE
        return idaapi.AST_DISABLE


class OpenAction(Action):
    """
    The "Open from server..." action installed in the "File" menu.
    """
    _ACTION_ID = 'idaconnect:open'

    def __init__(self, plugin):
        super(OpenAction, self).__init__(
            'File/Open',
            'Open from server...',
            'Load a database from server',
            plugin.resource('download.png'),
            OpenActionHandler(plugin))


class OpenActionHandler(ActionHandler):
    """
    The action handler for the open action.
    """

    @staticmethod
    def _progress_callback(progress, count, total):
        """
        Called when some data from the file has been received.

        :param progress: the progress dialog
        :param count: the number of bytes received
        :param total: the total number of bytes to receive
        """
        progress.setRange(0, total)
        progress.setValue(count)

    def activate(self, ctx):
        """
        Called when the action is triggered.

        :param ctx: the context
        :return: refresh or not the IDA windows
        """
        # Ask the server for the list of repositories
        d = self._plugin.network.send_packet(GetRepositories.Query())
        d.add_callback(self._on_get_repository_reply)
        d.add_errback(logger.exception)
        return 1

    def _on_get_repository_reply(self, reply):
        """
        Called when the list of repositories is received.

        :param reply: the reply from the server
        """
        # Ask the server for the list of branches
        d = self._plugin.network.send_packet(GetBranches.Query())
        d.add_callback(partial(self._on_get_branches_reply, reply.repos))
        d.add_errback(logger.exception)

    def _on_get_branches_reply(self, repos, reply):
        """
        Called when the list of branches is received.

        :param repos: the list of repositories
        :param reply: the reply from the server
        """
        dialog = OpenDialog(self._plugin, repos, reply.branches)
        dialog.accepted.connect(partial(self._dialog_accepted, dialog))
        dialog.exec_()

    def _dialog_accepted(self, dialog):
        """
        Called when the open dialog is accepted by the user.

        :param dialog: the open dialog
        """
        repo, branch = dialog.get_result()

        # Create the progress dialog
        text = "Downloading database from server, please wait..."
        progress = QProgressDialog(text, "Cancel", 0, 1)
        progress.setCancelButton(None)  # Remove cancel button
        progress.setModal(True)  # Set as a modal dialog
        windowFlags = progress.windowFlags()  # Disable close button
        progress.setWindowFlags(windowFlags & ~Qt.WindowCloseButtonHint)
        progress.setWindowTitle("Open from server")
        iconPath = self._plugin.resource('download.png')
        progress.setWindowIcon(QIcon(iconPath))

        # Send a packet to download the database
        packet = DownloadDatabase.Query(repo.hash, branch.uuid)
        callback = partial(self._progress_callback, progress)

        def setDownloadCallback(reply):
            reply.downback = callback

        d = self._plugin.network.send_packet(packet)
        d.add_initback(setDownloadCallback)
        d.add_callback(partial(self._database_downloaded, branch, progress))
        d.add_errback(logger.exception)
        progress.show()

    def _database_downloaded(self, branch, progress, reply):
        """
        Called when the file has been downloaded.

        :param branch: the branch
        :param progress: the progress dialog
        :param reply: the reply from the server
        """
        # Close the progress dialog
        self._progress_callback(progress, 1, 1)

        # Get the absolute path of the file
        fileName = branch.uuid + ('.i64' if branch.bits == 64 else '.idb')
        filePath = local_resource('files', fileName)

        # Write the packet content to disk
        with open(filePath, 'wb') as outputFile:
            outputFile.write(reply.content)
        logger.info("Saved file %s" % fileName)

        # Show a success dialog
        # success = QMessageBox()
        # success.setIcon(QMessageBox.Information)
        # success.setStandardButtons(QMessageBox.Ok)
        # success.setText("Database successfully downloaded!")
        # success.setWindowTitle("Open from server")
        # iconPath = self._plugin.getResource('download.png')
        # success.setWindowIcon(QIcon(iconPath))
        # success.exec_()

        # Save the old database
        idbPath = idc.GetIdbPath()
        if idbPath:
            idc.save_database(idbPath, 0)
        # Save the current state
        self._plugin.core.save_state(idbPath)
        # Open the new database
        QProcess.startDetached(qApp.applicationFilePath(), [filePath])
        qApp.quit()  # FIXME: Find an alternative, if any


class SaveAction(Action):
    """
    The "Save to server..." action installed in the "File" menu.
    """
    _ACTION_ID = 'idaconnect:save'

    def __init__(self, plugin):
        super(SaveAction, self).__init__(
            'File/Save',
            'Save to server...',
            'Save a database to server',
            plugin.resource('upload.png'),
            SaveActionHandler(plugin))


class SaveActionHandler(ActionHandler):
    """
    The action handler for the save action.
    """

    @staticmethod
    def _progress_callback(progress, count, total):
        """
        Called when some data from the file has been sent.

        :param progress: the progress dialog
        :param count: the number of bytes sent
        :param total: the total number of bytes to send
        """
        progress.setRange(0, total)
        progress.setValue(count)

    def update(self, ctx):
        if not idc.GetIdbPath():
            return idaapi.AST_DISABLE
        return super(SaveActionHandler, self).update(ctx)

    def activate(self, ctx):
        """
        Called when the action is triggered.

        :param ctx: the context
        :return: refresh or not the IDA windows
        """
        # Ask the server for the list of repositories
        d = self._plugin.network.send_packet(GetRepositories.Query())
        d.add_callback(self._on_get_repository_reply)
        d.add_errback(logger.exception)
        return 1

    def _on_get_repository_reply(self, reply):
        """
        Called when the list of repositories is received.

        :param reply: the reply from the server
        """
        # Ask the server for the list of branches
        d = self._plugin.network.send_packet(GetBranches.Query())
        d.add_callback(partial(self._on_get_branches_reply, reply.repos))
        d.add_errback(logger.exception)

    def _on_get_branches_reply(self, repos, reply):
        """
        Called when the list of branches is received.

        :param repos: the list of repositories
        :param reply: the reply from the server
        """
        dialog = SaveDialog(self._plugin, repos, reply.branches)
        dialog.accepted.connect(partial(self._dialog_accepted, dialog))
        dialog.exec_()

    def _dialog_accepted(self, dialog):
        """
        Called when the save dialog is accepted by the user.

        :param dialog: the save dialog
        """
        repo, branch = dialog.get_result()

        # Create new repository if necessary
        if not repo:
            hash = idautils.GetInputFileMD5()
            file = idc.GetInputFile()
            type = idaapi.get_file_type_name()
            dateFormat = "%Y/%m/%d %H:%M"
            date = datetime.datetime.now().strftime(dateFormat)
            repo = Repository(hash, file, type, date)
            d = self._plugin.network.send_packet(NewRepository.Query(repo))
            d.add_callback(partial(self._on_new_repository_reply,
                                   repo, branch))
            d.add_errback(logger.exception)
        else:
            self._on_new_repository_reply(repo, branch, None)

    def _on_new_repository_reply(self, repo, branch, _):
        self._plugin.core.repo = repo.hash

        # Create new branch if necessary
        if not branch:
            uuid_ = str(uuid.uuid4())
            dateFormat = "%Y/%m/%d %H:%M"
            date = datetime.datetime.now().strftime(dateFormat)
            branch = Branch(uuid_, repo.hash, date, 64 if idc.__EA64__ else 32)
            d = self._plugin.network.send_packet(NewBranch.Query(branch))
            d.add_callback(partial(self._on_new_branch_reply, repo, branch))
            d.add_errback(logger.exception)
        else:
            self._on_new_branch_reply(repo, branch, None)

    def _on_new_branch_reply(self, repo, branch, _):
        self._plugin.core.branch = branch.uuid

        # Save the current database
        self._plugin.core.save_netnode()
        idc.save_database(idc.GetIdbPath(), 0)

        # Create the packet that will hold the database
        packet = UploadDatabase.Query(repo.hash, branch.uuid)
        inputPath = idc.GetIdbPath()
        with open(inputPath, 'rb') as inputFile:
            packet.content = inputFile.read()

        # Create the progress dialog
        text = "Uploading database to server, please wait..."
        progress = QProgressDialog(text, "Cancel", 0, len(packet.content))
        progress.setCancelButton(None)  # Remove cancel button
        progress.setModal(True)  # Set as a modal dialog
        windowFlags = progress.windowFlags()  # Disable close button
        progress.setWindowFlags(windowFlags & ~Qt.WindowCloseButtonHint)
        progress.setWindowTitle("Save to server")
        iconPath = self._plugin.resource('upload.png')
        progress.setWindowIcon(QIcon(iconPath))
        progress.show()

        # Send the packet to upload the file
        packet.upback = partial(self._progress_callback, progress)
        d = self._plugin.network.send_packet(packet)
        d.add_callback(partial(self._database_uploaded, repo, branch))
        d.add_errback(logger.exception)

    def _database_uploaded(self, repo, branch, _):
        # Show a success dialog
        success = QMessageBox()
        success.setIcon(QMessageBox.Information)
        success.setStandardButtons(QMessageBox.Ok)
        success.setText("Database successfully uploaded!")
        success.setWindowTitle("Save to server")
        iconPath = self._plugin.resource('upload.png')
        success.setWindowIcon(QIcon(iconPath))
        success.exec_()

        # Subscribe to the new events stream
        self._plugin.network.send_packet(Subscribe(repo.hash, branch.uuid,
                                                   self._plugin.core.tick))
        self._plugin.core.hook_all()
