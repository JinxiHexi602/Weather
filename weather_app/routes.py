from flask import Flask, jsonify, render_template, request

from .qweather import search_qweather_cities
from .view_models import load_weather


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return render_template("index.html", weather=load_weather(request.args.get("location")))

    @app.get("/api/weather")
    def api_weather():
        weather = load_weather(request.args.get("location"))
        return jsonify({
            "cache_hit": weather["cache_hit"],
            "updated_at": weather["updated_at_iso"],
            "api_enabled": weather["api_enabled"],
            "background_time": weather["background_time"],
            "background_time_phase": weather["background_time_phase"],
        })

    @app.get("/api/cities")
    def api_cities():
        return jsonify({
            "cities": search_qweather_cities(request.args.get("q", "")),
        })
