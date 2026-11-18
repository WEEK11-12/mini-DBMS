import argparse
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .engine import Engine, InsertResult
from .errors import DBError, InputError
from .parser import iter_statements, parse
from .storage import TableStore, initialize


def _emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def _decoded_lines(source):
    line_number = 0
    try:
        for raw in source:
            line_number += 1
            try:
                decoded = raw.decode('utf-8')
            except UnicodeDecodeError as exc:
                # Execute complete preceding statements before reporting the bad byte.
                yield raw[:exc.start].decode('utf-8')
                raise InputError(
                    f'{source.name}: invalid UTF-8 on SQL line {line_number}, byte {exc.start}: {exc}'
                ) from exc
            yield decoded
    except OSError as exc:
        raise InputError(f'{source.name}: cannot read SQL line {line_number + 1}: {exc}') from exc


def _run(sql_path: Path, data_dir: Path):
    try:
        source = sql_path.open('rb')
    except OSError as exc:
        raise InputError(f'cannot open SQL file {sql_path}: {exc}') from exc
    number = 1
    try:
        with source, TableStore(data_dir) as store:
            engine = Engine(store)
            for sql in iter_statements(_decoded_lines(source)):
                result = engine.execute(parse(sql))
                if isinstance(result, InsertResult):
                    _emit(asdict(result))
                else:
                    with closing(result.rows):
                        _emit({'columns': result.columns})
                        count = 0
                        for row in result.rows:
                            _emit(row)
                            count += 1
                        _emit({'row_count': count})
                number += 1
    except DBError as exc:
        raise type(exc)(f'{sql_path}: statement {number}: {exc}') from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='mini_dbms')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='create an empty table; never overwrite')
    init.add_argument('--data-dir', type=Path, default=Path('data'))
    run = commands.add_parser('run', help='execute a UTF-8 SQL file, stopping on the first error')
    run.add_argument('sql_file', type=Path)
    run.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            initialize(args.data_dir)
            _emit({'initialized': str(args.data_dir / 'users.jsonl')})
        else:
            _run(args.sql_file, args.data_dir)
    except DBError as exc:
        print(f'[{exc.code}] {exc}', file=sys.stderr)
        return 1
    except OSError as exc:
        print(
            f'[output] cannot write CLI output: {exc}; '
            'data may already be stored; check the table before retrying',
            file=sys.stderr,
        )
        return 1
    return 0
