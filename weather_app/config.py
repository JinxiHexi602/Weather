from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "qweather_sample.json"
ENV_FILE = PROJECT_ROOT / ".env"

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

QWEATHER_CACHE: dict[str, dict[str, Any]] = {}
QWEATHER_JWT_CACHE: dict[str, Any] = {"token": "", "expires_at": 0}
QWEATHER_CITY_SEARCH_CACHE: dict[str, dict[str, Any]] = {}
