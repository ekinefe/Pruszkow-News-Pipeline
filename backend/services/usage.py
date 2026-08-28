import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.config import settings


class UsageService:
    def __init__(self):
        self._path = settings.data_dir / "usage.json"
        self._quota_path = settings.data_dir / "quota.json"

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save(self, records: list[dict]):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def record(
        self,
        provider: str,
        model: str,
        operation: str,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        error: str = "",
    ):
        records = self._load()
        records.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "model": model,
                "operation": operation,
                "success": success,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "error": error,
            }
        )
        self._save(records)

    def get_records(
        self,
        provider: str = "",
        since: str = "",
        limit: int = 500,
    ) -> list[dict]:
        records = self._load()
        if provider:
            records = [r for r in records if r["provider"] == provider]
        if since:
            records = [r for r in records if r["ts"] >= since]
        return records[-limit:]

    def get_summary(self, provider: str = "") -> dict:
        records = self._load()
        if provider:
            records = [r for r in records if r["provider"] == provider]

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        def _count(reqs, since):
            return [r for r in reqs if r["ts"] >= since.isoformat()]

        def _sum_tokens(reqs):
            return sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in reqs)

        total = len(records)
        total_success = sum(1 for r in records if r["success"])
        total_fail = total - total_success
        total_tokens = _sum_tokens(records)

        today_reqs = _count(records, today_start)
        week_reqs = _count(records, week_start)
        month_reqs = _count(records, month_start)

        avg_latency = 0
        latencies = [r["latency_ms"] for r in records if r["latency_ms"] > 0]
        if latencies:
            avg_latency = round(sum(latencies) / len(latencies))

        by_provider = {}
        for r in records:
            p = r["provider"]
            if p not in by_provider:
                by_provider[p] = {"requests": 0, "success": 0, "fail": 0, "tokens": 0}
            by_provider[p]["requests"] += 1
            if r["success"]:
                by_provider[p]["success"] += 1
            else:
                by_provider[p]["fail"] += 1
            by_provider[p]["tokens"] += r.get("input_tokens", 0) + r.get("output_tokens", 0)

        daily = {}
        for r in records:
            day = r["ts"][:10]
            if day not in daily:
                daily[day] = {"requests": 0, "success": 0, "fail": 0, "tokens": 0}
            daily[day]["requests"] += 1
            if r["success"]:
                daily[day]["success"] += 1
            else:
                daily[day]["fail"] += 1
            daily[day]["tokens"] += r.get("input_tokens", 0) + r.get("output_tokens", 0)

        return {
            "total_requests": total,
            "total_success": total_success,
            "total_fail": total_fail,
            "total_tokens": total_tokens,
            "today_requests": len(today_reqs),
            "today_tokens": _sum_tokens(today_reqs),
            "week_requests": len(week_reqs),
            "week_tokens": _sum_tokens(week_reqs),
            "month_requests": len(month_reqs),
            "month_tokens": _sum_tokens(month_reqs),
            "avg_latency_ms": avg_latency,
            "by_provider": by_provider,
            "daily": daily,
            "resets_in": {
                "daily": str(today_start + timedelta(days=1) - now).split(".")[0],
                "weekly": str(week_start + timedelta(weeks=1) - now).split(".")[0],
                "monthly": str((month_start + timedelta(days=32)).replace(day=1) - now).split(".")[0],
            },
        }

    # --- Quota ---

    def _load_quota(self) -> dict:
        defaults = {
            "daily_requests": 0,
            "weekly_requests": 0,
            "monthly_requests": 0,
            "daily_tokens": 0,
            "weekly_tokens": 0,
            "monthly_tokens": 0,
        }
        if not self._quota_path.exists():
            return defaults
        try:
            with open(self._quota_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
            return defaults
        except (json.JSONDecodeError, IOError):
            return defaults

    def _save_quota(self, quota: dict):
        with open(self._quota_path, "w", encoding="utf-8") as f:
            json.dump(quota, f, ensure_ascii=False, indent=2)

    def get_quota(self) -> dict:
        return self._load_quota()

    def set_quota(self, quota: dict):
        current = self._load_quota()
        current.update(quota)
        self._save_quota(current)

    def reset_usage(self):
        self._save([])


usage_service = UsageService()
