from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.app.models.chart import ChartRecord


class InMemoryChartRepository:
    """Repository used for the initial workflow implementation before the Postgres-backed version is wired in."""

    def __init__(self) -> None:
        self._charts: Dict[int, ChartRecord] = {}
        self._next_id = 1

    def create_chart(self, chart: ChartRecord) -> ChartRecord:
        if chart.chart_id is None:
            chart.chart_id = self._next_id
            self._next_id += 1
        self._charts[chart.chart_id] = chart
        return chart

    def get_chart(self, chart_id: int) -> Optional[ChartRecord]:
        return self._charts.get(chart_id)

    def list_charts(self) -> List[ChartRecord]:
        return sorted(self._charts.values(), key=lambda item: item.chart_id)

    def update_chart(self, chart: ChartRecord) -> ChartRecord:
        chart.updated_at = datetime.now(timezone.utc)
        if chart.chart_id is not None:
            self._charts[chart.chart_id] = chart
        return chart


class JsonChartRepository(InMemoryChartRepository):
    """Persistent local chart queue used when PostgreSQL is not configured."""

    def __init__(self, file_path: str = "instance/charts.json") -> None:
        self.file_path = file_path
        super().__init__()
        self._load()

    def create_chart(self, chart: ChartRecord) -> ChartRecord:
        chart = super().create_chart(chart)
        self._save()
        return chart

    def update_chart(self, chart: ChartRecord) -> ChartRecord:
        chart = super().update_chart(chart)
        self._save()
        return chart

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            return
        with open(self.file_path, "r", encoding="utf-8") as stream:
            for raw_chart in json.load(stream):
                for field in ("locked_at", "locked_until", "uploaded_at", "created_at", "updated_at"):
                    if raw_chart.get(field):
                        raw_chart[field] = datetime.fromisoformat(raw_chart[field])
                chart = ChartRecord(**raw_chart)
                super().create_chart(chart)
                if chart.chart_id is not None:
                    self._next_id = max(self._next_id, chart.chart_id + 1)

    def _save(self) -> None:
        directory = os.path.dirname(self.file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        charts = []
        for chart in self._charts.values():
            raw_chart = chart.__dict__.copy()
            for field in ("locked_at", "locked_until", "uploaded_at", "created_at", "updated_at"):
                if raw_chart[field]:
                    raw_chart[field] = raw_chart[field].isoformat()
            charts.append(raw_chart)
        temporary_path = f"{self.file_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump(charts, stream, indent=2)
        os.replace(temporary_path, self.file_path)
