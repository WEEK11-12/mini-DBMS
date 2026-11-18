# Phase 1 실행 방법

저장소 루트에서 실행합니다. 외부 패키지 설치는 필요하지 않습니다. 검증 환경은 Windows, Python 3.13.14입니다.

## 처음 실행

```powershell
python -m mini_dbms init --data-dir data
python -m mini_dbms run examples/phase1.sql --data-dir data
```

init은 data 디렉터리와 빈 users.jsonl을 만듭니다. 기존 파일이 있으면 덮어쓰지 않고 오류로 종료합니다. run은 테이블 파일이 없으면 생성하지 않고 실패합니다. 다른 데이터 디렉터리는 --data-dir로 지정합니다.

예제는 영희와 O'Brien; 철수 두 행을 저장하고 전체 행과 age = 25인 name을 조회합니다. 예제를 다시 실행하면 같은 이름의 새 행이 추가됩니다. ID는 재시작해도 증가합니다.

## 지원 SQL

```sql
INSERT INTO users (name, age) VALUES ('영희', 25);
INSERT INTO users (age, name) VALUES (28, 'O''Brien');
SELECT * FROM users;
SELECT name, age FROM users;
SELECT name FROM users WHERE id = 1;
```

스키마는 users(id: 자동 양의 정수, name: 문자열, age: 정수)입니다. INSERT는 name과 age를 각각 한 번씩 모두 지정합니다. WHERE는 생략하거나 동등 비교 한 개를 사용합니다. 정수는 signed 64-bit 범위이고 자동 형 변환·NULL은 지원하지 않습니다.

문자열 밖의 세미콜론으로 각 문장을 끝내야 합니다. 작은따옴표 자체는 두 번 써서 표현합니다. SQL 주석, JOIN·집계·정렬·복합 조건, CREATE TABLE·UPDATE·DELETE는 지원하지 않습니다.

## 출력과 오류

INSERT 성공은 다음처럼 한 줄로 출력합니다.

```json
{"inserted_id": 1, "affected_rows": 1}
```

SELECT는 컬럼 헤더, 각 행의 JSON 배열, 완료 시 행 수를 차례로 출력합니다.

```json
{"columns": ["name"]}
["영희"]
{"row_count": 1}
```

정상 출력은 stdout, 오류는 stderr입니다. 종료 코드는 성공 0, 실행 실패 1, 명령 사용 오류 2입니다. 오류에는 input / syntax / schema / corruption / storage 분류를 표시합니다.

첫 실패가 발생하면 이후 SQL을 실행하지 않습니다. 앞선 성공은 유지됩니다. SELECT 중간 실패 시 일부 행이 이미 출력되었을 수 있으며, 완료 행 수 없이 오류와 실패 종료 코드로 알립니다.

결과 출력도 문장 처리 중 flush합니다. 저장 뒤 출력에 실패하면 [output] 오류와 함께 데이터가 이미 저장됐을 수 있다고 알리고 이후 SQL을 중단합니다. 같은 INSERT를 재실행하기 전에 SELECT로 확인해야 합니다. 출력 실패가 저장 취소나 자동 중복 방지를 뜻하지 않습니다.

## 파일 저장과 재시작

data/users.jsonl은 UTF-8 JSON Lines입니다. 파일에는 한 행당 객체 하나와 LF 줄바꿈을 기록합니다. 자동 ID는 1부터 시작하고 쓰기·flush 성공 후 증가합니다. 재시작 시 파일 전체를 읽어 스키마·ID 순서·LF를 검사하고 최대 ID + 1을 복원합니다.

파일을 수동으로 수정하거나 텍스트 편집기로 CRLF·BOM을 추가하면 손상으로 판정할 수 있습니다. 손상 파일은 자동으로 고치거나 삭제하지 않습니다. 쓰기 실패 후에는 일부 데이터가 남았을 수 있으며, 저장소 사용을 중단하고 원본을 보존합니다.

성공 기준은 flush이며 fsync·전원 장애 내구성·자동 복구·여러 문장의 전체 롤백은 보장하지 않습니다. Phase 1은 단일 프로세스만 같은 데이터 디렉터리에 접근하는 조건입니다.

## 테스트

```powershell
python -W error::ResourceWarning -m unittest discover -v
python -m compileall -q mini_dbms tests
```

테스트는 임시 디렉터리를 사용하며 사용자 데이터는 수정하지 않습니다. Windows Codex 샌드박스에서는 Python 임시 디렉터리 ACL 때문에 테스트가 차단될 수 있습니다. 이번 검증은 동일 명령을 샌드박스 밖에서 실행해 통과했습니다. DB 동작을 우회하기 위해 테스트를 변경하지 않았습니다.

[Phase 1 설계](design/phase-1.md) · [학습·검증 기록](study/04-verification.md)
