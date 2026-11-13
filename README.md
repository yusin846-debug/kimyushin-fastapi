# 김유신 FastAPI 파일 관리 과제 (MySQL 연동)

- 유저 등록·조회 (MySQL `users` 테이블)
- 파일 업로드, 파일명으로 다운로드, 전체 파일 목록 조회
- 실제 파일은 **프로젝트 폴더의 `static/files`**, 파일 정보(이름·크기·올린 유저)는 MySQL `files` 테이블에 저장
- `/docs`에서 모두 테스트할 수 있습니다.

## API

| 메서드 | 주소 | 기능 |
|---|---|---|
| POST | `/users` | 유저 등록 (JSON: `name`, `email`) |
| GET | `/users` | 전체 유저 목록 |
| GET | `/users/{user_id}` | 유저 상세 조회 |
| POST | `/upload` | multipart/form-data의 `file`, `user_id`로 업로드 |
| GET | `/download?filename=example.txt` | 지정한 파일 다운로드 |
| GET | `/files` | 전체 파일 목록 (`count`, `files`, `unregistered_files`) |

## Windows 실행 순서

> 코드 블록 안의 명령만 입력합니다. 앞뒤의 ``` 기호는 입력하지 않습니다.
> 아래 명령은 VS Code에서 이 폴더를 연 뒤 **터미널 → 새 터미널**(PowerShell)에서 실행합니다.

### 1. 가상환경과 패키지 (처음 한 번)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`Activate.ps1`(가상환경 활성화)은 쓰지 않아도 됩니다. 항상 `.\.venv\Scripts\python.exe`로 실행합니다.

### 2. MySQL DB와 앱 전용 계정 (처음 한 번)

root로 접속합니다. 비밀번호를 입력할 때 **글자가 화면에 보이지 않는 것이 정상**입니다.

```powershell
& "C:\Program Files\MySQL\MySQL Server 26.10\bin\mysql.exe" -u root -p
```

`mysql>` 화면에서 아래를 입력합니다. `새비밀번호`는 직접 정한 비밀번호로 바꿉니다.
이미 `fastapi_user`가 있다면 `CREATE USER`에서 오류가 나는데, 그 경우 기존 비밀번호를 그대로 쓰면 됩니다.

```sql
SELECT VERSION();
CREATE DATABASE IF NOT EXISTS fastapi_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS fastapi_test_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'fastapi_user'@'localhost' IDENTIFIED BY '새비밀번호';
CREATE USER 'fastapi_user'@'127.0.0.1' IDENTIFIED BY '새비밀번호';
GRANT ALL PRIVILEGES ON fastapi_db.* TO 'fastapi_user'@'localhost', 'fastapi_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON fastapi_test_db.* TO 'fastapi_user'@'localhost', 'fastapi_user'@'127.0.0.1';
exit
```

### 3. `.env` 만들기

```powershell
Copy-Item .env.example .env
notepad .env
```

열린 파일에서 `DB_PASSWORD=` 뒤를 2단계에서 정한 비밀번호로 바꾸고 저장합니다.
`.env`는 `.gitignore`에 들어 있어 GitHub에 올라가지 않습니다.

### 4. 테이블 만들기

```powershell
.\.venv\Scripts\python.exe init_db.py
```

`연결 성공` → `새로 생성: users`, `새로 생성: files` → `준비 완료`가 나오면 됩니다.
이 스크립트는 **없는 테이블만** 만들고, 기존 테이블·데이터는 삭제하거나 바꾸지 않습니다.
같은 이름의 테이블이 다른 구조로 이미 있으면 알려주고 멈춥니다.

### 5. 서버 실행

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

브라우저에서 **http://127.0.0.1:8000/docs** 를 엽니다. 서버를 끄려면 터미널에서 `Ctrl + C`.

## /docs 테스트 순서

각 항목에서 **Try it out** → 값 입력 → **Execute** 순서로 실행합니다.

1. **POST /users** → `{"name": "김유신", "email": "yusin@example.com"}` → 201과 `id` 확인
2. **GET /users**, **GET /users/{user_id}** → 등록한 유저 확인
3. **POST /upload** → 파일 선택, `user_id`에 1번의 `id` 입력 → 201
4. **GET /files** → 파일명·크기·user_id 확인
5. **GET /download** → `filename`에 확장자 포함 파일명 입력 → **Download file**
6. 서버를 껐다 켠 뒤 **GET /users**, **GET /files** → 데이터가 그대로 있는지 확인
7. 오류 확인: 같은 이메일 재등록(409), 없는 user_id로 업로드(404), 같은 이름 파일(409), 없는 파일 다운로드(404)

## 처리 기준

- 한글 및 공백이 포함된 파일명을 지원합니다. 파일명은 전체에서 하나만 허용(중복 시 **409**, 원본 보존)합니다.
- 이메일은 소문자로 저장하며 중복 시 **409**입니다. 없는 유저는 **404**, 잘못된 입력은 **422**입니다.
- 없는 파일은 **404**, 잘못된 파일명은 **400**, 20 MiB 초과는 **413**입니다.
- 업로드는 임시 파일 → 완성 파일 공개 → DB 저장 순서로 진행합니다.
  DB 저장이 실패하면 이번에 새로 만든 파일만 지우고, 기존 파일은 건드리지 않습니다.
- 경로(`../` 등), 숨김 파일명, 심볼릭 링크는 허용하지 않습니다.
- DB에 연결할 수 없으면 **503**과 안내 메시지를 반환합니다.
- 인증 없는 로컬 수업용 앱입니다. 공개 운영 시 인증·권한 및 요청 전체 크기 제한을 별도로 적용해야 합니다.

### DB 정보가 없는 기존 파일

MySQL 연동 전에 `static/files`에 올린 파일은 DB 정보가 없습니다.
이런 파일은 삭제하거나 임의의 유저에게 배정하지 않고, `GET /files`의 `unregistered_files`에 이름만 보여줍니다.
다운로드는 계속 가능하며, 같은 이름으로 새로 올리면 409입니다.
DB에 등록하고 싶다면 파일을 다른 곳에 옮긴 뒤 `/upload`로 원하는 유저 id와 함께 다시 올리면 됩니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- `tests/test_files.py`: 임시 폴더 + 임시 SQLite로 실행 (실제 파일·DB에 영향 없음)
- `tests/test_mysql.py`: `.env`의 `TEST_DB_NAME`(fastapi_test_db)으로 **실제 MySQL**에서 실행.
  테스트 전용 DB가 비어 있을 때만 실행되고, 끝나면 그 DB의 테이블만 지웁니다.
- Windows에서는 심볼릭 링크 테스트가 권한 문제로 건너뛰어질 수 있습니다(정상).

## 오류 해결

| 증상 | 확인할 것 |
|---|---|
| `python`을 찾을 수 없음 | Python 설치 후 VS Code를 다시 열기. `py --version`도 확인 |
| `init_db.py`에서 `OperationalError` | MySQL 서비스 실행 여부(`Get-Service MySQL*`), `.env`의 비밀번호·DB 이름 |
| `Access denied for user` | 2단계의 `CREATE USER`/`GRANT` 실행 여부, 비밀번호 오타 |
| `Unknown database` | 2단계의 `CREATE DATABASE` 실행 여부 |
| `/docs`에서 503 | 위와 같이 DB 연결 확인 후 서버 재시작 |
| 포트 8000 사용 중 | `--port 8001`을 붙여 실행하고 주소도 8001로 변경 |

## 구성

- `main.py`: FastAPI 앱과 API
- `database.py`: MySQL 연결 (`.env`에서 접속 정보 읽음)
- `models.py`: `users`, `files` 테이블 정의
- `schemas.py`: 입력·출력 형식
- `init_db.py`: 연결 확인 + 없는 테이블만 생성
- `.env.example`: 환경변수 예시 (실제 비밀번호는 `.env`에만)
- `static/files/`: 실제 업로드 파일 저장 위치
- `tests/`: 테스트
