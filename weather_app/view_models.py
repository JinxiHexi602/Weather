import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import (
    DEFAULT_LOCATION_ID,
	HOURLY_PREVIEW_COUNT,
	QWEATHER_HOME_LIFE_TYPES,
	QWEATHER_HOME_POLLUTANTS,
	QWEATHER_LIFE_ICONS,
	QWEATHER_LIFE_TYPES,
	QWEATHER_POLLUTANT_LABELS,
)
from .formatting import (
    format_chart_number,
    format_datetime,
    format_iso_time,
    format_number,
    format_qweather_date,
    format_time,
    numeric_value,
)
from .icons import qweather_background_theme, qweather_icon
from .qweather import load_qweather_payload


LOCAL_TIMEZONE = timezone(timedelta(hours=8))


def parse_clock_minutes(value: Any) -> int | None:
	text = str(value or "").strip()
	parts = text.split(":")
	if len(parts) < 2:
		return None
	try:
		hour = int(parts[0])
		minute = int(parts[1])
	except ValueError:
		return None
	if not 0 <= hour <= 23 or not 0 <= minute <= 59:
		return None
	return hour * 60 + minute


def time_phase_from_minutes(current: int, sunrise: Any, sunset: Any) -> str:
	sunrise_minutes = parse_clock_minutes(sunrise)
	sunset_minutes = parse_clock_minutes(sunset)
	if sunrise_minutes is None or sunset_minutes is None:
		return fallback_time_phase(current)

	dawn_start = max(0, sunrise_minutes - 60)
	dawn_end = min(24 * 60, sunrise_minutes + 60)
	dusk_start = max(0, sunset_minutes - 60)
	dusk_end = min(24 * 60, sunset_minutes + 60)

	if dawn_start <= current < dawn_end:
		return "dawn"
	if dusk_start <= current < dusk_end:
		return "dusk"
	if dawn_end <= current < dusk_start:
		return "day"
	return "night"


def fallback_time_phase(current: int) -> str:
	if 330 <= current < 480:
		return "dawn"
	if 480 <= current < 1050:
		return "day"
	if 1050 <= current < 1200:
		return "dusk"
	return "night"


def build_background_time(daily: dict[str, Any], now: datetime) -> dict[str, str]:
	today = daily.get("daily", [{}])[0] if daily.get("daily") else {}
	current_minutes = now.hour * 60 + now.minute
	sunrise = today.get("sunrise", "")
	sunset = today.get("sunset", "")
	return {
		"sunrise": sunrise,
		"sunset": sunset,
		"updated_at_iso": now.isoformat(timespec="seconds"),
		"phase": time_phase_from_minutes(current_minutes, sunrise, sunset),
	}


def qweather_wind(item: dict[str, Any]) -> str:
	speed = format_number(item.get("windSpeed"), 0)
	if speed == "暂无":
		return item.get("windDir", "暂无")
	return f"{item.get('windDir', '暂无')} {speed} km/h"


def qweather_percent(value: Any) -> str:
	number = format_number(value, 0)
	return f"{number}%" if number != "暂无" else number


def qweather_metric(value: Any, unit: str, digits: int = 0) -> str:
	number = format_number(value, digits)
	if unit == "°":
		return f"{number}°" if number != "暂无" else number
	return f"{number} {unit}" if number != "暂无" else number


def qweather_air_index(air_current: dict[str, Any]) -> dict[str, Any]:
	indexes = air_current.get("indexes", [])
	for item in indexes:
		if item.get("code") == "cn-mee":
			return item
	return indexes[0] if indexes else {}


