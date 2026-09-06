"""编译任务持久化仓库（JOB-03/04/05）。

把 CompileJobManager 的持久化职责抽象为 JobRepository 接口：

- ``JsonJobRepository``：原有 JSON 原子替换文件（单进程，向后兼容）；
- ``SQLiteJobRepository``：SQLite WAL 事务存储（默认），携带 lease /
  heartbeat / 幂等键列，支持跨进程重启恢复与 JSON 自动迁移。

选择方式：环境变量 ``DOCHRIS_JOB_STORE=sqlite``（默认）或 ``json``。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = frozenset({"queued", "running", "cancelling"})
ACTIVE_SQL_STATUSES = frozenset({"queued", "running", "cancelling"})


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class JobRepository(ABC):
    """编译任务的持久化接口。

    实现负责按 job_id 存取完整任务记录；manager 仍持有进程内运行态，
    仓库只保证崩溃/重启后可恢复。
    """

    supports_lease = False
    """True 表示仓库实现了 lease 恢复语义（recover_stale_leases 已处理中断标记）。"""

    @abstractmethod
    def save(self, record: dict[str, Any]) -> None:
        """持久化单条任务记录（整记录覆盖写）。"""

    @abstractmethod
    def get(self, job_id: str) -> dict[str, Any] | None:
        """按 job_id 读取记录，不存在返回 None。"""

    @abstractmethod
    def list_all(self) -> list[dict[str, Any]]:
        """按插入时间升序返回全部记录（最旧在前）。"""

    @abstractmethod
    def delete(self, job_id: str) -> None:
        """删除单条记录。"""

    def close(self) -> None:  # noqa: B027
        """释放底层资源（文件句柄/连接）。"""

    def recover_stale_leases(self, owner_id: str) -> list[dict[str, Any]]:  # noqa: B027
        """启动恢复钩子：默认无操作，返回启动时应加载的记录。"""
        return self.list_all()

    def is_cancel_requested(self, job_id: str) -> bool:  # noqa: B027
        """默认不支持（JSON/无持久化仓库为单进程，本地内存即可见）。"""
        return False

    def find_active(self, active_statuses: frozenset[str] | set[str]) -> list[dict[str, Any]]:
        """按插入时间倒序返回活动任务（新任务在前）。"""
        return [
            record
            for record in reversed(self.list_all())
            if record.get("status") in active_statuses
        ]


class JsonJobRepository(JobRepository):
    """原有 JSON 快照文件实现（原子替换 + 损坏隔离）。"""

    def __init__(self, store_path: Path) -> None:
        self.store_path = Path(store_path)

    def save(self, record: dict[str, Any]) -> None:
        """整文件快照式保存：以 job_id 为主键合并后原子写回。"""
        jobs: dict[str, dict[str, Any]] = {}
        if self.store_path.is_file():
            try:
                payload = json.loads(self.store_path.read_text(encoding="utf-8"))
                parse_failed = not isinstance(payload, dict)
            except (OSError, ValueError):
                parse_failed = True
            if parse_failed:
                # 损坏文件先隔离（保留故障证据），再写新快照——禁止静默覆盖
                logger.warning("读取 JSON 任务历史失败，隔离损坏文件后重建快照", exc_info=True)
                self._quarantine_corrupt_store()
            else:
                for item in payload.get("jobs", []):
                    if isinstance(item, dict) and item.get("job_id"):
                        jobs[str(item["job_id"])] = item
        jobs[str(record["job_id"])] = record
        self._write_snapshot(list(jobs.values()))

    def get(self, job_id: str) -> dict[str, Any] | None:
        if not self.store_path.is_file():
            return None
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        for item in payload.get("jobs", []) if isinstance(payload, dict) else []:
            if isinstance(item, dict) and item.get("job_id") == job_id:
                return item
        return None

    def list_all(self) -> list[dict[str, Any]]:
        if not self.store_path.is_file():
            return []
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("无法读取编译任务历史，隔离损坏文件", exc_info=True)
            self._quarantine_corrupt_store()
            return []
        if not isinstance(payload, dict):
            self._quarantine_corrupt_store()
            return []
        return [item for item in payload.get("jobs", []) if isinstance(item, dict)]

    def _quarantine_corrupt_store(self) -> None:
        """Preserve an unreadable store for diagnosis and recreate a valid empty store."""
        if not self.store_path.exists():
            return
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine_path = self.store_path.with_name(
            f"{self.store_path.stem}.corrupt-{timestamp}{self.store_path.suffix}"
        )
        try:
            self.store_path.replace(quarantine_path)
        except OSError:
            logger.warning("无法隔离损坏的编译任务历史", exc_info=True)
            return
        self._write_snapshot([])

    def delete(self, job_id: str) -> None:
        remaining = [j for j in self.list_all() if j.get("job_id") != job_id]
        self._write_snapshot(remaining)

    def _write_snapshot(self, jobs: list[dict[str, Any]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.store_path.parent,
                prefix=f".{self.store_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = handle.name
                json.dump({"version": 1, "jobs": jobs}, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.store_path)
        except OSError:
            # fail-closed：写盘失败必须让调用方感知，禁止无持久化启动编译
            logger.warning("无法保存编译任务历史", exc_info=True)
            raise
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                os.unlink(temp_path)


class SQLiteJobRepository(JobRepository):
    """SQLite WAL 事务存储（JOB-04/05）。

    - WAL + NORMAL sync：单写多读，崩溃安全；
    - 每条任务一个事务（逐任务落盘，不再整文件重写）；
    - lease/heartbeat/幂等键为独立列，供启动恢复与去重使用。
    """

    supports_lease = True

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS compile_jobs (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL UNIQUE,
        idempotency_key TEXT,
        status TEXT NOT NULL,
        lease_owner TEXT,
        lease_expires_at TEXT,
        heartbeat_at TEXT,
        cancel_requested INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        record TEXT NOT NULL
    );
    """

    def __init__(self, db_path: Path, *, migrate_from: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None → 显式事务（claim 的 BEGIN IMMEDIATE 需要跨进程写互斥）
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        # 旧库可能存在同名普通索引（升级前版本）；先删再建唯一索引。
        # 若历史数据已有重复幂等键，唯一索引会创建失败并阻塞启动——
        # 升级前先做确定性去重（同一 key 保留最新 seq）
        self._conn.executescript(self._SCHEMA)
        dups = self._conn.execute(
            """
            SELECT COUNT(*) FROM compile_jobs
            WHERE idempotency_key IS NOT NULL
              AND seq NOT IN (
                  SELECT MAX(seq) FROM compile_jobs
                  WHERE idempotency_key IS NOT NULL GROUP BY idempotency_key
              )
            """
        ).fetchone()[0]
        if dups:
            # 不删除任务历史：仅把重复行的冲突键置空（保留最新一条持有键），
            # 历史完整保留且唯一索引可以创建
            logger.warning(
                "发现 %d 条重复幂等键的旧任务记录，升级时保留最新一条的键，其余键置空",
                dups,
            )
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    """
                    UPDATE compile_jobs SET idempotency_key = NULL
                    WHERE idempotency_key IS NOT NULL
                      AND seq NOT IN (
                          SELECT MAX(seq) FROM compile_jobs
                          WHERE idempotency_key IS NOT NULL GROUP BY idempotency_key
                      )
                    """
                )
                self._conn.execute("COMMIT")
            except sqlite3.Error:
                self._conn.execute("ROLLBACK")
                raise
        try:
            self._conn.execute(
                "ALTER TABLE compile_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # 列已存在
        try:
            self._conn.execute("ALTER TABLE compile_jobs ADD COLUMN created_at TEXT")
            self._conn.execute(
                """
                UPDATE compile_jobs
                SET created_at = json_extract(record, '$.created_at')
                WHERE created_at IS NULL
                """
            )
        except sqlite3.OperationalError:
            pass  # 列已存在
        self._conn.execute("DROP INDEX IF EXISTS idx_compile_jobs_idem")
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_compile_jobs_idem
                ON compile_jobs(idempotency_key) WHERE idempotency_key IS NOT NULL
            """
        )
        if migrate_from is not None:
            self._migrate_from_json(Path(migrate_from))

    # -- 基础 CRUD -------------------------------------------------

    def save(self, record: dict[str, Any]) -> None:
        job_id = str(record["job_id"])
        payload = json.dumps(record, ensure_ascii=False)
        with self._conn:
            # 注意：cancel_requested 不在写入列中——它只能由 mark_cancel 置位，
            # owner 侧的全记录持久化不允许覆盖取消标记（P1 review 修复）
            self._conn.execute(
                """
                INSERT INTO compile_jobs
                    (job_id, idempotency_key, status, lease_owner,
                     lease_expires_at, heartbeat_at, cancel_requested, created_at, record)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    idempotency_key=excluded.idempotency_key,
                    status=excluded.status,
                    lease_owner=excluded.lease_owner,
                    lease_expires_at=excluded.lease_expires_at,
                    heartbeat_at=excluded.heartbeat_at,
                    record=excluded.record
                """,
                (
                    job_id,
                    record.get("idempotency_key"),
                    str(record.get("status", "")),
                    record.get("lease_owner"),
                    record.get("lease_expires_at"),
                    record.get("heartbeat_at"),
                    record.get("created_at"),
                    payload,
                ),
            )

    def get(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT record FROM compile_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        try:
            result: dict[str, Any] = json.loads(row["record"])
            return result
        except ValueError:
            logger.warning("任务 %s 的记录损坏", job_id)
            return None

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT record FROM compile_jobs ORDER BY seq ASC").fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(json.loads(row["record"]))
            except ValueError:
                logger.warning("跳过损坏的任务记录")
        return results

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        """按幂等键取最新的一条任务（JOB-05）。"""
        row = self._conn.execute(
            """
            SELECT record FROM compile_jobs WHERE idempotency_key = ?
            ORDER BY seq DESC LIMIT 1
            """,
            (key,),
        ).fetchone()
        if row is None:
            return None
        try:
            result: dict[str, Any] = json.loads(row["record"])
            return result
        except ValueError:
            return None

    def delete(self, job_id: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM compile_jobs WHERE job_id = ?", (job_id,))

    def find_active(self, active_statuses: frozenset[str] | set[str]) -> list[dict[str, Any]]:
        """活动任务（新在前）。lease 已过期的 running 视为非活动（自愈语义）。"""
        if set(active_statuses) != ACTIVE_SQL_STATUSES:
            raise ValueError(f"unexpected active statuses: {active_statuses!r}")
        cutoff = (datetime.fromisoformat(_utc_now_iso()) - timedelta(seconds=300.0)).isoformat()
        rows = self._conn.execute(
            """
            SELECT record FROM compile_jobs
            WHERE status IN ('queued', 'running', 'cancelling')
              AND (
                  (lease_expires_at IS NOT NULL AND lease_expires_at > ?)
                  OR
                  (lease_expires_at IS NULL AND created_at > ?)
              )
            ORDER BY seq DESC
            """,
            (_utc_now_iso(), cutoff),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                results.append(json.loads(row["record"]))
            except (TypeError, ValueError):
                continue
        return results

    # -- 原子任务准入（多进程互斥 + 幂等）--------------------------

    def claim_job(
        self,
        record: dict[str, Any],
        idempotency_key: str | None,
        active_statuses: frozenset[str] | set[str],
        zombie_grace_seconds: float = 300.0,
    ) -> tuple[bool, dict[str, Any] | None]:
        """事务化任务准入：BEGIN IMMEDIATE 下一次完成互斥检查与插入。

        拒绝条件（返回 (False, 已存在任务)）：
        1. 库中已有活动任务（queued/running/cancelling 且 lease 未过期）——
           跨进程互斥，防止多个 API worker 同时接受编译；
        2. 幂等键命中既有任务。

        Raises:
            sqlite3.Error: 持久化失败（磁盘满/锁超时等）——调用方应 fail-closed。
        """
        now = _utc_now_iso()
        job_id = str(record["job_id"])
        payload = json.dumps(record, ensure_ascii=False)
        # 状态集合是代码自有常量（非用户输入），内联避免动态 SQL 拼接（bandit B608）
        if set(active_statuses) != ACTIVE_SQL_STATUSES:
            raise ValueError(f"unexpected active statuses: {active_statuses!r}")

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            # 1) 幂等解析优先：重放已完成/失败任务的 key 必须原样返回该任务，
            #    而不是被当前活跃任务互斥逻辑顶替
            if idempotency_key:
                dup = self._conn.execute(
                    """
                    SELECT record FROM compile_jobs
                    WHERE idempotency_key = ? ORDER BY seq DESC LIMIT 1
                    """,
                    (idempotency_key,),
                ).fetchone()
                if dup is not None:
                    self._conn.execute("ROLLBACK")
                    return False, self._loads_or_none(dup["record"])

            # 2) 活跃互斥：仅对全新 key 生效
            cutoff = (
                datetime.fromisoformat(now) - timedelta(seconds=zombie_grace_seconds)
            ).isoformat()
            blocking = self._conn.execute(
                """
                SELECT record FROM compile_jobs
                WHERE status IN ('queued', 'running', 'cancelling')
                  AND (
                      (lease_expires_at IS NOT NULL AND lease_expires_at > ?)
                      OR
                      (lease_expires_at IS NULL AND created_at > ?)
                  )
                LIMIT 1
                """,
                (now, cutoff),
            ).fetchone()
            if blocking is not None:
                self._conn.execute("ROLLBACK")
                return False, self._loads_or_none(blocking["record"])

            self._conn.execute(
                """
                INSERT INTO compile_jobs
                    (job_id, idempotency_key, status, lease_owner,
                     lease_expires_at, heartbeat_at, cancel_requested, created_at, record)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    job_id,
                    idempotency_key,
                    str(record.get("status", "")),
                    record.get("lease_owner"),
                    record.get("lease_expires_at"),
                    record.get("heartbeat_at"),
                    record.get("created_at"),
                    payload,
                ),
            )
            self._conn.execute("COMMIT")
            return True, None
        except Exception:
            try:
                self._conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    def mark_cancel(self, job_id: str) -> dict[str, Any] | None:
        """条件化取消写入：仅当任务仍为 queued/running/cancelling 时置 cancelling。

        事务内重查状态，杜绝"取消者的过期快照复活已完成任务"（P1 review）。
        Returns:
            取消写入后的最新记录；任务不存在或已终结时返回终结状态的记录。
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT record FROM compile_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return None
            try:
                record = json.loads(row["record"])
            except (TypeError, ValueError):
                self._conn.execute("COMMIT")
                return None

            if record.get("status") in ("completed", "failed", "cancelled", "interrupted"):
                self._conn.execute("COMMIT")
                fresh: dict[str, Any] = record
                return fresh  # 已终结：原样返回，不复活

            patched = dict(record)
            patched["cancel_requested"] = True
            patched["status"] = "cancelling"
            patched["message"] = "正在取消编译"
            now = _utc_now_iso()
            patched.setdefault("created_at", now)
            self._conn.execute(
                """
                UPDATE compile_jobs
                SET status = 'cancelling', cancel_requested = 1, record = ?
                WHERE job_id = ?
                """,
                (json.dumps(patched, ensure_ascii=False), job_id),
            )
            self._conn.execute("COMMIT")
            return patched
        except Exception:
            try:
                self._conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    def is_cancel_requested(self, job_id: str) -> bool:
        """owner 侧轮询：任务是否已被请求取消。"""
        row = self._conn.execute(
            "SELECT cancel_requested FROM compile_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return bool(row and row["cancel_requested"])

    @staticmethod
    def _loads_or_none(raw: Any) -> dict[str, Any] | None:
        try:
            result: dict[str, Any] = json.loads(raw)
            return result
        except (TypeError, ValueError):
            return None

    # -- lease 恢复（JOB-05）--------------------------------------

    def recover_stale_leases(self, owner_id: str) -> list[dict[str, Any]]:
        """启动恢复：过期的 running/cancelling lease 标记为 interrupted。

        - lease 过期（或无 lease）的活动任务 → 本进程接管：标记 interrupted
          （与旧 JSON 恢复语义一致，由 manager 完成）；
        - lease 仍有效且属于其他进程的任务 → 原样保留（不恢复也不阻塞查询），
          交给持有者继续完成。

        Returns:
            全部记录（含被其他进程持有的），按插入顺序。
        """
        now = _utc_now_iso()
        stale_ids: list[str] = []
        for record in self.list_all():
            if record.get("status") not in ACTIVE_STATUSES:
                continue
            expires_at = record.get("lease_expires_at")
            owner = record.get("lease_owner")
            if expires_at and expires_at > now and owner and owner != owner_id:
                continue  # 其他进程持有有效 lease，不动
            stale_ids.append(str(record["job_id"]))

        if stale_ids:
            with self._conn:
                for job_id in stale_ids:
                    row = self._conn.execute(
                        "SELECT record FROM compile_jobs WHERE job_id = ?", (job_id,)
                    ).fetchone()
                    if row is None:
                        continue
                    try:
                        record = json.loads(row["record"])
                    except ValueError:
                        continue
                    if record.get("status") not in ACTIVE_STATUSES:
                        continue
                    record["status"] = "interrupted"
                    record["message"] = "服务重启，编译任务已中断"
                    record["current_files"] = []
                    record["error"] = "ServiceRestart: 编译服务在任务完成前退出"
                    record["finished_at"] = now
                    record["lease_owner"] = None
                    record["lease_expires_at"] = None
                    self._conn.execute(
                        "UPDATE compile_jobs SET status = ?, record = ? WHERE job_id = ?",
                        ("interrupted", json.dumps(record, ensure_ascii=False), job_id),
                    )
        return self.list_all()

    # -- 迁移与清理 ------------------------------------------------

    def _migrate_from_json(self, json_path: Path) -> None:
        """旧 JSON 快照一次性导入（仅在 SQLite 为空时执行）。"""
        existing = self._conn.execute("SELECT COUNT(*) FROM compile_jobs").fetchone()[0]
        if existing > 0 or not json_path.is_file():
            return
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("无法读取旧 JSON 任务历史，跳过迁移", exc_info=True)
            return
        records = payload.get("jobs", []) if isinstance(payload, dict) else []

        # 确定性去重：同一幂等键保留文件中最后一条（视为最新），其余键置空后
        # 照常迁移——历史完整保留，不因唯一索引而丢任务
        by_key: dict[str, dict[str, Any]] = {}
        ordered: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict) or not record.get("job_id"):
                continue
            key = record.get("idempotency_key")
            if key:
                if key in by_key:
                    demoted = by_key[key]
                    demoted["idempotency_key"] = None
                by_key[key] = record
            ordered.append(record)

        imported = 0
        with self._conn:
            for record in ordered:
                self.save(dict(record))
                imported += 1
        if imported:
            logger.info("已从 %s 迁移 %d 条编译任务记录", json_path.name, imported)

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:  # pragma: no cover - 连接已损坏时忽略
            pass


def build_repository(workspace: str | Path) -> tuple[JobRepository, str]:
    """按环境变量构建任务仓库（供 API 装配使用）。

    ``DOCHRIS_JOB_STORE``：``sqlite``（默认）或 ``json``。

    Returns:
        (repository, kind) 元组，kind ∈ {"sqlite", "json"}。
    """
    data_dir = Path(workspace) / "data"
    kind = os.environ.get("DOCHRIS_JOB_STORE", "sqlite").strip().lower()
    if kind in {"json", "file"}:
        return JsonJobRepository(data_dir / "compile-jobs.json"), "json"
    return (
        SQLiteJobRepository(
            data_dir / "compile-jobs.db", migrate_from=data_dir / "compile-jobs.json"
        ),
        "sqlite",
    )
