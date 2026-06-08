import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from cryptography.hazmat.primitives import serialization

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)

DATA_FILE = Path(__file__).resolve().parent / "data" / "qweather_sample.json"
ENV_FILE = Path(__file__).resolve().parent / ".env"
DEFAULT_LOCATION_ID = "101240704"
QWEATHER_CACHE_SECONDS = 60
QWEATHER_TIMEOUT_SECONDS = 10
QWEATHER_JWT_TTL_SECONDS = 900
QWEATHER_LANGUAGE = "zh"
QWEATHER_MAX_FETCH_ATTEMPTS = 3
HOURLY_PREVIEW_COUNT = 24

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

QWEATHER_ICON: dict[str, str] = {
	"100": "i-sun",
	"101": "i-mostly-cloudy",
	"102": "i-partly-cloudy",
	"103": "i-cloud-sun",
	"104": "i-cloud",
	"150": "i-moon",
	"151": "i-mostly-cloudy-night",
	"152": "i-partly-cloudy-night",
	"153": "i-cloud-moon",
	"300": "i-shower",
	"301": "i-shower",
	"302": "i-thunderstorm",
	"303": "i-thunderstorm",
	"304": "i-hail",
	"305": "i-light-rain",
	"306": "i-rain",
	"307": "i-heavy-rain",
	"308": "i-heavy-rain",
	"309": "i-light-rain",
	"310": "i-heavy-rain",
	"311": "i-heavy-rain",
	"312": "i-heavy-rain",
	"313": "i-hail",
	"314": "i-rain",
	"315": "i-rain",
	"316": "i-heavy-rain",
	"317": "i-heavy-rain",
	"318": "i-heavy-rain",
	"350": "i-shower",
	"351": "i-shower",
	"399": "i-rain",
	"400": "i-snow",
	"401": "i-snow",
	"402": "i-heavy-snow",
	"403": "i-heavy-snow",
	"404": "i-sleet",
	"405": "i-sleet",
	"406": "i-sleet",
	"407": "i-snow",
	"408": "i-snow",
	"409": "i-snow",
	"410": "i-heavy-snow",
	"456": "i-sleet",
	"457": "i-snow",
	"499": "i-snow",
	"500": "i-fog",
	"501": "i-fog",
	"502": "i-haze",
	"503": "i-dust",
	"504": "i-dust",
	"507": "i-dust",
	"508": "i-dust",
	"509": "i-fog",
	"510": "i-fog",
	"511": "i-haze",
	"512": "i-haze",
	"513": "i-haze",
	"514": "i-fog",
	"515": "i-fog",
	"900": "i-hot",
	"901": "i-cold",
}

QWEATHER_LIFE_TYPES = {
	"1": "运动",
	"2": "洗车",
	"3": "穿衣",
	"5": "紫外线",
	"6": "旅游",
	"8": "舒适度",
	"9": "感冒",
	"10": "空气扩散",
}

QWEATHER_HOME_LIFE_TYPES = ("1", "2", "3", "5", "6", "8", "9", "10")
QWEATHER_HOME_POLLUTANTS = ("pm2p5", "pm10", "o3", "no2", "so2", "co")
QWEATHER_POLLUTANT_LABELS = {
	"pm2p5": "PM2.5",
	"pm10": "PM10",
	"o3": "O3",
	"no2": "NO2",
	"so2": "SO2",
	"co": "CO",
}

