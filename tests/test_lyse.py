from __future__ import print_function
import os
import time
from datetime import datetime, timedelta
from labscript_utils import PY2
if PY2:
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

from runmanager import generate_sequence_id, make_run_files

class FakeBLACS(object):
    """a class that "runs" shot files, adding run time and other attributes.
    Increments the run time by 30 seconds each time it is run, starting at the
    present (this means it returns run times in the future)"""
    _run_time = datetime.now()
   
    @classmethod
    def run_time(cls):
        """Increment the current run time by 30 seconds and return it as a
        struct time tuple"""
        cls._run_time += timedelta(seconds=30)
        return cls._run_time.timetuple()

    @classmethod
    def run(cls, shot_file):
        import h5py
        """Add the minimal data that BLACS would add to a shot file"""
        with h5py.File(shot_file) as f:
            data_group = f.create_group('data')
            # stamp with the run time of the experiment
            f.attrs['run time'] = time.strftime('%Y%m%dT%H%M%S', cls.run_time())


def make_shot_files(py_name, shot_globals=({},)):
    """Generate a list of HDF files given"""
    from labscript_utils.labconfig import LabConfig
    storage = LabConfig().get('paths', 'experiment_shot_storage')
    sequence_id = generate_sequence_id(py_name)
    shot_files = list(make_run_files(storage, sequence_globals=None,
                                     shots=shot_globals,
                                     sequence_id=sequence_id))
    for shot_file in shot_files:
        FakeBLACS.run(shot_file)

    return shot_files

def submit_to_lyse(h5_filename):
    # Send the hdf5 file to lyse, assuming it is running on localhost:
    from labscript_utils.labconfig import LabConfig
    import zprocess
    config = LabConfig()
    port = int(config.get('ports','lyse'))
    data = {'filepath': os.path.abspath(h5_filename)}
    response = zprocess.zmq_get(port, 'localhost', data)
    if response != 'added successfully':
        raise Exception(response)

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
            flags = QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows
            selection_model.select(model_index, flags)

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
        if expected_file_open_dir is not None:
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
            self.wait_for(lambda: (routine.worker.returncode is not None and
                                   not routine.exiting),timeout=5)

         # Verify they're gone:
        remaining_paths = set(routine.filepath for routine in routinebox.routines)
        self.assertFalse(remaining_paths.intersection(set(paths)))

    def add_shots(self, shots, method='button', expected_file_open_dir=None):
        assert method in ['button', 'server']
        assert not (method == 'button' and expected_file_open_dir is not None)

        initial_nshots = inmain(self.app.filebox.shots_model._model.rowCount)

        # Mock the file open dialog and simulate the mouse click:
        if method == 'button':
            mock_file_open = mock.Mock(return_value=shots)
            with monkeypatch(QtWidgets.QFileDialog, 'getOpenFileNames', mock_file_open):
                inmain(self.app.filebox.ui.toolButton_add_shots.click)
            # Verify the right directory was provided:
            if expected_file_open_dir is not None:
                mock_file_open.assert_called_with(ANY, ANY, expected_file_open_dir, ANY)
        elif method == 'server':
            for shot in shots:
                submit_to_lyse(shot)

        def done():
            nshots = inmain(self.app.filebox.shots_model._model.rowCount)
            return nshots == initial_nshots + len(shots)

        # Wait for them to be processed:
        self.wait_for(done)

    def set_visible_columns(self, column_names):
        """Set the visible columns by simulating interaction with the
        set columns dialog"""
        inmain(self.app.filebox.ui.pushButton_edit_columns.click)
        dialog = self.app.filebox.edit_columns_dialog

        # uncheck all columns
        inmain(dialog.select_all_checkbox.setCheckState, QtCore.Qt.Unchecked)

        # Look for our columns and check them:
        for i in range(inmain(dialog.model.rowCount)):
            name_item = inmain(dialog.model.item, i, dialog.COL_NAME)
            if inmain(name_item.text) in column_names:
                visible_item = inmain(dialog.model.item, i, dialog.COL_VISIBLE)
                inmain(visible_item.setCheckState, QtCore.Qt.Checked)

        # Click 'ok':
        inmain(dialog.ui.pushButton_make_it_so.click)

        # Check that these columns are the visible ones:
        model = self.app.filebox.shots_model._model
        view = self.app.filebox.shots_model._view
        for i in range(inmain(model.columnCount)):
            header_item = inmain(model.horizontalHeaderItem, i)
            if i == self.app.filebox.shots_model.COL_STATUS:
                continue
            if inmain(header_item.text).strip() not in column_names:
                self.assertTrue(inmain(view.isColumnHidden, i))
            else:
                self.assertFalse(inmain(view.isColumnHidden, i))
    def test_basic(self):

        # Add single shot rouines:
        self.add_routines(self.app.singleshot_routinebox,
                          [FOO_SINGLESHOT, BAR_SINGLESHOT],
                         expected_file_open_dir=analysislib)

        # Add multi shot routines:
        self.add_routines(self.app.multishot_routinebox,
                          [FOO_MULTISHOT, BAR_MULTISHOT],
                         expected_file_open_dir=analysislib)
        
        # pause analysis so the shots don't run immediately:
        self.app.filebox.pause_analysis()

        # Add some shots by file dialog:
        shot_files_foo = make_shot_files('foo.py', shot_globals=[{'x': i} for i in range(5)])
        self.add_shots(shot_files_foo, method='button')

        # Add some shots by network:
        shot_files_bar = make_shot_files('bar.py', shot_globals=[{'y': i**2} for i in range(5)])
        self.add_shots(shot_files_bar, method='server')

        # Make the columns dialog only show 'x' and 'y':
        self.set_visible_columns(['x', 'y'])

        # Remove the single-shot routines by button press:
        self.remove_routines(self.app.singleshot_routinebox, [0, 1], method='button')

        # Remove the multi shot routines by keyboard shortcuts:
        self.remove_routines(self.app.multishot_routinebox, [0], method='delete')
        self.remove_routines(self.app.multishot_routinebox, [0], method='shift-delete')

        

if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=3)
