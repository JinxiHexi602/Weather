import {fetchCities} from "./api.js";
import {elements} from "./dom.js";
import {currentRequestedLocation, fallbackToStoredLocation, navigateToLocation} from "./navigation.js";
import {readStoredPosition, saveSelectedCity, saveStoredPosition} from "./storage.js";

function saveLocation(position) {
	const coordinates = {
		accuracy: Math.round(position.coords.accuracy),
		latitude: Number(position.coords.latitude.toFixed(6)),
		longitude: Number(position.coords.longitude.toFixed(6)),
		updatedAt: new Date().toISOString(),
	};

	saveStoredPosition(coordinates);

	if (elements.locationInfo) {
		elements.locationInfo.classList.remove("is-locating", "is-location-denied");
		elements.locationInfo.classList.add("is-located");
		elements.locationInfo.dataset.browserLatitude = String(coordinates.latitude);
		elements.locationInfo.dataset.browserLongitude = String(coordinates.longitude);
		elements.locationInfo.title = `已定位：${coordinates.latitude}, ${coordinates.longitude}`;
	}
	elements.locateButton?.removeAttribute("aria-busy");

	return coordinates;
}

function handleLocationError(error) {
	if (elements.locationInfo) {
		elements.locationInfo.classList.remove("is-locating", "is-located");
		elements.locationInfo.classList.add("is-location-denied");
		elements.locationInfo.title = error?.message ? `定位未启用：${error.message}` : "定位未启用";
	}
	elements.locateButton?.removeAttribute("aria-busy");
	fallbackToStoredLocation();
}

async function resolveBrowserLocation(position) {
	const coordinates = saveLocation(position);
	const query = `${coordinates.longitude},${coordinates.latitude}`;

	try {
		const cities = await fetchCities(query);
		const city = cities[0];
		if (city?.key) {
			if (elements.cityLocation) {
				elements.cityLocation.value = city.key;
			}
			if (elements.citySearch && city.name) {
				elements.citySearch.value = city.name;
			}
			if (elements.cityDisplay && city.name) {
				elements.cityDisplay.textContent = city.name;
			}
			saveSelectedCity(city.key);
			navigateToLocation(city.key, true);
			return;
		}
	} catch {
		if (elements.locationInfo) {
			elements.locationInfo.title = "已定位，城市解析失败";
		}
	}

	fallbackToStoredLocation();
}

function requestBrowserLocationWithOptions({force = false} = {}) {
	if (!force && currentRequestedLocation()) {
		return false;
	}

	if (!("geolocation" in navigator)) {
		fallbackToStoredLocation();
		return false;
	}

	elements.locationInfo?.classList.add("is-locating");
	elements.locationInfo?.classList.remove("is-located", "is-location-denied");
	elements.locateButton?.setAttribute("aria-busy", "true");
	navigator.geolocation.getCurrentPosition(resolveBrowserLocation, handleLocationError, {
		enableHighAccuracy: true,
		maximumAge: 5 * 60 * 1000,
		timeout: 8000,
	});
	return true;
}

function initLocationStatus() {
	if (!elements.locationInfo) {
		return;
	}

	const stored = readStoredPosition();
	if (stored?.latitude && stored?.longitude) {
		elements.locationInfo.classList.add("is-located");
		elements.locationInfo.dataset.browserLatitude = String(stored.latitude);
		elements.locationInfo.dataset.browserLongitude = String(stored.longitude);
		elements.locationInfo.title = `已定位：${stored.latitude}, ${stored.longitude}`;
		return;
	}

	elements.locationInfo.classList.add("is-location-denied");
}

export function initGeolocation() {
	initLocationStatus();
	requestBrowserLocationWithOptions();
	elements.locateButton?.addEventListener("click", () => requestBrowserLocationWithOptions({force: true}));
}