QWEATHER_API_NOTES = {
	"auth": "JWT Ed25519; private key is intentionally not stored in this repository.",
	"required_env": [
		"QWEATHER_API_HOST",
		"QWEATHER_KEY_ID",
		"QWEATHER_PROJECT_ID",
		"QWEATHER_PRIVATE_KEY",
	],
	"jwt_mapping": {
		"QWEATHER_KEY_ID": "JWT header kid",
		"QWEATHER_PROJECT_ID": "JWT payload sub",
		"QWEATHER_PRIVATE_KEY": "Ed25519 private key used to sign the JWT",
	},
	"endpoints": {
		"geo_lookup": "/geo/v2/city/lookup",
		"weather_now": "/v7/weather/now",
		"weather_hourly": "/v7/weather/24h",
		"weather_daily": "/v7/weather/7d",
		"indices": "/v7/indices/1d",
		"air_current": "/airquality/v1/current/{latitude}/{longitude}",
		"air_hourly": "/airquality/v1/hourly/{latitude}/{longitude}",
		"air_daily": "/airquality/v1/daily/{latitude}/{longitude}",
		"minutely": "/v7/minutely/5m",
		"weather_alert": "/weatheralert/v1/current/{latitude}/{longitude}",
		"astronomy_sun": "/v7/astronomy/sun",
		"astronomy_moon": "/v7/astronomy/moon",
		"solar_angle": "/v7/astronomy/solar-elevation-angle",
	},
}

QWEATHER_CACHE: dict[str, dict[str, Any]] = {}
QWEATHER_JWT_CACHE: dict[str, Any] = {"token": "", "expires_at": 0}
QWEATHER_CITY_SEARCH_CACHE: dict[str, dict[str, Any]] = {}


def read_sample() -> dict[str, Any]:
	with DATA_FILE.open(encoding="utf-8-sig") as file:
		return json.load(file)


def load_local_env(path: Path = ENV_FILE) -> None:
	if not path.exists():
		return

	for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		os.environ.setdefault(key, value)


def qweather_config() -> dict[str, str]:
	load_local_env()
	config = {
		"host": os.getenv("QWEATHER_API_HOST", "").rstrip("/"),
		"key_id": os.getenv("QWEATHER_KEY_ID", ""),
		"project_id": os.getenv("QWEATHER_PROJECT_ID", ""),
		"private_key": os.getenv("QWEATHER_PRIVATE_KEY", ""),
	}
	if "\\n" in config["private_key"]:
		config["private_key"] = config["private_key"].replace("\\n", "\n")
	return config


def qweather_is_configured(config: dict[str, str] | None = None) -> bool:
	values = config or qweather_config()
	return all(values.values())


def base64url(data: bytes) -> str:
	import base64

	return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def qweather_jwt(config: dict[str, str]) -> str:
	now = int(time.time())
	if QWEATHER_JWT_CACHE["token"] and now < QWEATHER_JWT_CACHE["expires_at"] - 60:
		return str(QWEATHER_JWT_CACHE["token"])

	header = {"alg": "EdDSA", "kid": config["key_id"]}
	payload = {
		"sub": config["project_id"],
		"iat": now - 30,
		"exp": now + QWEATHER_JWT_TTL_SECONDS,
	}
	signing_input = ".".join([
		base64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
		base64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
	]).encode("ascii")
	private_key = serialization.load_pem_private_key(config["private_key"].encode("utf-8"), password=None)
	signature = private_key.sign(signing_input)
	token = f"{signing_input.decode('ascii')}.{base64url(signature)}"
	QWEATHER_JWT_CACHE.update({"token": token, "expires_at": payload["exp"]})
	return token


