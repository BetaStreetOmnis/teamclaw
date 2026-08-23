from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse
import os
import subprocess
import sys
import time
import uuid

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from jetlinks_ai_api.env_utils import env_str  # noqa: E402


def _is_local_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    return normalized in {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class PostgresContainer:
    name: str
    url: str


def _start_postgres_container() -> PostgresContainer:
    container_name = f"jetlinks-ai-test-pg-{uuid.uuid4().hex[:10]}"
    password = "postgres"
    db_name = "jetlinks_ai_test"

    image = (env_str("TEST_PG_IMAGE", "") or "").strip()
    if not image:
        # Prefer a locally available image to avoid slow/blocked pulls in dev environments.
        candidates = ["postgres:16-alpine", "postgres:16", "postgres:15-alpine", "postgres:15"]
        for candidate in candidates:
            try:
                result = subprocess.run(
                    ["docker", "image", "inspect", candidate],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except FileNotFoundError:
                pytest.skip("Docker binary not available; skipping Postgres-backed tests")
            if result.returncode == 0:
                image = candidate
                break
        if not image:
            image = "postgres:16-alpine"

    try:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--pull=missing",
                "--rm",
                "--name",
                container_name,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-e",
                "POSTGRES_USER=postgres",
                "-e",
                f"POSTGRES_DB={db_name}",
                "-p",
                "0:5432",
                image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            timeout=120,
        )
        port_out = subprocess.check_output(
            ["docker", "port", container_name, "5432/tcp"],
            text=True,
        ).strip()
    except subprocess.TimeoutExpired:
        pytest.skip("Docker image pull/run timed out (need a local Postgres image or faster network)")
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Docker run failed: {e}")
    except FileNotFoundError:
        pytest.skip("Docker binary not available; skipping Postgres-backed tests")

    # Example outputs: "0.0.0.0:49153" or ":::49153"
    host_port = port_out.split(":")[-1]
    url = f"postgresql://postgres:{password}@127.0.0.1:{host_port}/{db_name}"

    import psycopg  # local import to keep module load light

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with psycopg.connect(url, connect_timeout=1) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            break
        except Exception:
            time.sleep(0.5)
    else:
        subprocess.run(["docker", "logs", container_name], check=False)
        subprocess.run(["docker", "stop", container_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise RuntimeError("Postgres test container did not become ready in time")

    return PostgresContainer(name=container_name, url=url)


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    explicit = (env_str("TEST_DB_URL", "") or "").strip()
    if explicit:
        parsed = urlparse(explicit)
        if not _is_local_host(parsed.hostname or "") and (env_str("TEST_DB_UNSAFE", "") or "").strip() != "1":
            raise RuntimeError(
                "Refusing to run tests against a non-local Postgres URL. "
                "Set JETLINKS_AI_TEST_DB_UNSAFE=1 (or legacy AISTAFF_TEST_DB_UNSAFE=1) if you really mean it."
            )
        yield explicit
        return

    container = _start_postgres_container()
    try:
        yield container.url
    finally:
        subprocess.run(["docker", "stop", container.name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture(scope="session")
def _apply_migrations(pg_url: str) -> None:
    os.environ["JETLINKS_AI_DB_URL"] = pg_url

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture
def _clean_db(pg_url: str) -> None:
    import psycopg

    # Keep alembic_version; wipe everything else.
    tables = [
        "memberships",
        "team_skills",
        "invites",
        "integration_tokens",
        "external_identities",
        "external_events",
        "team_requirements",
        "team_projects",
        "team_settings",
        "team_chatbi_datasources",
        "wecom_apps",
        "feishu_webhooks",
        "chat_messages",
        "chat_sessions",
        "file_records",
        "users",
        "teams",
        "meta",
    ]

    with psycopg.connect(pg_url) as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE")
        conn.commit()


@pytest.fixture
def app(pg_url: str, _apply_migrations: None, _clean_db: None, tmp_path: Path):
    os.environ["JETLINKS_AI_DB_URL"] = pg_url
    os.environ["JETLINKS_AI_DATA_DIR"] = str(tmp_path / "data")
    os.environ["JETLINKS_AI_OUTPUTS_DIR"] = str(tmp_path / "outputs")
    os.environ["JETLINKS_AI_JWT_SECRET"] = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
    os.environ.setdefault("JETLINKS_AI_ENABLE_SHELL", "0")
    os.environ.setdefault("JETLINKS_AI_ENABLE_WRITE", "0")
    os.environ.setdefault("JETLINKS_AI_ENABLE_BROWSER", "0")

    from jetlinks_ai_api.app_factory import create_app
    from jetlinks_ai_api.config import load_settings

    settings = load_settings()
    return create_app(settings)


@pytest.fixture
async def client(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
