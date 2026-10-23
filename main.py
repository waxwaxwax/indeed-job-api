
import logging
import os
import secrets
import sqlite3
import time
import uuid

from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Form,
    Request,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware



# ==========================================
# 1. ファイル・フォルダ設定
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
READ_TOKEN = os.getenv("READ_TOKEN", "")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv(
    "ALLOWED_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
).split(",") if origin.strip()]

if not ADMIN_TOKEN or not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
    raise RuntimeError(".env に ADMIN_TOKEN、OAUTH_CLIENT_ID、OAUTH_CLIENT_SECRET を設定してください")

DB_PATH = BASE_DIR / "jobs.db"

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = LOG_DIR / "api.log"


# ==========================================
# 2. ログ設定
# ==========================================

logger = logging.getLogger("job_api")
logger.setLevel(logging.INFO)
logger.propagate = False

# 再読み込み時のハンドラー重複を防ぐ
if not logger.handlers:

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    # ログファイルへ保存
    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # ターミナルにも表示
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ==========================================
# 3. SQLiteデータベース
# ==========================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                salary INTEGER NOT NULL
            )
        """)


# ==========================================
# 4. FastAPIアプリケーション
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    logger.info("event=server_started")
    yield
    logger.info("event=server_stopped")


app = FastAPI(
    title="求人管理API",
    description="Indeed Technical Analyst面接対策用のAPI",
    version="1.4.0",
    lifespan=lifespan,
)


# CORS: FastAPIアプリ生成後に登録する
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ==========================================
# 5. HTTPアクセスログ
# ==========================================

@app.middleware("http")
async def access_log_middleware(
    request: Request,
    call_next,
):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()

    method = request.method
    path = request.url.path

    try:
        response = await call_next(request)

    except Exception:
        # 予期しない内部エラー
        # 詳細な例外や秘密情報はログに出さない
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.error(
            "request_id=%s method=%s path=%s "
            "status=500 duration_ms=%.2f "
            "error=internal_server_error",
            request_id,
            method,
            path,
            duration_ms,
        )

        raise

    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request_id=%s method=%s path=%s "
        "status=%s duration_ms=%.2f",
        request_id,
        method,
        path,
        response.status_code,
        duration_ms,
    )

    return response


# ==========================================
# 6. HTTPエラーのログ
# ==========================================

@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    request_id = getattr(
        request.state,
        "request_id",
        "unknown",
    )

    # エラー内容はあらかじめ定義した
    # 短いコードに変換して記録する
    error_codes = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        422: "validation_error",
        429: "too_many_requests",
    }

    error_code = error_codes.get(
        exc.status_code,
        "http_error",
    )

    logger.warning(
        "request_id=%s event=http_error "
        "status=%s error=%s",
        request_id,
        exc.status_code,
        error_code,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


# ==========================================
# 7. 入力検証エラーのログ
# ==========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    request_id = getattr(
        request.state,
        "request_id",
        "unknown",
    )

    # 入力値そのものはログに記録しない
    logger.warning(
        "request_id=%s event=validation_error "
        "status=422",
        request_id,
    )

    # Pydanticのエラーに含まれる入力値を
    # レスポンスへ露出しないよう除去する
    safe_errors = []

    for error in exc.errors():
        safe_error = {
            key: value
            for key, value in error.items()
            if key not in ("input", "ctx", "url")
        }
        safe_errors.append(safe_error)

    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors},
    )


# ==========================================
# 8. 求人データモデル
# ==========================================

class JobInput(BaseModel):
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    salary: int = Field(ge=0)


class Job(JobInput):
    id: int


# ==========================================
# 9. ホーム
# ==========================================

@app.get("/")
def home():
    return {
        "message": "求人管理APIが動作しています",
        "version": "1.4.0",
    }


# ==========================================
# 15. 固定トークン（学習用）
# ==========================================

API_TOKENS = {ADMIN_TOKEN: "admin"}
if READ_TOKEN and READ_TOKEN != ADMIN_TOKEN:
    API_TOKENS[READ_TOKEN] = "read"

security = HTTPBearer(
    auto_error=False,
    description="学習用Bearerトークン",
)


# ==========================================
# 16. 固定トークン認証
# ==========================================

def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security
    ),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="アクセストークンがありません、または形式が正しくありません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if token not in API_TOKENS:
        raise HTTPException(
            status_code=401,
            detail="無効なアクセストークンです",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return API_TOKENS[token]



def require_admin(role: str = Depends(verify_token)):
    if role != "admin":
        raise HTTPException(status_code=403, detail="書き込み権限がありません")
    return role


# ==========================================
# 10. 求人一覧取得
# ==========================================

@app.get("/jobs", response_model=list[Job])
def list_jobs():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY id"
        ).fetchall()

    return [dict(row) for row in rows]


# ==========================================
# 11. 求人1件取得
# ==========================================

@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="求人が見つかりません",
        )

    return dict(row)


# ==========================================
# 12. 求人登録
# ==========================================

@app.post(
    "/jobs",
    response_model=Job,
    status_code=201,
)
def create_job(job: JobInput, _role: str = Depends(require_admin)):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO jobs (title, location, salary)
            VALUES (?, ?, ?)
            """,
            (
                job.title,
                job.location,
                job.salary,
            ),
        )
        job_id = cursor.lastrowid

    return Job(
        id=job_id,
        **job.model_dump(),
    )


