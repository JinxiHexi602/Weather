export function readStoredCity() {
	try {
		return window.localStorage.getItem("weather:selected-location");
	} catch {
		return null;
	}
}

export function saveSelectedCity(cityKey) {
	try {
		window.localStorage.setItem("weather:selected-location", cityKey);
	} catch {
		// localStorage can be unavailable in private or restricted browsing modes.
	}
}

export function readStoredPosition() {
	try {
		const stored = window.localStorage.getItem("weather:last-position");
		return stored ? JSON.parse(stored) : null;
	} catch {
		return null;
	}
}

export function saveStoredPosition(coordinates) {
	try {
		window.localStorage.setItem("weather:last-position", JSON.stringify(coordinates));
	} catch {
		// localStorage can be unavailable in private or restricted browsing modes.
	}
}

