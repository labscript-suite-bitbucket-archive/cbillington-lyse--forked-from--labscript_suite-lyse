import os
import six
if six.PY2:
    import mock
else:
    import unittest.mock as mock

from lyse.tests import LyseTestCase, analysislib
from labscript_utils.testing_utils import monkeypatch, ANY

from qtutils.qt import QtWidgets, QtCore, QtGui
from qtutils import inmain, inmain_decorator


FOO_SINGLESHOT = os.path.join(analysislib, 'foo_singleshot.py')
BAR_SINGLESHOT = os.path.join(analysislib, 'bar_singleshot.py')
FOO_MULTISHOT = os.path.join(analysislib, 'foo_multishot.py')
BAR_MULTISHOT = os.path.join(analysislib, 'bar_multishot.py')



class LyseTests(LyseTestCase):

    def send_key(self, key, modifiers=QtCore.Qt.NoModifier):
        """Send a keypress and key release event to the application"""
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers)
        QtCore.QCoreApplication.postEvent(self.app.ui, event)
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyRelease, key, modifiers)
        QtCore.QCoreApplication.postEvent(self.app.ui, event)
        inmain(QtCore.QCoreApplication.sendPostedEvents, self.app.ui)
        
    @inmain_decorator()
    def set_treeview_selection(self, treeview, model, rows):
        """set the selected rows of a treeview with a given model."""
        # Select the items:
        selection_model = treeview.selectionModel()
        selection_model.clearSelection()
        for row in rows:
            model_index = model.index(row, 0)
            selection_model.select(model_index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)

        # Verify:
        selected_indexes = treeview.selectedIndexes()
        selected_rows = set(index.row() for index in selected_indexes)
        self.assertEqual(selected_rows, set(rows))

    @inmain_decorator()
    def add_routines(self, routinebox, paths, expected_file_open_dir=None):
        """Add routines by list of filepaths by simulating mouse-click of the
        add routine button and mocking the file open dialog. Verify the
        routine has been added. If expected_file_open_dir provided, check that
        the file open dialog was called with that directory"""

        assert routinebox in [self.app.singleshot_routinebox,
                              self.app.multishot_routinebox]

        # Mock the file open dialog and simulate the mouse click:
        mock_file_open = mock.Mock(return_value=paths)
        with monkeypatch(QtWidgets.QFileDialog, 'getOpenFileNames', mock_file_open):
            routinebox.ui.toolButton_add_routines.click()

        # Verify the right directory was provided:
        mock_file_open.assert_called_with(ANY, ANY, expected_file_open_dir, ANY)

        for i, path in enumerate(paths):
            # Verify the routine was added to the model:
            row = routinebox.model.rowCount() - len(paths) + i
            active_item = routinebox.model.item(row, routinebox.COL_ACTIVE)
            name_item = routinebox.model.item(row, routinebox.COL_NAME)
            self.assertEqual(active_item.checkState(), QtCore.Qt.Checked)
            self.assertEqual(name_item.text(), os.path.basename(path))

            # Verify the routine object was added to the list and some of its attributes:
            routine_instance = routinebox.routines[- len(paths) + i]
            self.assertEqual(routine_instance.filepath, path)
            self.assertTrue(routine_instance.enabled())

    def remove_routines(self, routinebox, rows, method='button'):
        """Remove routines by selecting them and then simulating a mouse-click
        of the remove selection button or keypress of delete keyboard shortcut
        (with or without shift held). Verify the routines have been
        removed."""
        assert method in ['button', 'delete', 'shift-delete']
        assert routinebox in [self.app.singleshot_routinebox,
                              self.app.multishot_routinebox]
        routines = [routinebox.routines[row] for row in rows]

        paths = [routine.filepath for routine in routines]

        inmain(self.set_treeview_selection, routinebox.ui.treeView, routinebox.model, rows)

        mock_question = mock.Mock(return_value=QtWidgets.QMessageBox.Yes)
        message = "Remove %d routines?" % len(rows)
        with monkeypatch(QtWidgets.QMessageBox, 'question', mock_question):
            if method == 'button':
                inmain(routinebox.ui.toolButton_remove_routines.click)
                mock_question.assert_called_with(ANY, ANY, message, ANY)
            elif method == 'delete':
                inmain(routinebox.ui.treeView.setFocus)
                self.send_key(QtCore.Qt.Key_Delete)
                mock_question.assert_called_with(ANY, ANY, message, ANY)
            elif method == 'shift-delete':
                inmain(routinebox.ui.treeView.setFocus)
                self.send_key(QtCore.Qt.Key_Delete, modifiers=QtCore.Qt.ShiftModifier)
                mock_question.assert_not_called()

        # Wait for them to go:
        for routine in routines:
            self.wait_for(lambda: routine.worker.returncode is not None and not routine.exiting, timeout=5)

         # Verify they're gone:
        remaining_paths = set(routine.filepath for routine in routinebox.routines)
        self.assertFalse(remaining_paths.intersection(set(paths)))


    def test_add_remove_routines(self):

        # Single shot:
        self.add_routines(self.app.singleshot_routinebox,
                          [FOO_SINGLESHOT, BAR_SINGLESHOT],
                         expected_file_open_dir=analysislib)

        # Test removing with buttonpress:
        self.remove_routines(self.app.singleshot_routinebox, [0, 1], method='button')

        # Multi shot:
        self.add_routines(self.app.multishot_routinebox,
                          [FOO_MULTISHOT, BAR_MULTISHOT],
                         expected_file_open_dir=analysislib)
        
        # Test removing with delete and shift delete:
        self.remove_routines(self.app.multishot_routinebox, [0], method='delete')
        self.remove_routines(self.app.multishot_routinebox, [0], method='shift-delete')


if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=3)
