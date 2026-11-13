# 김유신 FastAPI 파일 관리 과제

파일 업로드, 파일명으로 다운로드, 전체 파일 목록 조회를 구현했습니다.
저장 위치는 **프로젝트 폴더의 `static/files`**이며, `/docs`에서 테스트할 수 있습니다.

## 실행하기

Python 3.10 이상이 필요합니다. 터미널에서 아래 명령을 실행하세요.

```bash
git clone https://github.com/yusin846-debug/kimyushin-fastapi.git
cd kimyushin-fastapi
python -m venv .venv
```

Windows PowerShell에서 가상환경을 활성화합니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows 명령 프롬프트(cmd)는 `.venv\Scripts\activate.bat`, macOS/Linux는
`source .venv/bin/activate`를 사용합니다.

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

브라우저에서 **http://127.0.0.1:8000/docs**를 엽니다.
루트 주소로 접속해도 `/docs`로 이동합니다.

## /docs 테스트 순서

1. **POST /upload** → **Try it out** → 파일 선택 → **Execute**.
   성공하면 HTTP 201과 파일명, 크기(bytes)가 표시됩니다.
2. **GET /files** → **Try it out** → **Execute**.
   저장된 파일 개수와 파일명·크기 목록을 확인합니다.
3. **GET /download** → **Try it out** → `filename`에 확장자를 포함한 파일명 입력 → **Execute**.
   응답의 **Download file** 링크로 다운로드합니다.
4. 내려받은 파일이 업로드한 원본과 같은지 확인합니다.

| 메서드 | 주소 | 기능 |
|---|---|---|
| POST | `/upload` | multipart/form-data의 `file` 필드로 업로드 |
| GET | `/download?filename=example.txt` | 지정한 파일 다운로드 |
| GET | `/files` | 전체 파일 목록 조회 |

## 처리 기준

- 한글 및 공백이 포함된 파일명을 지원합니다.
- 같은 파일명은 **409**를 반환하며 원본을 보존합니다.
- 없는 파일은 **404**, 잘못된 파일명은 **400**을 반환합니다.
- 파일 크기 제한은 **20 MiB**입니다. 초과하면 **413**을 반환하고 임시 파일을 제거합니다.
- 경로(`../` 등), 숨김 파일명, 심볼릭 링크는 허용하지 않습니다.
- 업로드 데이터와 가상환경은 Git에 포함하지 않습니다.
- 인증 없는 로컬 수업용 앱입니다. 공개 운영 시 인증·권한 및 요청 전체 크기 제한을 별도로 적용해야 합니다.

## 테스트

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

테스트는 임시 폴더를 사용하므로 실제 업로드 파일에 영향을 주지 않습니다.

## 구성

- `main.py`: FastAPI 앱과 파일 관리 API
- `static/files/`: 실제 업로드 파일 저장 위치
- `tests/test_files.py`: 정상 흐름 및 오류 처리 테스트
- `requirements.txt`: 실행 패키지
- `requirements-dev.txt`: 테스트 패키지

참고: [FastAPI 파일 업로드](https://fastapi.tiangolo.com/tutorial/request-files/),
[FileResponse](https://fastapi.tiangolo.com/advanced/custom-response/#fileresponse)
