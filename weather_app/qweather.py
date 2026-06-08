import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from cryptography.hazmat.primitives import serialization

from .config import (
    DATA_FILE,
    ENV_FILE,
    DEFAULT_LOCATION_ID,
    QWEATHER_CACHE,
    QWEATHER_CACHE_SECONDS,
    QWEATHER_CITY_SEARCH_CACHE,
    QWEATHER_HOME_LIFE_TYPES,
    QWEATHER_JWT_CACHE,
    QWEATHER_JWT_TTL_SECONDS,
    QWEATHER_LANGUAGE,
    QWEATHER_MAX_FETCH_ATTEMPTS,
    QWEATHER_TIMEOUT_SECONDS,
)


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
		"_location": resolved_location,
		"fetched_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
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
