export async function fetchCities(query) {
	const response = await fetch(`/api/cities?q=${encodeURIComponent(query)}`, {
		headers: {"Accept": "application/json"},
	});
	if (!response.ok) {
		throw new Error(`City search failed: ${response.status}`);
	}
	const payload = await response.json();
	return payload.cities || [];
}

export async function fetchWeatherRefresh(params) {
	const response = await fetch(`/api/weather?${params.toString()}`, {
		headers: {"Accept": "application/json"},
	});
	if (!response.ok) {
		throw new Error(`Weather refresh failed: ${response.status}`);
	}
	return response.json();
}

