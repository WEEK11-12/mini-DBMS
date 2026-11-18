import unittest

from mini_dbms.errors import SQLSyntaxError
from mini_dbms.parser import Equal, Insert, Select, iter_statements, parse


class ParserTests(unittest.TestCase):
    def test_insert_preserves_values_and_normalizes_identifiers(self):
        self.assertEqual(
            parse("iNsErT INTO Users (Age, NAME) VALUES (-25, 'O''Brien; 김,철수');"),
            Insert('users', ('age', 'name'), (-25, "O'Brien; 김,철수")),
        )

    def test_select_and_typed_conditions(self):
        self.assertEqual(parse('SELECT * FROM users'), Select('users', None, None))
        self.assertEqual(
            parse("SELECT name, age FROM users WHERE name = '25';"),
            Select('users', ('name', 'age'), Equal('name', '25')),
        )
        self.assertEqual(parse('SELECT name FROM users WHERE id = 25').condition,
                         Equal('id', 25))

    def test_statement_boundaries_work_across_chunks(self):
        chunks = ["; INSERT INTO users (name,age) VALUES ('O'", "'Brien;", "김',25);\n",
                  'SELECT * FROM users; ;\n']
        self.assertEqual(list(iter_statements(chunks)), [
            "INSERT INTO users (name,age) VALUES ('O''Brien;김',25)",
            'SELECT * FROM users',
        ])

    def test_next_statement_error_does_not_hide_previous_statement(self):
        statements = iter_statements(['SELECT * FROM users; SELECT name FROM users'])
        self.assertEqual(next(statements), 'SELECT * FROM users')
        with self.assertRaises(SQLSyntaxError):
            next(statements)

    def test_rejects_unsupported_or_malformed_syntax(self):
        for sql in [
            'SELECT name FROM users WHERE age > 1',
            'SELECT name FROM users WHERE age = 1 AND id = 2',
            'SELECT * FROM users garbage',
            'SELECT * FROM users; SELECT * FROM users;',
            "INSERT INTO users VALUES ('x', 2)",
            "INSERT INTO users (name, age) VALUES ('x', 2), ('y', 3)",
            'SELECT * FROM users -- comment',
            "SELECT * FROM users WHERE name = 'unfinished",
            'SELECT * FROM "users"',
            'SELECT * FROM users WHERE age = +2',
            '',
        ]:
            with self.subTest(sql=sql), self.assertRaises(SQLSyntaxError):
                parse(sql)

    def test_missing_terminator_and_unclosed_string(self):
        for sql in ['SELECT * FROM users', "SELECT * FROM users WHERE name = 'abc;"]:
            with self.subTest(sql=sql), self.assertRaises(SQLSyntaxError):
                list(iter_statements([sql]))


if __name__ == '__main__':
    unittest.main()