def qweather_pollutants(air_current: dict[str, Any]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	pollutants_by_code = {pollutant.get("code"): pollutant for pollutant in air_current.get("pollutants", [])}
	for code in QWEATHER_HOME_POLLUTANTS:
		pollutant = pollutants_by_code.get(code)
		if not pollutant:
			continue
		concentration = pollutant.get("concentration", {})
		unit = concentration.get("unit", "μg/m³")
		items.append({
			"label": QWEATHER_POLLUTANT_LABELS.get(code, pollutant.get("name", "暂无")),
			"value": qweather_metric(concentration.get("value"), unit, 1 if code == "co" else 0),
			"full_name": pollutant.get("fullName", pollutant.get("name", "")),
		})
	return items


def build_minutely(minutely: dict[str, Any]) -> dict[str, Any]:
	points = []
	values = []
	for item in minutely.get("minutely", [])[:24]:
		value = numeric_value(item.get("precip")) or 0
		values.append(value)
		points.append({
			"time": format_iso_time(item.get("fxTime", "")),
			"value": format_number(value),
			"type": item.get("type", "rain"),
			"is_rain": value > 0,
		})
	max_value = max(values, default=0)
	for point, value in zip(points, values, strict=False):
		point["bar_height"] = chart_coord(max(6, (value / max_value * 48) if max_value else 6))
	return {
		"active": any(value > 0 for value in values),
		"summary": minutely.get("summary", "暂无分钟级降水数据"),
		"points": points,
		"total": qweather_metric(sum(values), "mm", 1),
		"peak": qweather_metric(max_value, "mm", 1),
	}


def build_weather_alerts(weather_alert: dict[str, Any]) -> dict[str, Any]:
	alerts = weather_alert.get("alerts", [])
	items = []
	for alert in alerts[:3]:
		event_type = alert.get("eventType") or {}
		color = alert.get("color") or {}
		title = alert.get("headline") or "天气预警"
		severity = color.get("code") or alert.get("severity") or "关注"
		items.append({
			"title": title,
			"type": event_type.get("name") or "天气",
			"severity": severity,
			"time": format_iso_time(alert.get("effectiveTime") or alert.get("issuedTime") or ""),
			"text": alert.get("description") or alert.get("instruction") or "",
		})
	attributions = weather_alert.get("metadata", {}).get("attributions", [])
	return {
		"active": bool(items),
		"count": len(alerts),
		"summary": f"当前有 {len(alerts)} 条天气预警" if alerts else "当前暂无天气预警",
		"list": items,
		"attributions": attributions,
	}


def build_qweather_life_index(indices: dict[str, Any]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for entry in indices.get("daily", []):
		life_type = str(entry.get("type"))
		if life_type not in QWEATHER_HOME_LIFE_TYPES:
			continue
		label = QWEATHER_LIFE_TYPES.get(life_type, entry.get("name", "生活指数"))
		desc = entry.get("category", "暂无")
		items.append({
			"label": label,
			"index": entry.get("level", "暂无"),
			"desc": desc,
			"text": entry.get("text", ""),
			"icon": QWEATHER_LIFE_ICONS.get(life_type, "i-leaf"),
			"tone": life_index_tone(life_type, desc),
		})
	return items


def life_index_tone(life_type: str, desc: str) -> str:
	text = str(desc)
	if any(keyword in text for keyword in ("较不", "较强", "较差", "偏高", "炎热", "寒冷")):
		return "warning"
	if any(keyword in text for keyword in ("不宜", "易发", "很强", "极强", "差")):
		return "danger"
	if any(keyword in text for keyword in ("适宜", "舒适", "弱", "良", "较好", "较舒适")):
		return "good"
	if life_type == "5" and any(keyword in text for keyword in ("中等", "中")):
		return "warning"
	return "neutral"


def build_qweather_hourly(hourly: dict[str, Any]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for entry in hourly.get("hourly", []):
		temperature_value = numeric_value(entry.get("temp"))
		temperature = f"{format_number(entry.get('temp'), 0)}°C"
		precipitation = f"{format_number(entry.get('precip'))} mm"
		items.append({
			"datetime": format_datetime(entry["fxTime"]),
			"time": format_time(entry["fxTime"]),
			"icon": qweather_icon(entry.get("icon"), entry.get("text", "")),
			"sky": entry.get("text", "暂无"),
			"temperature": temperature,
			"temperature_value": temperature_value,
			"apparent_temperature": temperature,
			"precipitation": precipitation,
			"probability": qweather_percent(entry.get("pop")),
			"wind": qweather_wind(entry),
			"humidity": qweather_percent(entry.get("humidity")),
			"cloudrate": qweather_percent(entry.get("cloud")),
			"pressure": f"{format_number(entry.get('pressure'), 0)} hPa",
			"visibility": "暂无",
			"dswrf": "暂无",
			"aqi": "暂无",
			"pm25": "暂无",
			"details": [
				{"label": "降水", "value": precipitation, "icon": "i-rain"},
				{"label": "降水概率", "value": qweather_percent(entry.get("pop")), "icon": "i-droplet"},
				{"label": "风", "value": qweather_wind(entry), "icon": "i-wind"},
				{"label": "湿度", "value": qweather_percent(entry.get("humidity")), "icon": "i-droplet"},
				{"label": "云量", "value": qweather_percent(entry.get("cloud")), "icon": "i-cloud"},
				{"label": "气压", "value": f"{format_number(entry.get('pressure'), 0)} hPa", "icon": "i-gauge"},
				{"label": "露点", "value": f"{format_number(entry.get('dew'), 0)}°C", "icon": "i-droplet"},
			],
		})
	return items


def chart_coord(value: float) -> str:
	return f"{value:.2f}".rstrip("0").rstrip(".")


def build_hourly_chart(hourly_items: list[dict[str, Any]]) -> dict[str, Any]:
	visible_items = hourly_items[:HOURLY_PREVIEW_COUNT]
	values = [item.get("temperature_value") for item in visible_items if isinstance(item.get("temperature_value"), int | float)]
	if not visible_items or not values:
		return {
			"points": [],
			"temperature_range": "暂无",
		}

	min_temp = math.floor(min(values))
	max_temp = math.ceil(max(values))
	if min_temp == max_temp:
		min_temp -= 1
		max_temp += 1

	temp_span = max_temp - min_temp

	points: list[dict[str, Any]] = []
	for index, item in enumerate(visible_items):
		temp_value = item.get("temperature_value")
		if not isinstance(temp_value, int | float):
			temp_value = min_temp
		bar_height = max(10, (temp_value - min_temp) / temp_span * 44 + 14)
		points.append({
			"index": index,
			"bar_height_px": chart_coord(bar_height),
			"time": item["time"],
			"icon": item["icon"],
			"sky": item["sky"],
			"temperature": format_chart_number(temp_value),
			"probability": item["probability"],
		})

	return {
		"points": points,
		"temperature_range": f"{min_temp}°C - {max_temp}°C",
	}


def build_qweather_daily(daily: dict[str, Any], life_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for entry in daily.get("daily", []):
		temperature = f"{format_number(entry.get('tempMin'), 0)}-{format_number(entry.get('tempMax'), 0)}°C"
		day_sky = entry.get("textDay", "暂无")
		night_sky = entry.get("textNight", "暂无")
		items.append({
			"date": format_qweather_date(entry["fxDate"]),
			"icon": qweather_icon(entry.get("iconDay"), day_sky),
			"sky": day_sky if day_sky == night_sky else f"{day_sky}转{night_sky}",
			"temperature": temperature,
			"precipitation": f"{format_number(entry.get('precip'))} mm",
			"sunrise": entry.get("sunrise", "暂无"),
			"sunset": entry.get("sunset", "暂无"),
			"parts": [
				{
					"label": "日间",
					"sky": day_sky,
					"temperature": temperature,
					"precipitation": f"{format_number(entry.get('precip'))} mm",
					"wind": qweather_wind({"windDir": entry.get("windDirDay"), "windSpeed": entry.get("windSpeedDay")}),
				},
				{
					"label": "夜间",
					"sky": night_sky,
					"temperature": temperature,
					"precipitation": f"{format_number(entry.get('precip'))} mm",
					"wind": qweather_wind({"windDir": entry.get("windDirNight"), "windSpeed": entry.get("windSpeedNight")}),
				},
			],
			"metrics": [
				{"label": "湿度", "value": qweather_percent(entry.get("humidity")), "icon": "i-droplet"},
				{"label": "紫外线", "value": entry.get("uvIndex", "暂无"), "icon": "i-sun"},
				{"label": "能见度", "value": f"{format_number(entry.get('vis'), 0)} km", "icon": "i-eye"},
			],
			"details": [
				{"label": "日间", "value": f"{day_sky} · {format_number(entry.get('tempMax'), 0)}°C", "icon": qweather_icon(entry.get("iconDay"), day_sky)},
				{"label": "夜间", "value": f"{night_sky} · {format_number(entry.get('tempMin'), 0)}°C", "icon": qweather_icon(entry.get("iconNight"), night_sky)},
				{"label": "降水", "value": f"{format_number(entry.get('precip'))} mm", "icon": "i-rain"},
				{"label": "日出", "value": entry.get("sunrise", "暂无"), "icon": "i-sun"},
				{"label": "日落", "value": entry.get("sunset", "暂无"), "icon": "i-moon"},
				{"label": "湿度", "value": qweather_percent(entry.get("humidity")), "icon": "i-droplet"},
				{"label": "云量", "value": qweather_percent(entry.get("cloud")), "icon": "i-cloud"},
				{"label": "气压", "value": f"{format_number(entry.get('pressure'), 0)} hPa", "icon": "i-gauge"},
				{"label": "紫外线", "value": entry.get("uvIndex", "暂无"), "icon": "i-sun"},
			],
			"life_index": life_index if entry["fxDate"] == daily.get("daily", [{}])[0].get("fxDate") else [],
		})
	return items


def selected_location(location_id: str | None) -> dict[str, str]:
	location_id = location_id or DEFAULT_LOCATION_ID
	return {
		"key": location_id,
		"name": location_id,
		"adm1": "",
		"adm2": "",
		"lat": "0",
		"lon": "0",
		"source": "qweather",
	}


def load_weather(location_id: str | None = None) -> dict[str, Any]:
	location = selected_location(location_id)
	payload, cache_hit = load_qweather_payload(location)
	location = payload.get("_location", location)
	now = payload["weather_now"]["now"]
	hourly = payload["weather_hourly"]
	daily = payload["weather_daily"]
	life_index = build_qweather_life_index(payload["indices_1d"])
	air_index = qweather_air_index(payload.get("air_current", {}))
	pollutants = qweather_pollutants(payload.get("air_current", {}))
	hourly_items = build_qweather_hourly(hourly)
	minutely = build_minutely(payload.get("minutely", {}))
	alerts = build_weather_alerts(payload.get("weather_alert", {}))
	latitude = location["lat"]
	longitude = location["lon"]
	current_time = datetime.now(LOCAL_TIMEZONE)
	updated_at = current_time.isoformat(timespec="seconds")
	background_time = build_background_time(daily, current_time)
	forecast_keypoint = f"{daily['daily'][0]['textDay']}转{daily['daily'][0]['textNight']}，最高 {daily['daily'][0]['tempMax']}°C，最低 {daily['daily'][0]['tempMin']}°C。"

	return {
		"place": location["name"],
		"coordinates": f"{location['adm1']} · {location['adm2']} · {location['name']}",
		"location": {
			"id": location["key"],
			"lat": latitude,
			"lon": longitude,
		},
		"selected_location_id": location["key"],
		"updated_at": "刚刚",
		"updated_at_iso": updated_at,
		"api_enabled": bool(payload.get("api_enabled")),
		"cache_hit": cache_hit,
		"background_theme": qweather_background_theme(now.get("icon"), now.get("text", "")),
		"background_time_phase": background_time["phase"],
		"background_time": background_time,
		"forecast_keypoint": forecast_keypoint,
		"hourly_description": "未来 24 小时以降雨和阴天为主，夜间雨势更明显。",
		"now": {
			"temperature": format_number(now.get("temp"), 0),
			"icon": qweather_icon(now.get("icon"), now.get("text", "")),
			"apparent_temperature": f"{format_number(now.get('feelsLike'), 0)}°C",
			"sky": now.get("text", "暂无"),
			"humidity": qweather_percent(now.get("humidity")),
			"cloudrate": qweather_percent(now.get("cloud")),
			"visibility": f"{format_number(now.get('vis'), 0)} km",
			"dswrf": "暂无",
			"pressure": f"{format_number(now.get('pressure'), 0)} hPa",
			"wind": qweather_wind(now),
			"precipitation": f"{format_number(now.get('precip'))} mm",
			"precipitation_source": "和风天气",
			"nearest_precipitation": minutely["summary"],
			"air_quality": air_index.get("category", "暂无"),
			"details": [
				{"label": "体感", "value": f"{format_number(now.get('feelsLike'), 0)}°C", "icon": "i-thermometer"},
				{"label": "湿度", "value": qweather_percent(now.get("humidity")), "icon": "i-droplet"},
				{"label": "云量", "value": qweather_percent(now.get("cloud")), "icon": "i-cloud"},
				{"label": "风", "value": qweather_wind(now), "icon": "i-wind"},
				{"label": "降水", "value": f"{format_number(now.get('precip'))} mm", "icon": "i-rain"},
				{"label": "露点", "value": f"{format_number(now.get('dew'), 0)}°C", "icon": "i-droplet"},
				{"label": "能见度", "value": f"{format_number(now.get('vis'), 0)} km", "icon": "i-eye"},
				{"label": "气压", "value": f"{format_number(now.get('pressure'), 0)} hPa", "icon": "i-gauge"},
			],
		},
		"current_metrics": [
			{"label": "AQI", "value": air_index.get("aqiDisplay", air_index.get("aqi", "暂无")), "icon": "i-leaf"},
			{"label": "体感", "value": f"{format_number(now.get('feelsLike'), 0)}°C", "icon": "i-thermometer"},
			{"label": "湿度", "value": qweather_percent(now.get("humidity")), "icon": "i-droplet"},
			{"label": "风", "value": qweather_wind(now), "icon": "i-wind"},
			{"label": "降水", "value": f"{format_number(now.get('precip'))} mm", "icon": "i-rain"},
			{"label": "能见度", "value": f"{format_number(now.get('vis'), 0)} km", "icon": "i-eye"},
		],
		"air_quality": {
			"description": air_index.get("category", "暂无"),
			"aqi": air_index.get("aqiDisplay", air_index.get("aqi", "暂无")),
			"standard": air_index.get("name", "暂无"),
			"level": air_index.get("level", "暂无"),
			"effect": air_index.get("health", {}).get("effect", ""),
			"advice": air_index.get("health", {}).get("advice", {}).get("generalPopulation", ""),
			"pollutants": pollutants,
		},
		"minutely": minutely,
		"alerts": alerts,
		"life_index": life_index,
		"hourly": hourly_items,
		"hourly_chart": build_hourly_chart(hourly_items),
		"daily": build_qweather_daily(daily, life_index),
	}
