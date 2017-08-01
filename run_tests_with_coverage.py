from __future__ import unicode_literals, print_function, division
import subprocess
import sys
import os
import errno

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

cmds = [sys.executable, '-c', 'import site; print(site.getusersitepackages())']
user_site = subprocess.check_output(cmds).decode('utf8').strip()
if not os.path.exists(user_site):
    mkdir_p(user_site)

path_file = os.path.join(user_site, 'coverage.pth')

import coverage
coverage_import_path = os.path.dirname(os.path.dirname(os.path.abspath(coverage.__file__)))
environ = os.environ.copy()
environ['COVERAGE_PROCESS_START'] = 'coveragerc'

try:
    with open(path_file, 'w') as f:
        f.write("import sys; sys.path.insert(0, '{}')\n".format(coverage_import_path))
        f.write("import coverage; coverage.process_startup()" + '\n')
    subprocess.call([sys.executable, 'tests/run_tests.py'], env=environ)
finally:
    try:
        os.unlink(path_file)
    except OSError:
        pass
try:
    print('processing coverage data...')
    subprocess.call([sys.executable, '-m', 'coverage', 'combine'])
    subprocess.call([sys.executable, '-m', 'coverage', 'html', '--rcfile=coveragerc'])
    subprocess.call([sys.executable, '-m', 'coverage', 'erase'])
    print('done')
except Exception:
    pass
