from dataclasses import dataclass
import re
from collections.abc import Iterable, Iterator

from .errors import SQLSyntaxError


@dataclass(frozen=True)
class Insert:
    table: str
    columns: tuple[str, ...]
    values: tuple[str | int, ...]


@dataclass(frozen=True)
class Equal:
    column: str
    value: str | int


@dataclass(frozen=True)
class Select:
    table: str
    columns: tuple[str, ...] | None
    condition: Equal | None


def iter_statements(chunks: Iterable[str]) -> Iterator[str]:
    buffer = []
    in_string = False
    for chunk in chunks:
        for char in chunk:
            if char == "'":
                in_string = not in_string
            if char == ';' and not in_string:
                statement = ''.join(buffer).strip()
                buffer.clear()
                if statement:
                    yield statement
            else:
                buffer.append(char)
    if in_string:
        raise SQLSyntaxError('unclosed string at end of SQL file')
    if ''.join(buffer).strip():
        raise SQLSyntaxError('SQL statement must end with a semicolon')


_TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<string>'(?:[^']|'')*')|"
    r'(?P<integer>-?[0-9]+)|(?P<identifier>[A-Za-z_][A-Za-z_0-9]*)|'
    r'(?P<symbol>[(),=*;])'
)


class _Parser:
    def __init__(self, sql: str):
        self.tokens = []
        self.index = 0
        position = 0
        while position < len(sql):
            match = _TOKEN.match(sql, position)
            if match is None:
                raise SQLSyntaxError(f'unexpected character at offset {position}')
            if match.lastgroup != 'space':
                self.tokens.append((match.lastgroup, match.group(), position))
            position = match.end()
        self.tokens.append(('end', '', len(sql)))

    def accept(self, text: str) -> bool:
        if self.tokens[self.index][1].upper() == text:
            self.index += 1
            return True
        return False

    def require(self, text: str):
        if not self.accept(text):
            self.error(f'expected {text}')

    def error(self, message: str):
        raise SQLSyntaxError(f'{message} at offset {self.tokens[self.index][2]}')

    def identifier(self) -> str:
        kind, value, _ = self.tokens[self.index]
        if kind != 'identifier':
            self.error('expected identifier')
        self.index += 1
        return value.lower()

    def literal(self) -> str | int:
        kind, value, _ = self.tokens[self.index]
        if kind == 'string':
            result = value[1:-1].replace("''", "'")
        elif kind == 'integer':
            try:
                result = int(value)
            except ValueError as exc:
                raise SQLSyntaxError('integer literal is too long') from exc
        else:
            self.error('expected integer or single-quoted string')
        self.index += 1
        return result

    def comma_list(self, read_item) -> tuple:
        items = [read_item()]
        while self.accept(','):
            items.append(read_item())
        return tuple(items)

    def statement(self) -> Insert | Select:
        if self.accept('INSERT'):
            self.require('INTO')
            table = self.identifier()
            self.require('(')
            columns = self.comma_list(self.identifier)
            self.require(')')
            self.require('VALUES')
            self.require('(')
            values = self.comma_list(self.literal)
            self.require(')')
            result = Insert(table, columns, values)
        elif self.accept('SELECT'):
            columns = None if self.accept('*') else self.comma_list(self.identifier)
            self.require('FROM')
            table = self.identifier()
            condition = None
            if self.accept('WHERE'):
                column = self.identifier()
                self.require('=')
                condition = Equal(column, self.literal())
            result = Select(table, columns, condition)
        else:
            self.error('expected INSERT or SELECT')
        self.accept(';')
        if self.tokens[self.index][0] != 'end':
            self.error('unexpected trailing token')
        return result


def parse(sql: str) -> Insert | Select:
    return _Parser(sql).statement()
