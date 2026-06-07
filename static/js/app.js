const backdrop = document.querySelector("#modal-backdrop");
const modalContent = document.querySelector("#modal-content");
const closeButton = document.querySelector(".modal-close");
const locationInfo = document.querySelector("#location-info");
const updateInfo = document.querySelector("#update-info");
const updateTime = document.querySelector("#update-time");
const refreshButton = document.querySelector("#refresh-weather");
const cityPicker = document.querySelector("#city-picker");
const citySearch = document.querySelector("#city-search");
const cityLocation = document.querySelector("#city-location");
const cityResults = document.querySelector("#city-results");
let activeTrigger = null;
let closeTimer = null;
let lastUpdatedAt = parseUpdatedAt(updateTime?.dataset.updatedAt);
let refreshTimer = null;
let updateTimer = null;
let citySearchTimer = null;
let activeCityResults = [];
let locationFallbackApplied = false;

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
	if (!updateTime) {
		return;
	}

	updateTimer = window.setTimeout(renderUpdateTime, Math.max(1000, getNextUpdateDelay(lastUpdatedAt)));
}

function renderUpdateTime() {
	if (!updateTime) {
		return;
	}

	updateTime.textContent = formatRelativeTime(lastUpdatedAt);
	scheduleUpdateTime();
}

function playRefreshAnimation() {
	window.clearTimeout(refreshTimer);
	refreshButton?.classList.remove("is-refreshing");
	updateInfo?.classList.remove("is-refreshing");
	void refreshButton?.offsetWidth;
	refreshButton?.classList.add("is-refreshing");
	updateInfo?.classList.add("is-refreshing");
	refreshTimer = window.setTimeout(() => {
		refreshButton?.classList.remove("is-refreshing");
		updateInfo?.classList.remove("is-refreshing");
	}, 720);
}

function refreshWeatherTime() {
	lastUpdatedAt = new Date();
	if (updateTime) {
		updateTime.dataset.updatedAt = lastUpdatedAt.toISOString();
	}
	renderUpdateTime();
	playRefreshAnimation();
}

async function refreshWeather() {
	playRefreshAnimation();
	refreshButton?.setAttribute("aria-busy", "true");

	try {
		const params = new URLSearchParams(window.location.search);
		if (cityLocation?.value) {
			params.set("location", cityLocation.value);
			params.delete("city");
		}
		const response = await fetch(`/api/weather?${params.toString()}`, {
			headers: {"Accept": "application/json"},
		});
		if (!response.ok) {
			throw new Error(`Weather refresh failed: ${response.status}`);
		}

		const payload = await response.json();
		lastUpdatedAt = parseUpdatedAt(payload.updated_at);
		if (updateTime) {
			updateTime.dataset.updatedAt = lastUpdatedAt.toISOString();
		}
		renderUpdateTime();

		if (!payload.cache_hit && payload.api_enabled) {
			window.location.reload();
		}
	} catch {
		refreshWeatherTime();
	} finally {
		refreshButton?.removeAttribute("aria-busy");
	}
}

function readStoredCity() {
	try {
		return window.localStorage.getItem("weather:selected-location");
	} catch {
		return null;
	}
}

function saveSelectedCity(cityKey) {
	try {
		window.localStorage.setItem("weather:selected-location", cityKey);
	} catch {
		// localStorage can be unavailable in private or restricted browsing modes.
	}
}

function currentRequestedLocation() {
	const params = new URLSearchParams(window.location.search);
	return params.get("location") || params.get("city") || "";
}

function isLegacyCityKey(value) {
	return /^[a-z-]+$/.test(value);
}

function buildLocationUrl(locationId, parameterName = "location") {
	const params = new URLSearchParams(window.location.search);
	if (parameterName === "city") {
		params.set("city", locationId);
		params.delete("location");
	} else {
		params.set("location", locationId);
		params.delete("city");
	}
	params.delete("q");
	return `${window.location.pathname}?${params.toString()}`;
}

