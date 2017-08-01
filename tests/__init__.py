import sys
import os
import threading
import shutil

from qtutils.qt import QtCore
from qtutils import inmain

from labscript_utils.testing_utils import ThreadTestCase
from labscript_utils import labscript_suite_install_dir
from labscript_utils.labconfig import LabConfig
import labscript_utils.labconfig

this_dir = os.path.dirname(os.path.abspath(__file__))
scratch_dir = os.path.join(this_dir, "scratch")
lyse_main_path = os.path.join(labscript_suite_install_dir, 'lyse', '__main__.py')

experiment_name = "test_experiment"
shared_drive = os.path.join(scratch_dir, "test_shared_drive")
analysislib = os.path.join(this_dir, "test_analysislib")
mock_labconfig_path = os.path.join(scratch_dir, "mock_labconfig.ini")

mock_labconfig_contents = """
[DEFAULT]
experiment_name = {experiment_name}
shared_drive = {shared_drive}
experiment_shot_storage = %(shared_drive)s/Experiments/%(experiment_name)s
labscript_suite = {labscript_suite}
labscriptlib = %(labscript_suite)s/userlib/labscriptlib/%(experiment_name)s
analysislib = {analysislib}
pythonlib = %(labscript_suite)s/userlib/pythonlib

[servers]
zlock = localhost

[ports]
blacs = 42517
lyse = 42519
mise = 42520
runviewer = 42521
zlock = 7339

[programs]
text_editor = subl
text_editor_arguments = {{file}}
hdf5_viewer = hdfview
hdf5_viewer_arguments = {{file}}

[paths]
connection_table_h5 = %(experiment_shot_storage)s/connectiontable.h5
connection_table_py = %(labscriptlib)s/connectiontable.py

[runmanager]
autoload_config_file = %(experiment_shot_storage)s/runmanager.ini
output_folder_format = %%Y/%%m/%%d

[lyse]
autoload_config_file = %(experiment_shot_storage)s/lyse.ini
""".format(experiment_name=experiment_name,
           shared_drive=shared_drive,
           labscript_suite=labscript_suite_install_dir,
           analysislib=analysislib)

def mkdir_p(path):
    import errno
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


class LyseTestCase(ThreadTestCase):

    def setUp(self):
        """Create the testing environment lyse will run in"""
        
        # Monkey patch the labconfig module to use our mock labconfig file:
        try:
            class MockLabConfig(LabConfig):
                def __init__(self, config_path=mock_labconfig_path,
                             required_params={}, defaults={}):
                    LabConfig.__init__(self, mock_labconfig_path,
                                       required_params, defaults)

            labscript_utils.labconfig.LabConfig = MockLabConfig

            # Make the experiment shot storage folder and ancestor directories:
            mkdir_p(os.path.join(shared_drive, 'Experiments', experiment_name))

            # Write the fake labconfig file:
            with open(mock_labconfig_path, 'w') as f:
                f.write(mock_labconfig_contents)

            self.start_lyse()

        except Exception:
            self.tearDown()
            raise

    def start_lyse(self):

        globals_dict = self.run_script_as_main(lyse_main_path)

        # Wait for the Lyse() instance to exist:
        self.wait_for(lambda: 'app' in globals_dict)

        # Get a reference to the lyse main module:
        self.__main__ = globals_dict
        # Get a reference to the lyse app:
        self.app = self.__main__.app
        
        # Wait for qt event loop to be capable of processing events:
        ready = threading.Event()
        timer = inmain(QtCore.QTimer.singleShot, 0, ready.set)
        ready.wait()

    def quit_lyse(self):
        if hasattr(self, 'app'):
            inmain(self.app.ui.close)

    def tearDown(self):
        try:
            if hasattr(self, 'app') and not inmain(self.app.ui.isActiveWindow):
                raise RuntimeError("Must leave lyse window as active window during testing")
        finally:
            try:
                self.quit_lyse()
            except Exception:
                pass

            # Delete testing scratch directory and all its contents:
            try:
                shutil.rmtree(scratch_dir)
            except OSError:
                pass
            # Restore labconfig to normal:
            labscript_utils.labconfig.LabConfig = LabConfig

            # Quit the mainloop:
            self.quit_mainloop()
        
        


