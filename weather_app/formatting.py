from datetime import datetime
from typing import Any

from .config import WEEKDAYS


def format_number(value: Any, digits: int = 1) -> str:
	if isinstance(value, str):
		try:
			value = float(value)
		except ValueError:
			return "暂无"
	if not isinstance(value, int | float):
		return "暂无"
	rounded = round(value, digits)
	if rounded == int(rounded):
		return str(int(rounded))
	return f"{rounded:.{digits}f}"


def numeric_value(value: Any) -> float | None:
	if isinstance(value, str):
		try:
			return float(value)
		except ValueError:
			return None
	if isinstance(value, int | float):
		return float(value)
	return None


def format_chart_number(value: float) -> str:
	if value == int(value):
		return str(int(value))
	return f"{value:.1f}"


def format_datetime(value: str) -> str:
	parsed = datetime.fromisoformat(value)
	return f"{parsed.month}月{parsed.day}日 {parsed.strftime('%H:%M')}"


def format_time(value: str) -> str:
	return datetime.fromisoformat(value).strftime("%H:%M")


def format_qweather_date(value: str) -> str:
	parsed = datetime.fromisoformat(value)
	return f"{parsed.month}月{parsed.day}日 {WEEKDAYS[parsed.weekday()]}"


def format_month_day(value: str) -> str:
	parsed = datetime.fromisoformat(value)
	return f"{parsed.month}/{parsed.day}"


def format_iso_time(value: str) -> str:
	try:
		return datetime.fromisoformat(value).strftime("%H:%M")
	except ValueError:
		return value or "暂无"
