class DBError(Exception):
    code = 'database'


class SQLSyntaxError(DBError):
    code = 'syntax'


class SchemaError(DBError):
    code = 'schema'


class InputError(DBError):
    code = 'input'


class StorageError(DBError):
    code = 'storage'


class CorruptionError(StorageError):
    code = 'corruption'
