from typing import Any

from .config import QWEATHER_ICON


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

	if icon_text in ("302", "303", "304", "313") or any(keyword in weather_text for keyword in ("\u96f7", "\u51b0\u96f9")):
		return "storm"
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
