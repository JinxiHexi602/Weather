import {fetchCities} from "./api.js";
import {elements} from "./dom.js";
import {currentRequestedLocation, navigateToLocation} from "./navigation.js";
import {saveSelectedCity} from "./storage.js";

let citySearchTimer = null;
let cityPickerTimer = null;
let activeCityResults = [];

function cityLabel(city) {
	return [city.name, city.adm2, city.adm1, city.country].filter(Boolean).join(" · ");
}

export function hideCityResults() {
	if (!elements.cityResults || !elements.citySearch) {
		return;
	}

	elements.cityResults.hidden = true;
	elements.cityResults.innerHTML = "";
	elements.citySearch.setAttribute("aria-expanded", "false");
	activeCityResults = [];
}

function openCityPicker() {
	if (!elements.cityPicker || !elements.citySearch || !elements.cityDisplay) {
		return;
	}

	window.clearTimeout(cityPickerTimer);
	elements.citySearch.disabled = false;
	elements.citySearch.tabIndex = 0;
	elements.cityPicker.classList.add("is-editing");
	elements.cityDisplay.setAttribute("aria-expanded", "true");
	window.requestAnimationFrame(() => {
		elements.citySearch.focus();
		elements.citySearch.select();
	});
}

function closeCityPicker() {
	if (!elements.cityPicker || !elements.citySearch || !elements.cityDisplay) {
		return;
	}

	elements.cityPicker.classList.remove("is-editing");
	elements.cityDisplay.setAttribute("aria-expanded", "false");
	if (elements.cityDisplay.textContent && elements.citySearch.value.trim() !== elements.cityDisplay.textContent.trim()) {
		elements.citySearch.value = elements.cityDisplay.textContent.trim();
	}
	hideCityResults();
	window.clearTimeout(cityPickerTimer);
	cityPickerTimer = window.setTimeout(() => {
		if (!elements.cityPicker.classList.contains("is-editing")) {
			elements.citySearch.disabled = true;
			elements.citySearch.tabIndex = -1;
		}
	}, 220);
}

function renderCityResults(cities) {
	if (!elements.cityResults || !elements.citySearch) {
		return;
	}

	activeCityResults = cities;
	elements.cityResults.innerHTML = "";
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
		elements.cityResults.append(button);
	});
	elements.cityResults.hidden = false;
	elements.citySearch.setAttribute("aria-expanded", "true");
}

async function searchCities(query) {
	renderCityResults(await fetchCities(query));
}

function scheduleCitySearch() {
	window.clearTimeout(citySearchTimer);
	const query = elements.citySearch?.value.trim() || "";
	if (query.length < 2) {
		hideCityResults();
		return;
	}

	citySearchTimer = window.setTimeout(() => {
		searchCities(query).catch(hideCityResults);
	}, 240);
}

export function selectCity(city) {
	if (!elements.cityLocation || !elements.citySearch || !elements.cityPicker) {
		return;
	}

	elements.cityLocation.value = city.key;
	elements.citySearch.value = city.name;
	if (elements.cityDisplay) {
		elements.cityDisplay.textContent = city.name;
	}
	saveSelectedCity(city.key);
	hideCityResults();
	if (typeof elements.cityPicker.requestSubmit === "function") {
		elements.cityPicker.requestSubmit();
		return;
	}
	elements.cityPicker.submit();
}

export function initCityPicker() {
	if (!elements.cityPicker || !elements.citySearch || !elements.cityLocation || !elements.cityDisplay) {
		return false;
	}

	if (currentRequestedLocation() && elements.cityLocation.value) {
		saveSelectedCity(elements.cityLocation.value);
	}
	elements.citySearch.disabled = true;
	elements.citySearch.tabIndex = -1;

	elements.cityDisplay.addEventListener("click", openCityPicker);

	elements.citySearch.addEventListener("input", () => {
		elements.cityLocation.value = "";
		scheduleCitySearch();
	});

	elements.citySearch.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			event.preventDefault();
			closeCityPicker();
			elements.cityDisplay.focus();
			return;
		}
		if (event.key === "Tab") {
			hideCityResults();
			return;
		}
		if (event.key === "Enter" && activeCityResults.length) {
			event.preventDefault();
			selectCity(activeCityResults[0]);
		}
	});

	document.addEventListener("click", (event) => {
		if (!elements.cityPicker.contains(event.target)) {
			closeCityPicker();
		}
	});

	elements.cityPicker.addEventListener("submit", (event) => {
		if (elements.cityLocation.value) {
			saveSelectedCity(elements.cityLocation.value);
			event.preventDefault();
			navigateToLocation(elements.cityLocation.value);
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

