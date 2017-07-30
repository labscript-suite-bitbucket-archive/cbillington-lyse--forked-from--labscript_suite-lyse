import os
import unittest

this_dir = os.path.dirname(os.path.abspath(__file__))

test_suite = unittest.TestLoader().discover(this_dir)

if __name__ == '__main__':
    test_runner = unittest.TextTestRunner(verbosity=3)
    test_runner.run(test_suite)