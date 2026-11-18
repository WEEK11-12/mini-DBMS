from pathlib import Path
import tempfile
import unittest

from mini_dbms.engine import Engine, InsertResult, SelectResult
from mini_dbms.errors import CorruptionError, SchemaError
from mini_dbms.parser import parse
from mini_dbms.storage import TableStore, initialize


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        initialize(self.directory)
        self.store = TableStore(self.directory)
        self.addCleanup(self.store.close)
        self.engine = Engine(self.store)

    def test_insert_and_select_reuse_typed_ast(self):
        self.assertEqual(self.engine.execute(parse(
            "INSERT INTO users (age, name) VALUES (25, '영희')")), InsertResult(1, 1))
        self.engine.execute(parse("INSERT INTO users (name, age) VALUES ('철수', 25)"))
        self.engine.execute(parse("INSERT INTO users (name, age) VALUES ('민수', 30)"))
        result = self.engine.execute(parse('SELECT name FROM users WHERE age = 25'))
        self.assertIsInstance(result, SelectResult)
        self.assertEqual(result.columns, ('name',))
        self.assertEqual(list(result.rows), [('영희',), ('철수',)])
        self.assertEqual(list(self.engine.execute(parse(
            'SELECT * FROM users WHERE id = 3')).rows), [(3, '민수', 30)])
        self.assertEqual(list(self.engine.execute(parse(
            'SELECT name FROM users WHERE age = 99')).rows), [])

    def test_invalid_ast_values_fail_before_read_or_write(self):
        self.store.append({'name': 'x', 'age': 1})
        before = self.store.path.read_bytes()
        for sql in ["INSERT INTO users (name, age) VALUES ('x', '25')",
                    'SELECT absent FROM users',
                    "SELECT name FROM users WHERE age = '25'",
                    'SELECT name FROM absent']:
            with self.subTest(sql=sql), self.assertRaises(SchemaError):
                self.engine.execute(parse(sql))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(self.store.next_id, 2)

    def test_select_is_lazy_and_reports_midstream_corruption(self):
        self.store.append({'name': 'x', 'age': 1})
        result = self.engine.execute(parse('SELECT * FROM users'))
        with self.store.path.open('ab') as target:
            target.write(b'broken\n')
        self.assertEqual(next(result.rows), (1, 'x', 1))
        with self.assertRaises(CorruptionError):
            next(result.rows)

    def test_select_generator_can_be_closed_early(self):
        self.store.append({'name': 'x', 'age': 1})
        result = self.engine.execute(parse('SELECT * FROM users'))
        next(result.rows)
        result.rows.close()
        self.assertEqual(self.store.append({'name': 'y', 'age': 2}).inserted_id, 2)
