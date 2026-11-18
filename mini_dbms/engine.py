from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass

from .parser import Insert, Select
from .schema import validate_insert, validate_select
from .storage import TableStore


@dataclass(frozen=True)
class InsertResult:
    inserted_id: int
    affected_rows: int = 1


@dataclass(frozen=True)
class SelectResult:
    columns: tuple[str, ...]
    rows: Iterator[tuple]


class Engine:
    def __init__(self, store: TableStore):
        self.store = store

    def execute(self, statement: Insert | Select) -> InsertResult | SelectResult:
        if isinstance(statement, Insert):
            values = validate_insert(statement.table, statement.columns, statement.values)
            result = self.store.append(values)
            return InsertResult(result.inserted_id)
        if not isinstance(statement, Select):
            raise TypeError('execute requires an Insert or Select AST')
        columns = validate_select(statement.table, statement.columns, statement.condition)

        def rows():
            with closing(self.store.scan()) as records:
                for row in records:
                    condition = statement.condition
                    if condition is None or row[condition.column] == condition.value:
                        yield tuple(row[column] for column in columns)

        return SelectResult(columns, rows())
