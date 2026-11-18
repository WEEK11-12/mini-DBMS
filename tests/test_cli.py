import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mini_dbms.cli import main
from mini_dbms.storage import TableStore, initialize

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'data'
        self.sql_path = Path(self.temp.name) / 'queries.sql'

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, '-W', 'error::ResourceWarning', '-m', 'mini_dbms', *map(str, args)],
            cwd=ROOT, capture_output=True, encoding='utf-8', timeout=10,
            env={**os.environ, 'PYTHONUTF8': '1'},
        )

    def run_sql(self, sql):
        if isinstance(sql, bytes):
            self.sql_path.write_bytes(sql)
        else:
            self.sql_path.write_text(sql, encoding='utf-8')
        return self.run_cli('run', self.sql_path, '--data-dir', self.directory)

    def test_init_run_restart_and_query_in_separate_processes(self):
        initialized = self.run_cli('init', '--data-dir', self.directory)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        first = self.run_sql("INSERT INTO users (name, age) VALUES ('영희', 25);"
                             'SELECT name FROM users WHERE id = 1;')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual([json.loads(line) for line in first.stdout.splitlines()], [
            {'inserted_id': 1, 'affected_rows': 1}, {'columns': ['name']},
            ['영희'], {'row_count': 1},
        ])
        second = self.run_sql("INSERT INTO users (name, age) VALUES ('철수', 28);"
                              'SELECT * FROM users;')
        self.assertEqual(second.returncode, 0, second.stderr)
        output = [json.loads(line) for line in second.stdout.splitlines()]
        self.assertEqual(output[0]['inserted_id'], 2)
        self.assertEqual(output[2:4], [[1, '영희', 25], [2, '철수', 28]])
        self.assertEqual(output[-1], {'row_count': 2})

    def test_first_failure_stops_file_and_preserves_first_success(self):
        initialize(self.directory)
        result = self.run_sql("INSERT INTO users (name, age) VALUES ('first', 1);"
                              "INSERT INTO users (name, age) VALUES ('bad');"
                              "INSERT INTO users (name, age) VALUES ('later', 3);")
        self.assertEqual(result.returncode, 1)
        self.assertIn('[schema]', result.stderr)
        self.assertIn('statement 2', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual([json.loads(s) for s in (self.directory/'users.jsonl').read_text().splitlines()],
                         [{'id': 1, 'name': 'first', 'age': 1}])

    def test_later_lexical_and_utf8_errors_preserve_previous_insert(self):
        for suffix in [b"SELECT * FROM users", b"SELECT * FROM users WHERE name = 'unclosed;",
                       b'\xff\nSELECT * FROM users;']:
            with self.subTest(suffix=suffix):
                if not self.directory.exists():
                    initialize(self.directory)
                (self.directory/'users.jsonl').write_bytes(b'')
                result = self.run_sql(
                    b"INSERT INTO users (name, age) VALUES ('first', 1);\n" + suffix)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('statement 2', result.stderr)
                self.assertEqual(len((self.directory/'users.jsonl').read_bytes().splitlines()), 1)

    def test_missing_input_and_table_are_reported_without_creating_files(self):
        missing = self.run_cli('run', self.sql_path, '--data-dir', self.directory)
        self.assertEqual(missing.returncode, 1)
        self.assertIn('[input]', missing.stderr)
        self.assertFalse(self.directory.exists())
        result = self.run_sql('SELECT * FROM users;')
        self.assertEqual(result.returncode, 1)
        self.assertIn('[storage]', result.stderr)
        self.assertFalse((self.directory/'users.jsonl').exists())

    def test_utf8_error_after_semicolon_on_same_line_keeps_prior_insert(self):
        initialize(self.directory)
        result = self.run_sql(
            b"INSERT INTO users (name, age) VALUES ('first', 1);\xff"
            b"INSERT INTO users (name, age) VALUES ('later', 2);")
        self.assertEqual(result.returncode, 1)
        self.assertIn('[input]', result.stderr)
        self.assertIn('statement 2', result.stderr)
        self.assertEqual([json.loads(line) for line in
                          (self.directory/'users.jsonl').read_bytes().splitlines()],
                         [{'id': 1, 'name': 'first', 'age': 1}])

    def test_existing_file_and_corruption_are_never_overwritten(self):
        initialize(self.directory)
        path = self.directory/'users.jsonl'
        raw = b'{"id":1'
        path.write_bytes(raw)
        result = self.run_cli('init', '--data-dir', self.directory)
        self.assertEqual(result.returncode, 1)
        result = self.run_sql('SELECT * FROM users;')
        self.assertEqual(result.returncode, 1)
        self.assertIn('[corruption]', result.stderr)
        self.assertIn('line 1, byte 0', result.stderr)
        self.assertEqual(path.read_bytes(), raw)

    def test_cli_returns_usage_error_and_accepts_empty_sql_file(self):
        self.assertEqual(self.run_cli('unknown').returncode, 2)
        initialize(self.directory)
        result = self.run_sql(' ; \n ; ')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_partial_select_has_no_success_completion_and_stops(self):
        initialize(self.directory)
        store = TableStore(self.directory)
        self.addCleanup(store.close)
        store.append({'name': 'first', 'age': 1})
        with store.path.open('ab') as target:
            target.write(b'broken\n')
        self.sql_path.write_text("SELECT * FROM users; INSERT INTO users (name,age) VALUES ('later',2);",
                                 encoding='utf-8')
        out, err = io.StringIO(), io.StringIO()
        with patch('mini_dbms.cli.TableStore', return_value=store), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['run', str(self.sql_path), '--data-dir', str(self.directory)])
        self.assertEqual(code, 1)
        self.assertEqual([json.loads(line) for line in out.getvalue().splitlines()],
                         [{'columns': ['id', 'name', 'age']}, [1, 'first', 1]])
        self.assertIn('[corruption]', err.getvalue())
        self.assertTrue(store._file.closed)

    def test_output_flush_failure_preserves_insert_and_stops_before_next_sql(self):
        class FailingOutput(io.StringIO):
            def flush(self):
                raise OSError('injected stdout flush failure')

        initialize(self.directory)
        self.sql_path.write_text(
            "INSERT INTO users (name,age) VALUES ('first',1);"
            "INSERT INTO users (name,age) VALUES ('later',2);", encoding='utf-8')
        out, err = FailingOutput(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['run', str(self.sql_path), '--data-dir', str(self.directory)])
        self.assertEqual(code, 1)
        self.assertIn('[output]', err.getvalue())
        self.assertIn('may already be stored', err.getvalue())
        with TableStore(self.directory) as store:
            self.assertEqual(list(store.scan()), [{'id': 1, 'name': 'first', 'age': 1}])
            self.assertEqual(store.next_id, 2)
