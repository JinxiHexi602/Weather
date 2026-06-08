import {readStoredCity} from "./storage.js";

let locationFallbackApplied = false;

export function currentRequestedLocation() {
	const params = new URLSearchParams(window.location.search);
	return params.get("location") || "";
}

export function buildLocationUrl(locationId) {
	const params = new URLSearchParams(window.location.search);
	params.set("location", locationId);
	params.delete("q");
	return `${window.location.pathname}?${params.toString()}`;
}

export function navigateToLocation(locationId, replace = false) {
	if (!locationId) {
		return false;
	}

	const nextUrl = buildLocationUrl(locationId);
	const currentUrl = `${window.location.pathname}${window.location.search}`;
	if (nextUrl === currentUrl) {
		return false;
	}

	const method = replace ? "replace" : "assign";
	window.location[method](nextUrl);
	return true;
}

export function fallbackToStoredLocation() {
	if (locationFallbackApplied || currentRequestedLocation()) {
		return false;
	}

	locationFallbackApplied = true;
	const storedCity = readStoredCity();
	if (!storedCity) {
		return false;
	}

	return navigateToLocation(storedCity, true);
}