# ==========================================
# 13. 求人更新
# ==========================================

@app.put("/jobs/{job_id}", response_model=Job)
def update_job(job_id: int, job: JobInput, _role: str = Depends(require_admin)):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET title = ?, location = ?, salary = ?
            WHERE id = ?
            """,
            (
                job.title,
                job.location,
                job.salary,
                job_id,
            ),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="求人が見つかりません",
            )

    return Job(
        id=job_id,
        **job.model_dump(),
    )


# ==========================================
# 14. 求人削除
# ==========================================

@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, _role: str = Depends(require_admin)):
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM jobs WHERE id = ?",
            (job_id,),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="求人が見つかりません",
            )

    return {
        "message": "求人を削除しました"
    }


# ==========================================
# 17. 固定トークン認証付き求人取得
# ==========================================

@app.get(
    "/secure/jobs",
    response_model=list[Job],
)
def get_secure_jobs(
    role: str = Depends(verify_token),
):
    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="求人情報へのアクセス権限がありません",
        )

    return list_jobs()


# ==========================================
# 18. OAuth 2.0学習用設定
# ==========================================

# ローカル学習専用の設定です。
# 本番用OAuth認可サーバーではありません。

OAUTH_CLIENTS = {
    OAUTH_CLIENT_ID: {
        "secret": OAUTH_CLIENT_SECRET,
        "scopes": {"jobs.read", "jobs.write"},
    }
}

ISSUED_TOKENS = {}

TOKEN_LIFETIME_SECONDS = 120


# ==========================================
# 19. アクセストークン発行
# ==========================================

@app.post("/token")
def issue_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form("jobs.read"),
):
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=400,
            detail="unsupported_grant_type",
        )

    client = OAUTH_CLIENTS.get(client_id)

    if client is None or not secrets.compare_digest(
        client_secret,
        client["secret"],
    ):
        raise HTTPException(
            status_code=401,
            detail="invalid_client",
        )

    requested_scopes = set(scope.split())

    if not requested_scopes.issubset(client["scopes"]):
        raise HTTPException(
            status_code=400,
            detail="invalid_scope",
        )

    access_token = secrets.token_urlsafe(32)

    ISSUED_TOKENS[access_token] = {
        "scopes": requested_scopes,
        "expires_at": (
            time.time() + TOKEN_LIFETIME_SECONDS
        ),
    }

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_LIFETIME_SECONDS,
        "scope": " ".join(sorted(requested_scopes)),
    }


# ==========================================
# 20. OAuthトークン検証
# ==========================================

def verify_oauth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security
    ),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="アクセストークンがありません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = ISSUED_TOKENS.get(
        credentials.credentials
    )

    if token_data is None:
        raise HTTPException(
            status_code=401,
            detail="無効なアクセストークンです",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if time.time() >= token_data["expires_at"]:
        raise HTTPException(
            status_code=401,
            detail="アクセストークンの有効期限が切れています",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


# ==========================================
# 21. OAuth認証付き求人取得
# ==========================================

@app.get(
    "/oauth/jobs",
    response_model=list[Job],
)
def get_oauth_jobs(
    token_data: dict = Depends(verify_oauth_token),
):
    if "jobs.read" not in token_data["scopes"]:
        raise HTTPException(
            status_code=403,
            detail="jobs.readスコープがありません",
        )

    return list_jobs()


# ==========================================
# 22. OAuth認証付き求人登録
# ==========================================

@app.post(
    "/oauth/jobs",
    response_model=Job,
    status_code=201,
)
def create_oauth_job(
    job: JobInput,
    token_data: dict = Depends(verify_oauth_token),
):
    if "jobs.write" not in token_data["scopes"]:
        raise HTTPException(
            status_code=403,
            detail="jobs.writeスコープがありません",
        )

    return create_job(job, _role="admin")
