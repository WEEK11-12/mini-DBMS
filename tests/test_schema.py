import unittest

from mini_dbms.errors import SchemaError
from mini_dbms.parser import Equal
from mini_dbms.schema import validate_insert, validate_row, validate_select


class SchemaTests(unittest.TestCase):
    def test_insert_maps_names_in_requested_order(self):
        self.assertEqual(validate_insert('users', ('age', 'name'), (25, '영희')),
                         {'name': '영희', 'age': 25})
        self.assertEqual(validate_insert('users', ('name', 'age'), ('', -1)),
                         {'name': '', 'age': -1})

    def test_insert_rejects_invalid_names_counts_and_types(self):
        cases = [
            ('missing', ('name', 'age'), ('x', 1)),
            ('users', ('name', 'name'), ('x', 'y')),
            ('users', ('name', 'age'), ('x',)),
            ('users', ('name',), ('x',)),
            ('users', ('name', 'age', 'id'), ('x', 1, 1)),
            ('users', ('name', 'age'), ('x', '1')),
            ('users', ('name', 'age'), ('x', True)),
            ('users', ('name', 'age'), ('x', 2**63)),
            ('users', ('name', 'age'), ('x', -(2**63)-1)),
            ('users', ('name', 'age'), ('\ud800', 1)),
        ]
        for args in cases:
            with self.subTest(args=repr(args)), self.assertRaises(SchemaError):
                validate_insert(*args)

    def test_select_checks_columns_and_condition_before_scanning(self):
        self.assertEqual(validate_select('users', None, None), ('id', 'name', 'age'))
        self.assertEqual(validate_select('users', ('age', 'name'), Equal('id', 1)),
                         ('age', 'name'))
        for columns, condition in [
            (('missing',), None), (('name', 'name'), None),
            (('name',), Equal('missing', 1)), (('name',), Equal('age', '25')),
        ]:
            with self.subTest(columns=columns, condition=condition), self.assertRaises(SchemaError):
                validate_select('users', columns, condition)

    def test_stored_rows_have_exact_schema_and_positive_id(self):
        validate_row({'id': 1, 'name': 'x', 'age': -(2**63)})
        for row in [
            [], {'id': 1, 'name': 'x'},
            {'id': 1, 'name': 'x', 'age': 1, 'extra': 0},
            {'id': True, 'name': 'x', 'age': 1},
            {'id': 0, 'name': 'x', 'age': 1},
            {'id': 1, 'name': 'x', 'age': 1.0},
        ]:
            with self.subTest(row=row), self.assertRaises(SchemaError):
                validate_row(row)
