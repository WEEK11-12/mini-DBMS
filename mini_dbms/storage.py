from dataclasses import dataclass
import json
import os
from pathlib import Path

from .errors import CorruptionError, SchemaError, StorageError
from .schema import MAX_INT, validate_insert, validate_row


@dataclass(frozen=True)
class AppendResult:
    inserted_id: int
    offset: int


def initialize(data_dir):
    directory = Path(data_dir)
    path = directory / 'users.jsonl'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with path.open('xb'):
            pass
    except OSError as exc:
        raise StorageError(f'cannot initialize {path}: {exc}') from exc


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'invalid JSON constant: {value}')


class TableStore:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / 'users.jsonl'
        self._failed = False
        try:
            self._file = self.path.open('r+b')
        except OSError as exc:
            raise StorageError(f'cannot open {self.path}: {exc}') from exc
        self.next_id = 1
        try:
            for row in self.scan():
                self.next_id = row['id'] + 1
        except BaseException:
            self._invalidate()
            raise

    def _ensure_open(self):
        if self._failed or self._file.closed:
            raise StorageError(f'{self.path}: storage is unavailable; reopen after inspection')

    def _invalidate(self):
        self._failed = True
        try:
            self._file.close()
        except OSError:
            # Preserve the original failure; close may retry a failed buffered write.
            pass

    def scan(self):
        self._ensure_open()
        line_number = 0
        offset = 0
        previous_id = 0
        try:
            with self.path.open('rb') as source:
                while True:
                    self._ensure_open()
                    offset = source.tell()
                    raw = source.readline()
                    if not raw:
                        break
                    line_number += 1
                    try:
                        if not raw.endswith(b'\n') or raw.endswith(b'\r\n'):
                            raise ValueError('record must end with LF')
                        row = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                                         parse_constant=_reject_constant)
                        validate_row(row)
                        if row['id'] <= previous_id:
                            raise ValueError('stored IDs must be strictly increasing')
                    except (ValueError, SchemaError) as exc:
                        raise CorruptionError(
                            f'{self.path}: line {line_number}, byte {offset}: {exc}'
                        ) from exc
                    previous_id = row['id']
                    yield row
        except OSError as exc:
            self._invalidate()
            raise StorageError(
                f'{self.path}: read failed near line {line_number + 1}, byte {offset}: {exc}'
            ) from exc
        except CorruptionError:
            self._invalidate()
            raise

    def append(self, values: dict) -> AppendResult:
        self._ensure_open()
        values = validate_insert('users', tuple(values), tuple(values.values()))
        if self.next_id > MAX_INT:
            raise SchemaError('automatic ID exhausted signed 64-bit integer range')
        row = {'id': self.next_id, **values}
        data = (json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        try:
            self._file.seek(0, os.SEEK_END)
            offset = self._file.tell()
            remaining = memoryview(data)
            while remaining:
                written = self._file.write(remaining)
                if written is None or written <= 0:
                    raise OSError('write made no progress')
                remaining = remaining[written:]
            self._file.flush()
        except OSError as exc:
            self._invalidate()
            raise StorageError(
                f'{self.path}: write/flush failed; partial data may remain: {exc}'
            ) from exc
        inserted_id = self.next_id
        self.next_id += 1
        return AppendResult(inserted_id, offset)

    def close(self):
        if self._file.closed:
            return
        try:
            self._file.close()
        except OSError as exc:
            self._failed = True
            raise StorageError(f'{self.path}: close failed: {exc}') from exc

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            self._invalidate()
        else:
            self.close()
