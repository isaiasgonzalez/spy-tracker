import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GitLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='spy git test ')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'checkout'
        self.remote = Path(self.temp.name) / 'remote.git'
        self.repo.mkdir()
        self.git('init', '--bare', str(self.remote))
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Launcher Test')
        self.git('config', 'user.email', 'launcher@example.test')
        for name in ['script.py', 'market_hours.py', 'weights.py', 'spy500.csv',
                     'SPY_componentes_base.json', 'SPY_data.json']:
            (self.repo / name).write_bytes((ROOT / name).read_bytes())
        self.git('add', '.')
        self.git('commit', '-m', 'Initial fixture')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-u', 'origin', 'main')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def launch(self):
        return subprocess.run(['bash', str(ROOT / 'Actualizar-Pesos-Git'),
                               '--repo', str(self.repo), '--python', sys.executable,
                               '--no-pause'], capture_output=True, text=True)

    def test_real_weights_command_and_push_to_local_remote(self):
        text = (self.repo / 'spy500.csv').read_text()
        rows = list(csv.reader(io.StringIO(text)))
        rows[1][-1] = str(float(rows[1][-1]) + .01)
        buffer = io.StringIO()
        csv.writer(buffer).writerows(rows)
        (self.repo / 'spy500.csv').write_text(buffer.getvalue())
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        local = self.git('rev-parse', 'HEAD')
        remote = self.git('--git-dir', str(self.remote), 'rev-parse', 'refs/heads/main')
        self.assertEqual(local, remote)
        base = json.loads((self.repo / 'SPY_componentes_base.json').read_text())
        feed = json.loads((self.repo / 'SPY_data.json').read_text())
        self.assertEqual(base['componentes'][0]['peso_pct'], float(rows[1][-1]))
        self.assertEqual(feed['componentes'][0]['peso_pct'], float(rows[1][-1]))
        self.assertEqual(self.git('diff', '--name-only', 'HEAD~', 'HEAD').splitlines(),
                         ['SPY_componentes_base.json', 'SPY_data.json', 'spy500.csv'])
        # Running again executes pesos but does not publish a timestamp-only commit.
        again = self.launch()
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), local)

    def test_invalid_csv_does_not_commit_or_push(self):
        original = self.git('rev-parse', 'HEAD')
        (self.repo / 'spy500.csv').write_text('Ticker,Weight\nAAPL,NaN\n')
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), original)
        self.assertEqual(self.git('--git-dir', str(self.remote), 'rev-parse', 'refs/heads/main'), original)

    def test_unrelated_staged_change_is_preserved(self):
        (self.repo / 'other.txt').write_text('user work')
        self.git('add', 'other.txt')
        original = self.git('rev-parse', 'HEAD')
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), original)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), 'other.txt')
