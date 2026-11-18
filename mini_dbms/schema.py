from .errors import SchemaError
from .parser import Equal

MIN_INT = -(2**63)
MAX_INT = 2**63 - 1
COLUMNS = {'id': int, 'name': str, 'age': int}


def _table(table: str):
    if table != 'users':
        raise SchemaError(f'unknown table: {table}')


def _value(column: str, value):
    if column not in COLUMNS:
        raise SchemaError(f'unknown column: {column}')
    expected = COLUMNS[column]
    if type(value) is not expected:
        raise SchemaError(f'{column} requires {expected.__name__}')
    if expected is int and not MIN_INT <= value <= MAX_INT:
        raise SchemaError(f'{column} is outside signed 64-bit integer range')
    if expected is str:
        try:
            value.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise SchemaError(f'{column} contains invalid Unicode') from exc


def validate_insert(table: str, columns: tuple, values: tuple) -> dict:
    _table(table)
    if len(columns) != len(values):
        raise SchemaError('column and value counts differ')
    if len(set(columns)) != len(columns):
        raise SchemaError('duplicate INSERT columns')
    if set(columns) != {'name', 'age'}:
        raise SchemaError('INSERT must specify name and age exactly once; id is automatic')
    supplied = dict(zip(columns, values))
    for column, value in supplied.items():
        _value(column, value)
    return {'name': supplied['name'], 'age': supplied['age']}


def validate_select(table: str, columns: tuple | None, condition: Equal | None) -> tuple:
    _table(table)
    selected = tuple(COLUMNS) if columns is None else columns
    if not selected or len(set(selected)) != len(selected):
        raise SchemaError('SELECT columns must be nonempty and unique')
    for column in selected:
        if column not in COLUMNS:
            raise SchemaError(f'unknown column: {column}')
    if condition is not None:
        _value(condition.column, condition.value)
    return selected


def validate_row(row):
    if type(row) is not dict or set(row) != set(COLUMNS):
        raise SchemaError('stored row must contain exactly id, name, age')
    for column, value in row.items():
        _value(column, value)
    if row['id'] < 1:
        raise SchemaError('stored id must be positive')
