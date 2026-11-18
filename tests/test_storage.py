import json
from pathlib import Path
import tempfile
import unittest

from mini_dbms.errors import CorruptionError, SchemaError, StorageError
from mini_dbms.storage import TableStore, initialize


class FailingFile:
    """Inject a failure below storage logic while keeping real file side effects."""

    def __init__(self, file, failure):
        self.file = file
        self.failure = failure
        self.writes = 0

    def __getattr__(self, name):
        return getattr(self.file, name)

    def write(self, data):
        self.writes += 1
        if self.failure == 'partial':
            if self.writes > 1:
                raise OSError('injected disk full')
            return self.file.write(data[:5])
        if self.failure == 'zero':
            return 0
        if self.failure == 'short':
            return self.file.write(data[:3])
        return self.file.write(data)

    def flush(self):
        if self.failure == 'flush':
            raise OSError('injected flush failure')
        return self.file.flush()


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'data'
        initialize(self.directory)
        self.path = self.directory / 'users.jsonl'

    def test_initialization_never_overwrites_existing_table(self):
        self.path.write_bytes(b'keep me')
        with self.assertRaises(StorageError):
            initialize(self.directory)
        self.assertEqual(self.path.read_bytes(), b'keep me')

    def test_missing_file_is_not_created_by_run(self):
        self.path.unlink()
        with self.assertRaises(StorageError):
            TableStore(self.directory)
        self.assertFalse(self.path.exists())

    def test_append_roundtrip_and_utf8_byte_offsets(self):
        with TableStore(self.directory) as store:
            self.assertEqual(list(store.scan()), [])
            first = store.append({'name': '영희,\n";', 'age': 25})
            second = store.append({'name': '철수', 'age': -2})
            self.assertEqual((first.inserted_id, first.offset), (1, 0))
            raw = self.path.read_bytes()
            self.assertEqual(second.offset, raw.index(b'\n') + 1)
            self.assertEqual(json.loads(raw[second.offset:]),
                             {'id': 2, 'name': '철수', 'age': -2})
            self.assertEqual(list(store.scan()), [
                {'id': 1, 'name': '영희,\n";', 'age': 25},
                {'id': 2, 'name': '철수', 'age': -2},
            ])
            self.assertEqual(len(raw.splitlines()), 2)

    def test_restart_uses_max_id_and_allows_gaps(self):
        self.path.write_bytes(b'{"id":2,"name":"a","age":1}\n'
                              b'{"id":5,"name":"b","age":2}\n')
        with TableStore(self.directory) as store:
            self.assertEqual(store.append({'name': 'c', 'age': 3}).inserted_id, 6)
        with TableStore(self.directory) as store:
            self.assertEqual(store.next_id, 7)

    def test_invalid_insert_does_not_change_file_or_consume_id(self):
        with TableStore(self.directory) as store:
            with self.assertRaises(SchemaError):
                store.append({'name': 'x', 'age': True})
            self.assertEqual(self.path.read_bytes(), b'')
            self.assertEqual(store.append({'name': 'x', 'age': 1}).inserted_id, 1)

    def test_id_exhaustion_is_rejected_without_writing(self):
        raw = b'{"id":9223372036854775807,"name":"x","age":1}\n'
        self.path.write_bytes(raw)
        with TableStore(self.directory) as store:
            with self.assertRaises(SchemaError):
                store.append({'name': 'y', 'age': 2})
        self.assertEqual(self.path.read_bytes(), raw)

    def test_startup_rejects_corruption_and_preserves_bytes(self):
        records = [
            b'\n', b'{"id":1', b'{"id":1,"name":"x","age":1}',
            b'{"id":1,"name":"x","age":1}\r\n',
            b'{"id":1,"id":2,"name":"x","age":1}\n',
            b'{"id":true,"name":"x","age":1}\n',
            b'{"id":1,"name":"x","age":null}\n',
            b'{"id":1,"name":"x","age":NaN}\n',
            b'{"id":1,"name":"x","age":1,"extra":0}\n',
            b'{"id":1,"age":1}\n', b'[]\n', b'\xff\n',
            b'\xef\xbb\xbf{"id":1,"name":"x","age":1}\n',
            b'{"id":1,"name":"\\ud800","age":1}\n',
            b'{"id":1,"name":"x","age":1}\n' * 2,
            b'{"id":2,"name":"x","age":1}\n{"id":1,"name":"y","age":2}\n',
        ]
        for raw in records:
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaises(CorruptionError) as caught:
                    TableStore(self.directory)
                self.assertIn('byte', str(caught.exception))
                self.assertIn('line', str(caught.exception))
                self.assertEqual(self.path.read_bytes(), raw)

    def test_short_writes_complete_before_success(self):
        with TableStore(self.directory) as store:
            store._file = FailingFile(store._file, 'short')
            result = store.append({'name': '한글', 'age': 1})
            self.assertEqual(result.inserted_id, 1)
            self.assertEqual(json.loads(self.path.read_bytes()),
                             {'id': 1, 'name': '한글', 'age': 1})

    def test_deep_invalid_json_is_reported_as_corruption(self):
        raw = b'[' * 2000 + b'0' + b']' * 2000 + b'\n'
        self.path.write_bytes(raw)
        with self.assertRaises(CorruptionError):
            TableStore(self.directory)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_write_failure_blocks_followup_and_keeps_existing_data(self):
        for failure in ['partial', 'zero', 'flush']:
            with self.subTest(failure=failure):
                self.path.write_bytes(b'{"id":1,"name":"old","age":1}\n')
                before = self.path.read_bytes()
                with TableStore(self.directory) as store:
                    store._file = FailingFile(store._file, failure)
                    with self.assertRaises(StorageError):
                        store.append({'name': 'new', 'age': 2})
                    self.assertEqual(store.next_id, 2)
                    self.assertTrue(store._file.closed)
                    after = self.path.read_bytes()
                    self.assertTrue(after.startswith(before))
                    with self.assertRaises(StorageError):
                        store.append({'name': 'later', 'age': 3})
                    with self.assertRaises(StorageError):
                        list(store.scan())
                    self.assertEqual(self.path.read_bytes(), after)

    def test_scan_failure_invalidates_store_and_closes_file(self):
        with TableStore(self.directory) as store:
            self.path.write_bytes(b'broken\n')
            with self.assertRaises(CorruptionError):
                list(store.scan())
            self.assertTrue(store._file.closed)
            with self.assertRaises(StorageError):
                store.append({'name': 'x', 'age': 1})

    def test_early_scan_close_and_store_context_release_resources(self):
        with TableStore(self.directory) as store:
            store.append({'name': 'x', 'age': 1})
            rows = store.scan()
            self.assertEqual(next(rows)['id'], 1)
            rows.close()
        self.assertTrue(store._file.closed)
        self.path.unlink()


if __name__ == '__main__':
    unittest.main()