function navigateToLocation(locationId, replace = false, parameterName = "location") {
	if (!locationId) {
		return false;
	}

	const nextUrl = buildLocationUrl(locationId, parameterName);
	const currentUrl = `${window.location.pathname}${window.location.search}`;
	if (nextUrl === currentUrl) {
		return false;
	}

	const method = replace ? "replace" : "assign";
	window.location[method](nextUrl);
	return true;
}

function fallbackToStoredLocation() {
	if (locationFallbackApplied || currentRequestedLocation()) {
		return false;
	}

	locationFallbackApplied = true;
	const storedCity = readStoredCity();
	if (!storedCity) {
		return false;
	}

	return navigateToLocation(storedCity, true, isLegacyCityKey(storedCity) ? "city" : "location");
}

function cityLabel(city) {
	return [city.name, city.adm2, city.adm1, city.country].filter(Boolean).join(" · ");
}

function hideCityResults() {
	if (!cityResults || !citySearch) {
		return;
	}

	cityResults.hidden = true;
	cityResults.innerHTML = "";
	citySearch.setAttribute("aria-expanded", "false");
	activeCityResults = [];
}

function renderCityResults(cities) {
	if (!cityResults || !citySearch) {
		return;
	}

	activeCityResults = cities;
	cityResults.innerHTML = "";
	if (!cities.length) {
		hideCityResults();
		return;
	}

	cities.forEach((city) => {
		const button = document.createElement("button");
		button.className = "city-result";
		button.type = "button";
		button.role = "option";
		button.dataset.locationId = city.key;
		button.innerHTML = `<strong>${city.name}</strong><span>${cityLabel(city)}</span>`;
		button.addEventListener("click", () => selectCity(city));
		cityResults.append(button);
	});
	cityResults.hidden = false;
	citySearch.setAttribute("aria-expanded", "true");
}

async function fetchCities(query) {
	const response = await fetch(`/api/cities?q=${encodeURIComponent(query)}`, {
		headers: {"Accept": "application/json"},
	});
	if (!response.ok) {
		throw new Error(`City search failed: ${response.status}`);
	}
	const payload = await response.json();
	return payload.cities || [];
}

async function searchCities(query) {
	renderCityResults(await fetchCities(query));
}

function scheduleCitySearch() {
	window.clearTimeout(citySearchTimer);
	const query = citySearch?.value.trim() || "";
	if (query.length < 2) {
		hideCityResults();
		return;
	}

	citySearchTimer = window.setTimeout(() => {
		searchCities(query).catch(hideCityResults);
	}, 240);
}

function selectCity(city) {
	if (!cityLocation || !citySearch || !cityPicker) {
		return;
	}

	cityLocation.value = city.key;
	citySearch.value = city.name;
	saveSelectedCity(city.key);
	hideCityResults();
	if (typeof cityPicker.requestSubmit === "function") {
		cityPicker.requestSubmit();
		return;
	}
	cityPicker.submit();
}

function initCityPicker() {
	if (!cityPicker || !citySearch || !cityLocation) {
		return false;
	}

	if (currentRequestedLocation() && cityLocation.value) {
		saveSelectedCity(cityLocation.value);
	}

	citySearch.addEventListener("input", () => {
		cityLocation.value = "";
		scheduleCitySearch();
	});

	citySearch.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			hideCityResults();
			return;
		}
		if (event.key === "Enter" && activeCityResults.length) {
			event.preventDefault();
			selectCity(activeCityResults[0]);
		}
	});

	document.addEventListener("click", (event) => {
		if (!cityPicker.contains(event.target)) {
			hideCityResults();
		}
	});

	cityPicker.addEventListener("submit", (event) => {
		if (cityLocation.value) {
			saveSelectedCity(cityLocation.value);
			event.preventDefault();
			navigateToLocation(cityLocation.value);
			return;
		}
		if (activeCityResults.length) {
			event.preventDefault();
			selectCity(activeCityResults[0]);
			return;
		}
		event.preventDefault();
		scheduleCitySearch();
	});
	return false;
}

