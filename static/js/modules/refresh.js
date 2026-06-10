import {elements} from "./dom.js";
import {fetchWeatherRefresh} from "./api.js";
import {updateBackgroundPhase} from "./background.js";

let lastUpdatedAt = parseUpdatedAt(elements.updateTime?.dataset.updatedAt);
let refreshTimer = null;
let updateTimer = null;

function parseUpdatedAt(value) {
	if (!value) {
		return new Date();
	}

	const parsed = new Date(value);
	if (Number.isNaN(parsed.getTime())) {
		return new Date();
	}

	return parsed;
}

function formatRelativeTime(date) {
	const elapsedSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));

	if (elapsedSeconds < 5) {
		return "刚刚";
	}

	if (elapsedSeconds < 15) {
		return "5秒前";
	}

	if (elapsedSeconds < 30) {
		return "15秒前";
	}

	if (elapsedSeconds < 60) {
		return "30秒前";
	}

	const elapsedMinutes = Math.floor(elapsedSeconds / 60);
	if (elapsedMinutes < 60) {
		return `${elapsedMinutes}分钟前`;
	}

	const elapsedHours = Math.floor(elapsedMinutes / 60);
	if (elapsedHours < 24) {
		return `${elapsedHours}小时前`;
	}

	return `${Math.floor(elapsedHours / 24)}天前`;
}

function getNextUpdateDelay(date) {
	const elapsedSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));

	if (elapsedSeconds < 5) {
		return (5 - elapsedSeconds) * 1000;
	}

	if (elapsedSeconds < 15) {
		return (15 - elapsedSeconds) * 1000;
	}

	if (elapsedSeconds < 30) {
		return (30 - elapsedSeconds) * 1000;
	}

	if (elapsedSeconds < 60) {
		return (60 - elapsedSeconds) * 1000;
	}

	if (elapsedSeconds < 3600) {
		return (60 - (elapsedSeconds % 60)) * 1000;
	}

	if (elapsedSeconds < 86400) {
		return (3600 - (elapsedSeconds % 3600)) * 1000;
	}

	return (86400 - (elapsedSeconds % 86400)) * 1000;
}

function scheduleUpdateTime() {
	window.clearTimeout(updateTimer);
	if (!elements.updateTime) {
		return;
	}

	updateTimer = window.setTimeout(renderUpdateTime, Math.max(1000, getNextUpdateDelay(lastUpdatedAt)));
}

export function renderUpdateTime() {
	if (!elements.updateTime) {
		return;
	}

	elements.updateTime.textContent = formatRelativeTime(lastUpdatedAt);
	scheduleUpdateTime();
}

function playRefreshAnimation() {
	window.clearTimeout(refreshTimer);
	elements.refreshButton?.classList.remove("is-refreshing");
	elements.updateInfo?.classList.remove("is-refreshing");
	void elements.refreshButton?.offsetWidth;
	elements.refreshButton?.classList.add("is-refreshing");
	elements.updateInfo?.classList.add("is-refreshing");
	refreshTimer = window.setTimeout(() => {
		elements.refreshButton?.classList.remove("is-refreshing");
		elements.updateInfo?.classList.remove("is-refreshing");
	}, 720);
}

function refreshWeatherTime() {
	lastUpdatedAt = new Date();
	if (elements.updateTime) {
		elements.updateTime.dataset.updatedAt = lastUpdatedAt.toISOString();
	}
	renderUpdateTime();
	updateBackgroundPhase(lastUpdatedAt);
	playRefreshAnimation();
}

export async function refreshWeather() {
	playRefreshAnimation();
	elements.refreshButton?.setAttribute("aria-busy", "true");

	try {
		const params = new URLSearchParams(window.location.search);
		if (elements.cityLocation?.value) {
			params.set("location", elements.cityLocation.value);
		}

		const payload = await fetchWeatherRefresh(params);
		lastUpdatedAt = parseUpdatedAt(payload.updated_at);
		if (elements.updateTime) {
			elements.updateTime.dataset.updatedAt = lastUpdatedAt.toISOString();
		}
		if (payload.background_time) {
			document.body.dataset.sunrise = payload.background_time.sunrise || "";
			document.body.dataset.sunset = payload.background_time.sunset || "";
		}
		if (payload.background_time_phase) {
			document.body.dataset.timePhase = payload.background_time_phase;
		}
		renderUpdateTime();
		updateBackgroundPhase(lastUpdatedAt);

		if (!payload.cache_hit && payload.api_enabled) {
			window.location.reload();
		}
	} catch {
		refreshWeatherTime();
	} finally {
		elements.refreshButton?.removeAttribute("aria-busy");
	}
}

export function initRefresh() {
	renderUpdateTime();
	elements.refreshButton?.addEventListener("click", refreshWeather);
}
