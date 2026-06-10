const backgroundRefreshMs = 5 * 60 * 1000;
let backgroundTimer = 0;

function parseClockMinutes(value) {
	const parts = String(value || "").trim().split(":");
	if (parts.length < 2) {
		return null;
	}

	const hour = Number(parts[0]);
	const minute = Number(parts[1]);
	if (!Number.isInteger(hour) || !Number.isInteger(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
		return null;
	}

	return hour * 60 + minute;
}

function fallbackPhase(current) {
	if (current >= 330 && current < 480) {
		return "dawn";
	}
	if (current >= 480 && current < 1050) {
		return "day";
	}
	if (current >= 1050 && current < 1200) {
		return "dusk";
	}
	return "night";
}

function utc8Minutes(date) {
	const utc8Date = new Date(date.getTime() + 8 * 60 * 60 * 1000);
	return utc8Date.getUTCHours() * 60 + utc8Date.getUTCMinutes();
}

export function getTimePhase(now = new Date(), sunrise = document.body.dataset.sunrise, sunset = document.body.dataset.sunset) {
	const current = utc8Minutes(now);
	const sunriseMinutes = parseClockMinutes(sunrise);
	const sunsetMinutes = parseClockMinutes(sunset);
	if (sunriseMinutes === null || sunsetMinutes === null) {
		return fallbackPhase(current);
	}

	const dawnStart = Math.max(0, sunriseMinutes - 60);
	const dawnEnd = Math.min(24 * 60, sunriseMinutes + 60);
	const duskStart = Math.max(0, sunsetMinutes - 60);
	const duskEnd = Math.min(24 * 60, sunsetMinutes + 60);

	if (current >= dawnStart && current < dawnEnd) {
		return "dawn";
	}
	if (current >= duskStart && current < duskEnd) {
		return "dusk";
	}
	if (current >= dawnEnd && current < duskStart) {
		return "day";
	}
	return "night";
}

export function updateBackgroundPhase(now = new Date()) {
	document.body.dataset.timePhase = getTimePhase(now);
}

function scheduleBackgroundPhase() {
	window.clearInterval(backgroundTimer);
	backgroundTimer = window.setInterval(updateBackgroundPhase, backgroundRefreshMs);
}

export function initBackground() {
	updateBackgroundPhase();
	scheduleBackgroundPhase();
}
