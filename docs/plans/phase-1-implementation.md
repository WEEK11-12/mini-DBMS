# Phase 1 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user authorized Phase 1 implementation and questions only for consequential new choices.

**Goal:** Python 표준 라이브러리로 설계한 CLI·INSERT·SELECT·JSON Lines 저장을 구현하고 재시작·실패 정책을 검증한다.

**Architecture:** 파서 AST → 실행기의 스키마 검증 → 저장소. CLI는 SQL 문장을 순서대로 실행하고 스트리밍 결과를 출력한다.

**Tech Stack:** Python 3.13, dataclasses, argparse, json, unittest.

**Spec:** [Phase 1 설계](../design/phase-1.md).

## Global Constraints

- 기존 yeongeun-main 브랜치에서 구현한다. 루트 README의 main 원문을 유지한다.
- 외부 의존성을 추가하지 않는다. Phase 2·3은 구현하지 않는다.
- 첫 SQL 실패 후 중단, 앞선 성공 유지. 손상 데이터 자동 삭제·복구 없음.
- JSON Lines UTF-8·LF, 정확한 정수/문자열 타입, 자동 ID, flush 완료 후 성공.
- 사용자 승인으로 설계 3절 기본값을 첫 구현에 사용한다. 새로 중요한 선택이 생기면 질문한다.

## Review Focus

- 문자열의 세미콜론·이스케이프가 잘못된 문장 분할을 일으키지 않는가.
- 저장 레코드의 bool·중복 키·역순 ID·잘린 마지막 기록을 조용히 허용하지 않는가.
- 일부 쓰기 또는 flush 실패 후 성공 응답하거나 추가 쓰기를 하지 않는가.
- 지연 SELECT의 오류·반복 중단 시 파일 핸들이 남지 않는가.
- 뒤 문장의 문법·UTF-8 오류 때문에 앞선 성공을 취소하거나 후속 INSERT를 실행하지 않는가.

## Task 1: 파서·스키마

Files: mini_dbms/{__init__,errors,parser,schema}.py; tests/test_parser.py; tests/test_schema.py.

Interfaces: iter_statements(chunks) → SQL 문자열 반복자; parse(sql) → Insert | Select; validate_insert(table, columns, values) → dict; validate_select(table, columns, condition) → 컬럼 튜플; validate_row(row) → None.

- [x] 특수문자·조건·문장 종료·범위·중복·잘못된 타입 테스트 작성.
- [x] python -m unittest tests.test_parser tests.test_schema -v 실행, 기능 부재 실패 확인.
- [x] AST, 문장 분리·토큰 파서, 공유 스키마 검증 구현.
- [x] 같은 테스트 PASS 확인.

## Task 2: 저장소

Files: mini_dbms/storage.py; tests/test_storage.py.

Interfaces: initialize(data_dir); TableStore(data_dir) context manager; scan() → 행 반복자; append(values) → AppendResult(inserted_id, offset).

- [x] 초기화 보존·재시작·손상·바이트 위치·부분 쓰기·flush 실패 테스트 작성.
- [x] python -m unittest tests.test_storage -v 실행, 기능 부재 실패 확인.
- [x] 검증된 JSON Lines 읽기·쓰기, ID와 파일 수명 관리 구현.
- [x] 저장소 테스트 PASS 확인.

## Task 3: 실행기·CLI

Files: mini_dbms/{engine,cli,__main__}.py; tests/test_engine.py; tests/test_cli.py.

Interfaces: Engine(store).execute(AST) → InsertResult | SelectResult; main(argv=None) → 종료 코드.

- [x] 실행 전 검증·스트리밍·SQL 파일 중단·별도 프로세스 재실행 테스트 작성.
- [x] python -m unittest tests.test_engine tests.test_cli -v 실행, 기능 부재 실패 확인.
- [x] 실행기·CLI와 예외 정리 구현.
- [x] 전체 python -m unittest discover -v PASS 확인.

## Task 4: 검토·사용 문서

Files: docs/usage.md; examples/phase1.sql; docs/design/phase-1.md; docs/study/00-overview.md; docs/study/04-verification.md.

- [x] 실제 CLI 초기화·SQL 실행·재시작 결과 확인.
- [x] 전체 테스트·구문 검사·문서 링크·Git diff 확인.
- [x] fresh reviewer로 전체 변경 검토, 중요한 결함은 회귀 테스트 RED→GREEN으로 수정.
- [x] 실행 명령·결과·보장 한계를 기록하고 변경을 보고.

## Progress

2026-11-18: 기존 개인 작업 브랜치의 깨끗한 checkout을 사용. 별도 worktree 생성은 사용자 지정 브랜치 작업에 불필요하여 생략. 계획과 설계의 입출력 계약을 대조했다. 새 의존성은 없다.

2026-11-18 실행 기록:

- Task 1 complete: 파서·스키마 테스트 모듈 부재 실패 확인 후 구현, 10개 통과.
- Task 2 complete: 저장소 모듈 부재 실패 확인 후 구현, 11개 통과. 이후 손상 JSON 경계 사례를 추가했다.
- Task 3 complete: 실행기·CLI 모듈 부재 실패 확인 후 구현, 최초 전체 32개 통과.
- Task 4 complete: fresh reviewer의 중요한 지적 1건(같은 줄 UTF-8 오류로 앞 문장 미실행)을 실제 subprocess 테스트로 RED 확인 후 수정. 최종 전체 34개 통과. 추가 중요한 지적 없음.
- 실제 명령: python -W error::ResourceWarning -m unittest discover -v → 34 tests, OK. python -m compileall -q mini_dbms tests → exit 0.
- 예제 init과 run을 별도 프로세스로 실행하고 재실행 ID 1·2 → 3·4와 기존 행 유지 확인.
- Windows 샌드박스 tempfile ACL 오류는 최소 진단으로 분리했고, 테스트를 변경하지 않고 정상 권한으로 실행했다.
- 사용자 요청은 Phase 1 로컬 구현이며, 별도 코드 커밋·푸시·main 병합은 수행하지 않았다.

진행 중 중요한 설계 변경은 없었다. 첫 구현은 설계 3절의 기본값을 따른다. Phase 2·3 및 성능 실험은 다음 작업이다.

후속 보완: 저장 뒤 결과 출력 실패를 테스트로 재현하고 출력 flush·재실행 전 조회 안내를 추가했다. 첫 행 보존, 다음 SQL 미실행, ID 복원을 확인했으며 전체 35개 테스트가 통과했다. 추가 코드 커밋·푸시는 하지 않았다.