function saveLocation(position) {
	const coordinates = {
		accuracy: Math.round(position.coords.accuracy),
		latitude: Number(position.coords.latitude.toFixed(6)),
		longitude: Number(position.coords.longitude.toFixed(6)),
		updatedAt: new Date().toISOString(),
	};

	try {
		window.localStorage.setItem("weather:last-position", JSON.stringify(coordinates));
	} catch {
		// localStorage can be unavailable in private or restricted browsing modes.
	}

	if (locationInfo) {
		locationInfo.classList.remove("is-locating", "is-location-denied");
		locationInfo.classList.add("is-located");
		locationInfo.dataset.browserLatitude = String(coordinates.latitude);
		locationInfo.dataset.browserLongitude = String(coordinates.longitude);
		locationInfo.title = `已定位：${coordinates.latitude}, ${coordinates.longitude}`;
	}

	return coordinates;
}

function handleLocationError(error) {
	if (locationInfo) {
		locationInfo.classList.remove("is-locating", "is-located");
		locationInfo.classList.add("is-location-denied");
		locationInfo.title = error?.message ? `定位未启用：${error.message}` : "定位未启用";
	}
	fallbackToStoredLocation();
}

async function resolveBrowserLocation(position) {
	const coordinates = saveLocation(position);
	const query = `${coordinates.longitude},${coordinates.latitude}`;

	try {
		const cities = await fetchCities(query);
		const city = cities[0];
		if (city?.key) {
			if (cityLocation) {
				cityLocation.value = city.key;
			}
			if (citySearch && city.name) {
				citySearch.value = city.name;
			}
			saveSelectedCity(city.key);
			navigateToLocation(city.key, true);
			return;
		}
	} catch {
		if (locationInfo) {
			locationInfo.title = "已定位，城市解析失败";
		}
	}

	fallbackToStoredLocation();
}

function requestBrowserLocation() {
	if (currentRequestedLocation()) {
		return false;
	}

	if (!("geolocation" in navigator)) {
		fallbackToStoredLocation();
		return false;
	}

	locationInfo?.classList.add("is-locating");
	navigator.geolocation.getCurrentPosition(resolveBrowserLocation, handleLocationError, {
		enableHighAccuracy: true,
		maximumAge: 5 * 60 * 1000,
		timeout: 8000,
	});
	return true;
}

initCityPicker();
renderUpdateTime();
requestBrowserLocation();

function settleOpenAnimation() {
	if (!backdrop) {
		return;
	}

	backdrop.classList.remove("is-opening");
	backdrop.classList.add("is-open");
}

function openModal(templateId, trigger) {
	const template = document.querySelector(`#${templateId}`);
	if (!template || !backdrop || !modalContent) {
		return;
	}

	window.clearTimeout(closeTimer);
	activeTrigger = trigger;
	modalContent.innerHTML = "";
	modalContent.append(template.content.cloneNode(true));
	backdrop.classList.remove("is-open", "is-closing");
	backdrop.classList.add("is-opening");
	backdrop.hidden = false;
	document.body.classList.add("modal-open");
	requestAnimationFrame(settleOpenAnimation);
	closeButton?.focus();
}

function closeModal() {
	if (!backdrop || !modalContent) {
		return;
	}

	if (backdrop.hidden || backdrop.classList.contains("is-closing")) {
		return;
	}

	backdrop.classList.remove("is-opening", "is-open");
	backdrop.classList.add("is-closing");
	document.body.classList.remove("modal-open");
	closeTimer = window.setTimeout(() => {
		backdrop.hidden = true;
		backdrop.classList.remove("is-closing");
		modalContent.innerHTML = "";
		activeTrigger?.focus();
		activeTrigger = null;
	}, 180);
}

document.querySelectorAll("[data-modal-target]").forEach((trigger) => {
	trigger.addEventListener("click", () => openModal(trigger.dataset.modalTarget, trigger));
	trigger.addEventListener("keydown", (event) => {
		if (event.key === "Enter" || event.key === " ") {
			event.preventDefault();
			openModal(trigger.dataset.modalTarget, trigger);
		}
	});
});

closeButton?.addEventListener("click", closeModal);
refreshButton?.addEventListener("click", refreshWeather);
backdrop?.addEventListener("click", (event) => {
	if (event.target === backdrop) {
		closeModal();
	}
});

document.addEventListener("keydown", (event) => {
	if (event.key === "Escape" && backdrop && !backdrop.hidden) {
		closeModal();
	}
});
