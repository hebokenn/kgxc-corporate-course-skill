"""Isolated before-write refusal tests; not an actual desktop installation."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime_guard_installer', ROOT/'scripts/install_plugin.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallRuntimeGuard(unittest.TestCase):
    def check_refusal(self, main_app, process_line):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            dsh_home = home/'.dsh'
            process_line = process_line.replace('INSTALL_ROOT',str(dsh_home/'profiles/desktop/node_modules/kgxc-course-plugin'))
            with patch.object(installer.Path,'home',return_value=home), \
                 patch.dict(os.environ,{'DSH_HOME':str(dsh_home)}), \
                 patch.object(installer.subprocess,'run',return_value=subprocess.CompletedProcess([],0 if main_app else 1)) as run, \
                 patch.object(installer.subprocess,'check_output',return_value=process_line), \
                 patch.object(installer,'local_package') as package:
                with self.assertRaisesRegex(ValueError,'DSH_RUNTIME_ACTIVE'):
                    installer.dsh('unused-package-manager','desktop')
                package.assert_not_called()
                self.assertEqual(run.call_count,1)  # pgrep only; no package manager
                self.assertEqual(list(home.iterdir()),[])  # refusal precedes mkdir/backup/config writes

    def test_main_app_prevents_install_before_any_write(self):
        self.check_refusal(True,'')

    def test_live_backend_prevents_install_with_main_app_closed(self):
        self.check_refusal(False,'97524 /usr/bin/python3 INSTALL_ROOT/skills/corporate-training-motion/scripts/workbench.py serve audit-course\n')


if __name__ == '__main__':
    unittest.main()