def qweather_get(config: dict[str, str], path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
	query = f"?{urlencode(params or {})}" if params else ""
	url = f"{config['host']}{path}{query}"
	response = requests.get(
		url,
		headers={"Authorization": f"Bearer {qweather_jwt(config)}"},
		timeout=QWEATHER_TIMEOUT_SECONDS,
	)
	response.raise_for_status()
	data = response.json()
	if str(data.get("code", "200")) not in {"200"}:
		raise RuntimeError(f"QWeather API {path} returned code {data.get('code')}")
	return data


def normalize_qweather_location(entry: dict[str, Any], fallback: dict[str, str] | None = None) -> dict[str, str]:
	fallback = fallback or {}
	location_id = str(entry.get("id") or fallback.get("key") or DEFAULT_LOCATION_ID)
	name = str(entry.get("name") or fallback.get("name") or location_id)
	return {
		"key": location_id,
		"name": name,
		"adm1": str(entry.get("adm1") or fallback.get("adm1") or ""),
		"adm2": str(entry.get("adm2") or fallback.get("adm2") or ""),
		"country": str(entry.get("country") or fallback.get("country") or ""),
		"lat": str(entry.get("lat") or fallback.get("lat") or "0"),
		"lon": str(entry.get("lon") or fallback.get("lon") or "0"),
		"source": "qweather",
	}


def qweather_location_lookup(location_value: str) -> dict[str, Any]:
	config = qweather_config()
	if not qweather_is_configured(config):
		raise RuntimeError("QWeather API credentials are not configured")
	return qweather_get(
		config,
		"/geo/v2/city/lookup",
		{"location": location_value, "lang": QWEATHER_LANGUAGE},
	)


def search_qweather_cities(query: str) -> list[dict[str, str]]:
	query = query.strip()
	if len(query) < 2:
		return []

	now = time.time()
	cache_key = query.casefold()
	cached = QWEATHER_CITY_SEARCH_CACHE.get(cache_key)
	if cached and now - cached["loaded_at"] < QWEATHER_CACHE_SECONDS:
		return cached["cities"]

	config = qweather_config()
	if not qweather_is_configured(config):
		return []

	data = qweather_get(
		config,
		"/geo/v2/city/lookup",
		{"location": query, "lang": QWEATHER_LANGUAGE, "number": 10},
	)
	cities = [normalize_qweather_location(item) for item in data.get("location", [])]
	QWEATHER_CITY_SEARCH_CACHE[cache_key] = {"loaded_at": now, "cities": cities}
	return cities


def fetch_qweather_payload(location: dict[str, str]) -> dict[str, Any]:
	config = qweather_config()
	if not qweather_is_configured(config):
		raise RuntimeError("QWeather API credentials are not configured")

	lookup_value = location["key"] if location.get("source") == "qweather" else f"{location['lon']},{location['lat']}"
	geo_lookup = qweather_location_lookup(lookup_value)
	if not geo_lookup.get("location"):
		raise RuntimeError(f"QWeather GeoAPI could not resolve {lookup_value}")
	resolved_location = normalize_qweather_location(geo_lookup["location"][0], location)
	location_id = resolved_location["key"]
	indices_types = ",".join(QWEATHER_HOME_LIFE_TYPES)
	weather_params = {"location": location_id, "lang": QWEATHER_LANGUAGE}
	air_latitude = f"{float(resolved_location['lat']):.2f}"
	air_longitude = f"{float(resolved_location['lon']):.2f}"
	weather_coord = f"{air_longitude},{air_latitude}"
	today = datetime.now(timezone(timedelta(hours=8)))
	astronomy_date = today.strftime("%Y%m%d")
	return {
		"provider": "QWeather",
		"api_enabled": True,
		"api_notes": QWEATHER_API_NOTES,
		"_location": resolved_location,
		"fetched_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
		"browser_location": None,
		"geo_lookup": geo_lookup,
		"weather_now": qweather_get(config, "/v7/weather/now", weather_params),
		"weather_hourly": qweather_get(config, "/v7/weather/24h", weather_params),
		"weather_daily": qweather_get(config, "/v7/weather/7d", weather_params),
		"indices_1d": qweather_get(config, "/v7/indices/1d", {"type": indices_types, **weather_params}),
		"minutely": qweather_get(config, "/v7/minutely/5m", {"location": weather_coord, "lang": QWEATHER_LANGUAGE}),
		"weather_alert": qweather_get(
			config,
			f"/weatheralert/v1/current/{air_latitude}/{air_longitude}",
			{"lang": QWEATHER_LANGUAGE, "localTime": "true"},
		),
		"air_current": qweather_get(
			config,
			f"/airquality/v1/current/{air_latitude}/{air_longitude}",
			{"lang": QWEATHER_LANGUAGE},
		),
		"air_hourly": qweather_get(
			config,
			f"/airquality/v1/hourly/{air_latitude}/{air_longitude}",
			{"lang": QWEATHER_LANGUAGE, "localTime": "true"},
		),
		"air_daily": qweather_get(
			config,
			f"/airquality/v1/daily/{air_latitude}/{air_longitude}",
			{"lang": QWEATHER_LANGUAGE, "localTime": "true"},
		),
		"astronomy_sun": qweather_get(config, "/v7/astronomy/sun", {"location": location_id, "date": astronomy_date}),
		"astronomy_moon": qweather_get(config, "/v7/astronomy/moon", {"location": location_id, "date": astronomy_date, "lang": QWEATHER_LANGUAGE}),
		"solar_angle": qweather_get(
			config,
			"/v7/astronomy/solar-elevation-angle",
			{"location": weather_coord, "date": astronomy_date, "time": today.strftime("%H%M"), "tz": "0800", "alt": "0"},
		),
	}


def load_qweather_payload(location: dict[str, str]) -> tuple[dict[str, Any], bool]:
	cache_key = location["key"]
	now = time.time()
	cached = QWEATHER_CACHE.get(cache_key)
	if cached and now - cached["loaded_at"] < QWEATHER_CACHE_SECONDS:
		return cached["payload"], True

	last_error: Exception | None = None
	for _ in range(QWEATHER_MAX_FETCH_ATTEMPTS):
		try:
			payload = fetch_qweather_payload(location)
		except Exception as error:
			last_error = error
			continue
		QWEATHER_CACHE[cache_key] = {"loaded_at": time.time(), "payload": payload}
		return payload, False

	if cached:
		payload = dict(cached["payload"])
		payload["api_error"] = str(last_error)
		return payload, True

	payload = read_sample()
	payload["api_enabled"] = False
	payload["api_error"] = str(last_error) if last_error else "QWeather API request failed"
	return payload, False


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


def qweather_icon(icon: Any, text: str = "") -> str:
	icon_text = str(icon)
	if icon_text in QWEATHER_ICON:
		return QWEATHER_ICON[icon_text]

	if "冰雹" in text:
		return "i-hail"
	if "雨夹雪" in text or "冻雨" in text:
		return "i-sleet"
	if icon_text.startswith("3") or "雨" in text or "雷" in text:
		if "雷" in text:
			return "i-thunderstorm"
		if "阵雨" in text:
			return "i-shower"
		if any(keyword in text for keyword in ("大雨", "暴雨", "强降雨")):
			return "i-heavy-rain"
		if "小雨" in text or "毛毛雨" in text:
			return "i-light-rain"
		return "i-rain"
	if icon_text.startswith("4") or "雪" in text:
		if "暴雪" in text or "大雪" in text:
			return "i-heavy-snow"
		return "i-snow"
	if icon_text.startswith("5") or any(keyword in text for keyword in ("雾", "霾", "沙", "尘")):
		if "沙" in text or "尘" in text:
			return "i-dust"
		if "雾" in text:
			return "i-fog"
		return "i-haze"
	if "热" in text or "高温" in text:
		return "i-hot"
	if "冷" in text or "低温" in text:
		return "i-cold"
	if "风" in text:
		return "i-wind"
	if "少云" in text or "晴间多云" in text:
		return "i-partly-cloudy"
	if "夜" in text:
		if "多云" in text:
			return "i-mostly-cloudy-night"
		return "i-cloud-moon"
	if "多云" in text:
		return "i-mostly-cloudy"
	return "i-cloud"


def qweather_background_theme(icon: Any, text: str = "") -> str:
	icon_text = str(icon or "")
	weather_text = str(text or "")

	if icon_text.startswith("4") or "\u96ea" in weather_text:
		return "snow"
	if icon_text.startswith("3") or any(keyword in weather_text for keyword in ("\u96e8", "\u96f7")):
		return "rain"
	if icon_text.startswith("5") or any(keyword in weather_text for keyword in ("\u96fe", "\u973e", "\u6c99", "\u5c18")):
		return "haze"
	if icon_text in ("150", "151", "152", "153"):
		return "night" if icon_text == "150" else "cloud-night"
	if icon_text == "901":
		return "cold"
	if icon_text in ("100", "900") or "\u6674" in weather_text:
		return "sunny"
	if "\u98ce" in weather_text:
		return "wind"
	if icon_text in ("101", "102", "103", "104") or any(keyword in weather_text for keyword in ("\u4e91", "\u9634")):
		return "cloud"
	return "cloud"


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


def qweather_primary_pollutant(index: dict[str, Any]) -> str:
	pollutant = index.get("primaryPollutant")
	if not pollutant:
		return "无首要污染物"
	return pollutant.get("name") or pollutant.get("fullName") or "暂无"


def qweather_aqi_index(item: dict[str, Any]) -> dict[str, Any]:
	indexes = item.get("indexes", [])
	for index in indexes:
		if index.get("code") == "cn-mee":
			return index
	return indexes[0] if indexes else {}


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


def build_air_forecast(air_hourly: dict[str, Any], air_daily: dict[str, Any]) -> dict[str, Any]:
	hourly_items = []
	for item in air_hourly.get("hours", [])[:8]:
		index = qweather_aqi_index(item)
		if not index:
			continue
		hourly_items.append({
			"time": format_iso_time(item.get("forecastTime", "")),
			"aqi": index.get("aqiDisplay", index.get("aqi", "暂无")),
			"category": index.get("category", "暂无"),
			"primary": qweather_primary_pollutant(index),
		})

	daily_items = []
	for item in air_daily.get("days", [])[:3]:
		index = qweather_aqi_index(item)
		if not index:
			continue
		daily_items.append({
			"date": format_month_day(item.get("forecastStartTime", "")),
			"aqi": index.get("aqiDisplay", index.get("aqi", "暂无")),
			"category": index.get("category", "暂无"),
			"primary": qweather_primary_pollutant(index),
		})

	return {
		"hourly": hourly_items,
		"daily": daily_items,
	}


def build_astronomy(sun: dict[str, Any], moon: dict[str, Any], solar_angle: dict[str, Any]) -> dict[str, Any]:
	moon_phases = moon.get("moonPhase", [])
	current_phase = moon_phases[0] if moon_phases else {}
	return {
		"cards": [
			{"label": "日出", "value": format_iso_time(sun.get("sunrise", "")), "icon": "i-sun"},
			{"label": "日落", "value": format_iso_time(sun.get("sunset", "")), "icon": "i-moon"},
			{"label": "月出", "value": format_iso_time(moon.get("moonrise", "")), "icon": "i-moon"},
			{"label": "月落", "value": format_iso_time(moon.get("moonset", "")), "icon": "i-moon"},
			{"label": "月相", "value": current_phase.get("name", "暂无"), "icon": "i-moon"},
			{"label": "月亮照明", "value": qweather_percent(current_phase.get("illumination")), "icon": "i-moon"},
			{"label": "太阳高度", "value": qweather_metric(solar_angle.get("solarElevationAngle"), "°", 1), "icon": "i-sun"},
			{"label": "太阳方位", "value": qweather_metric(solar_angle.get("solarAzimuthAngle"), "°", 1), "icon": "i-gauge"},
		],
	}


def build_qweather_life_index(indices: dict[str, Any]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for entry in indices.get("daily", []):
		if str(entry.get("type")) not in QWEATHER_HOME_LIFE_TYPES:
			continue
		label = QWEATHER_LIFE_TYPES.get(str(entry.get("type")), entry.get("name", "生活指数"))
		items.append({
			"label": label,
			"index": entry.get("level", "暂无"),
			"desc": entry.get("category", "暂无"),
			"text": entry.get("text", ""),
		})
	return items


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
	air_index = qweather_air_index(payload["air_current"])
	pollutants = qweather_pollutants(payload["air_current"])
	hourly_items = build_qweather_hourly(hourly)
	minutely = build_minutely(payload.get("minutely", {}))
	alerts = build_weather_alerts(payload.get("weather_alert", {}))
	air_forecast = build_air_forecast(payload.get("air_hourly", {}), payload.get("air_daily", {}))
	astronomy = build_astronomy(payload.get("astronomy_sun", {}), payload.get("astronomy_moon", {}), payload.get("solar_angle", {}))
	latitude = location["lat"]
	longitude = location["lon"]
	coordinates = f"{latitude}, {longitude}"
	updated_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
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
				{"label": "空气", "value": air_index.get("category", "暂无"), "icon": "i-leaf"},
			],
		},
		"current_metrics": [
			{"label": "体感", "value": f"{format_number(now.get('feelsLike'), 0)}°C", "icon": "i-thermometer"},
			{"label": "湿度", "value": qweather_percent(now.get("humidity")), "icon": "i-droplet"},
			{"label": "风", "value": qweather_wind(now), "icon": "i-wind"},
			{"label": "降水", "value": f"{format_number(now.get('precip'))} mm", "icon": "i-rain"},
			{"label": "能见度", "value": f"{format_number(now.get('vis'), 0)} km", "icon": "i-eye"},
			{"label": "空气质量", "value": f"{air_index.get('category', '暂无')} · AQI {air_index.get('aqiDisplay', air_index.get('aqi', '暂无'))}", "icon": "i-leaf"},
		],
		"air_quality": {
			"description": air_index.get("category", "暂无"),
			"aqi_chn": air_index.get("aqiDisplay", air_index.get("aqi", "暂无")),
			"standard": air_index.get("name", "暂无"),
			"level": air_index.get("level", "暂无"),
			"effect": air_index.get("health", {}).get("effect", ""),
			"advice": air_index.get("health", {}).get("advice", {}).get("generalPopulation", ""),
			"pollutants": pollutants,
			"forecast": air_forecast,
		},
		"minutely": minutely,
		"alerts": alerts,
		"astronomy": astronomy,
		"life_index": life_index,
		"hourly": hourly_items,
		"hourly_chart": build_hourly_chart(hourly_items),
		"daily": build_qweather_daily(daily, life_index),
		"meta": [
			{"label": "数据源", "value": payload.get("provider", "暂无")},
			{"label": "API 启用", "value": "否" if not payload.get("api_enabled") else "是"},
			{"label": "缓存命中", "value": "是" if cache_hit else "否"},
			{"label": "天气接口状态", "value": payload["weather_now"].get("code", "暂无")},
			{"label": "GeoAPI 状态", "value": payload["geo_lookup"].get("code", "暂无")},
			{"label": "空气质量标准", "value": air_index.get("name", "暂无")},
			{"label": "手动城市", "value": location["name"]},
			{"label": "返回坐标", "value": coordinates},
			{"label": "时区", "value": "Asia/Shanghai"},
		],
	}


@app.route("/")
def index():
	return render_template("index.html", weather=load_weather(request.args.get("location")))


@app.get("/api/weather")
def api_weather():
	weather = load_weather(request.args.get("location"))
	return jsonify({
		"cache_hit": weather["cache_hit"],
		"updated_at": weather["updated_at_iso"],
		"api_enabled": weather["api_enabled"],
	})


@app.get("/api/cities")
def api_cities():
	return jsonify({
		"cities": search_qweather_cities(request.args.get("q", "")),
	})


if __name__ == "__main__":
	app.run(debug=True)
