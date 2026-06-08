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
	"101": "i-cloud-sun",
	"102": "i-cloud-sun",
	"103": "i-cloud-sun",
	"104": "i-cloud",
	"150": "i-moon",
	"151": "i-cloud-moon",
	"152": "i-cloud-moon",
	"153": "i-cloud-moon",
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
QWEATHER_HOME_POLLUTANTS = ("pm2p5", "pm10", "o3", "no2")
QWEATHER_POLLUTANT_LABELS = {
	"pm2p5": "PM2.5",
	"pm10": "PM10",
	"o3": "O3",
	"no2": "NO2",
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
		"air_current": qweather_get(
			config,
			f"/airquality/v1/current/{air_latitude}/{air_longitude}",
			{"lang": QWEATHER_LANGUAGE},
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


def qweather_icon(icon: Any, text: str = "") -> str:
	icon_text = str(icon)
	if icon_text in QWEATHER_ICON:
		return QWEATHER_ICON[icon_text]
	if icon_text.startswith("3") or "雨" in text:
		return "i-rain"
	if icon_text.startswith("4") or "雪" in text:
		return "i-snow"
	if icon_text.startswith("5") or any(keyword in text for keyword in ("雾", "霾", "沙", "尘")):
		return "i-haze"
	if "风" in text:
		return "i-wind"
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
		items.append({
			"label": QWEATHER_POLLUTANT_LABELS.get(code, pollutant.get("name", "暂无")),
			"value": format_number(concentration.get("value"), 0),
		})
	return items


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
		probability_value = numeric_value(entry.get("pop")) or 0
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
			"probability_value": max(0, min(100, round(probability_value))),
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
			"nearest_precipitation": "待接入分钟级降水",
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
			"pollutants": pollutants,
		},
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
