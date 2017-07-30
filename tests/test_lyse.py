import os
import six
if six.PY2:
    import mock
else:
    import unittest.mock as mock

from lyse.tests import LyseTestCase, analysislib
from testing_utils import monkeypatch



class LyseTests(LyseTestCase):

    def test_add_routine(self):

        from qtutils.qt import QtWidgets
        from qtutils import inmain

        routine = os.path.join(analysislib, 'test_singleshot_routine.py')
        mock_file_open = mock.Mock(return_value=[routine])
        
        with monkeypatch(QtWidgets.QFileDialog, 'getOpenFileNames', mock_file_open):
            inmain(self.app.singleshot_routinebox.ui.toolButton_add_routines.click)

        import time
        time.sleep(2)

        self.quit_lyse()
        self.start_lyse()
        

if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=3)
