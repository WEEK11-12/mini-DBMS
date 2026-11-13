[⬅ overview](./00-overview.md)
# 3. 사용자가 실제로 쓰는 기능

> - SQL 기본: INSERT, SELECT, WHERE, UPDATE, DELETE
> - 테이블, 스키마, 기본 키(PK), 자동 증가 ID
> - 인덱스는 어떤 상황에서 왜 쓰는지
> - 트랜잭션과 ACID, 동시성 제어(락)
> - 백업과 복구, 사용자 권한
> - 직접 체험하기: SQLite나 MySQL로 간단한 테이블을 만들고, EXPLAIN으로 - 인덱스 유무에 따른 차이 확인

---

## SQL 기본 문법
- SQL : 무슨 데이터를 어떻게 할지를 표현
- `INSERT` : 행 넣기
- `SELECT` : 행 읽기
- `UPDATE` : 수정하기
- `DELETE` : 행 지우기. 조건이 없으면 모든 행을 대상으로 함. (예: `DELETE FROM users` - 모든 행 삭제)
- `WHERE` : 어떤 행을 대상으로 할지 정하는 **조건** (동작과 **대상 범위**를 따로 확인해야 함)

---

## DB의 구성
#### 테이블과 스키마
- **테이블 (데이터 집합)** : 데이터를 행으로 모아둔 것
- **스키마 (데이터 구조)** : 그 테이블에 어떤 열이 있으며, 각 열에 어떤 값이 들어갈 수 있는지 정한 약속
  - 각 열에 대한 약속이 있어야 DBMS와 사용자 모두 행의 의미를 일관되게 해석할 수 있음
- 스키마와 테이블 생성 : `CREATE TABLE`
  - 과제 상황 : 스키마와 테이블이 이미 존재한다고 가정
  - Phase 01에서 테이블 직접 만드는 기능은 요구하지 않는 상황
#### 기본 키 (PK, Primary Key)
- **기본 키** : 테이블에서 각 행을 서로 구별하기 위해 정한 '열' 또는 '열의 조합'
  - 각 행을 유일하게 구분해주는 기준이 됨
  - 특정 행을 찾거나, 다른 테이블에서 그 사용자를 참조할 때 유용
- **자동 증가 ID** : 새 행을 추가할 때, 사용자가 ID를 직접 정하는 대신, DBMS가 다음 ID 값을 부여하는 방식
  - 매번 사용자가 기존 ID와 겹치지 않는 값을 찾아 넣을 필요가 줄어듦
  - 번호가 빈틈없이 이어지지는 않음 (엔티티 삭제 혹은 작업 실패)
#### 인덱스
- **인덱스** : 원하는 행을 찾을 때 모든 행을 하나씩 살펴보지 않도록 돕는 검색용 구조
- **인덱스의 키** : 인덱스 안에서 검색 기준으로 쓰는 값 
  - 인덱스의 키 ≠ 기본 키(PK) (예 : `user.email` ≠ `user.id`)
  - **기본 키는 행을 구별하는 규칙, 인덱스는 행을 빨리 찾기 위한 구조**
  - 기본 키에만 만드는 게 아니라, 검색에 필요한 열을 기준으로 만들 수 있음
  - 모든 열에 인덱스가 생기는 것도 아님

---

## 작업 단위와 제어
#### 트랜잭션
- **트랜잭션** : 여러 데이터 변경을 하나의 작업 단위로 묶는 것
- 일련의 데이터 변경 작업이 함께 완료되거나, 함께 취소되어야 할 때 사용
- DBMS는 여러 SQL 문장이 하나의 트랜잭션이라고 스스로 알 수 없음.
  - 어디부터 어디까지를 한 작업으로 볼지는 사용하는 쪽이 정함
  - DBMS마다 사용자가 사용할 수 있는 API가 있음 (예 : MySQL의 `START TRANSACTION` & `COMMIT`)
  - DBMS는 사용자가 정한 경계를 지켜주는 것.
#### ACID
- **ACID** : 트랜잭션에 기대하는 성질을 정리한 것
- `Atomicity` : 트랜잭션에 묶인 변경이 전부 반영되거나, 전부 취소되어야 한다
- `Consistency` : 트랜잭션 전후에 데이터가 정해진 규칙을 지켜야 한다 (예 : 계좌 잔액은 음수가 될 수 없다는 규칙 유지)
- `Isolation` : 동시에 실행되는 트랜잭션들이 서로의 중간 상태 때문에 잘못된 결과를 내지 않아야 한다. (관련 : lock으로 보장)
- `Durability` : 확정된 처리의 경우 이후 장애가 나더라도 유지되어야 한다.
#### 동시성 제어 (lock)
- **락 (lock, 잠금)** : 여러 트랜잭션이 같은 데이터에 접근할 때, 충돌할 수 있는 작업을 잠시 기다리게 하는 동시성 제어 방법
- Isolation(격리성)을 위한 도구
- 락이 있다고 모든 읽기를 무조건 막는 것은 아님
  - 무엇을 잠그고 어떤 접근을 기다리게 할지는 락의 종류와 DBMS의 동시성 제어 방식에 따라 다름
#### 백업과 복구
- Durability (지속성)을 위한 도구
- **백업** : 데이터의 별도 사본을 마련하는 것
- **복구** : 장애나 실수로 데이터가 손상됐을 때, 사본 등을 이용해 되돌리는 과정
#### 사용자 권한
- 누가 어떤 데이터에 어떤 작업을 할 수 있는지 제한
  - 예 : 조회만 하는 계정에는 `SELECT` 권한만

--- 

## 실습
#### EXPLAIN으로 인덱스 사용 여부 확인하기
- SQLite에 users(id, email) 테이블과 예시 행을 만든 뒤 같은 이메일 조회 비교하기
  ``` sql
  CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);
  
  INSERT INTO users (email)
  VALUES ('a@example.com'), ('b@example.com'), ('c@example.com');
  
  -- ① 이메일 인덱스가 없을 때 실행 계획 확인
  EXPLAIN QUERY PLAN
  SELECT * FROM users WHERE email = 'b@example.com';
  
  -- ② email 열에 인덱스 등록
  CREATE INDEX idx_users_email ON users(email);
  
  -- ③ 같은 조회문의 실행 계획 다시 확인
  EXPLAIN QUERY PLAN
  SELECT * FROM users WHERE email = 'b@example.com';
  ```
- `EXPLAIN QUERY PLAN` : SQL을 어떻게 실행할 계획인지 보여줌 (결과 차이 ↓)
  ```sql
  -- ① 인덱스 생성 전 결과
  SCAN users
  
  -- ③ 인덱스 생성 후 결과 
  SEARCH users USING COVERING INDEX idx_users_email (email=?)
  ```


<br>
<br>

---

<p align="right">
  <a href="./02-when-to-use.md">⬅ 이전 페이지</a>
  &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="./04-how-it-works.md">다음 페이지 ➡</a>
</p>