"""
リアルタイム天気取得サービス

Open-Meteo JMA API（プライマリ）→ OpenWeatherMap（フォールバック）→ 静的データ
の3段階で天気データを取得し、投票率修正値と日本語説明を提供する。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class PrefectureWeather:
    """都道府県の天気情報"""
    prefecture_code: str
    prefecture_name: str
    temperature: float          # 摂氏
    precipitation_mm: float     # 降水量 (mm)
    snowfall_cm: float          # 降雪量 (cm)
    wind_speed_kmh: float       # 風速 (km/h)
    weather_description_ja: str # 日本語天気説明（LLMプロンプト用）
    turnout_modifier: float     # 投票率修正値 (-0.15 ~ +0.03)
    source: str                 # "open-meteo" | "openweathermap" | "static"


def _compute_turnout_modifier(
    temperature: float,
    precipitation_mm: float,
    snowfall_cm: float,
    wind_speed_kmh: float,
) -> float:
    """天気条件から投票率修正値を算出する"""
    modifier = 0.0

    # 降雪の影響（最も強い要因）
    if snowfall_cm >= 20:
        modifier -= 0.12
    elif snowfall_cm >= 10:
        modifier -= 0.08
    elif snowfall_cm >= 5:
        modifier -= 0.05
    elif snowfall_cm > 0:
        modifier -= 0.02

    # 降水の影響
    if precipitation_mm >= 50:
        modifier -= 0.08
    elif precipitation_mm >= 20:
        modifier -= 0.05
    elif precipitation_mm >= 10:
        modifier -= 0.03
    elif precipitation_mm >= 5:
        modifier -= 0.01

    # 極端な気温の影響
    if temperature <= -5:
        modifier -= 0.05
    elif temperature <= 0:
        modifier -= 0.03
    elif temperature >= 35:
        modifier -= 0.04
    elif temperature >= 30:
        modifier -= 0.02

    # 風の影響
    if wind_speed_kmh >= 50:
        modifier -= 0.03
    elif wind_speed_kmh >= 30:
        modifier -= 0.01

    # 穏やかな天候はわずかにプラス
    if (precipitation_mm < 1 and snowfall_cm < 1
            and 10 <= temperature <= 25 and wind_speed_kmh < 20):
        modifier += 0.02

    return max(-0.15, min(0.03, modifier))


def _generate_weather_description_ja(
    temperature: float,
    precipitation_mm: float,
    snowfall_cm: float,
    wind_speed_kmh: float,
) -> str:
    """天気条件から日本語の天気説明を生成する"""
    parts: list[str] = []

    if snowfall_cm >= 20:
        parts.append("大雪")
    elif snowfall_cm >= 10:
        parts.append("積雪あり")
    elif snowfall_cm > 0:
        parts.append("小雪")

    if precipitation_mm >= 50:
        parts.append("大雨")
    elif precipitation_mm >= 20:
        parts.append("雨")
    elif precipitation_mm >= 5:
        parts.append("小雨")

    if temperature <= -5:
        parts.append("強烈な寒さ")
    elif temperature <= 0:
        parts.append("厳しい冷え込み")
    elif temperature >= 35:
        parts.append("猛暑")

    if wind_speed_kmh >= 50:
        parts.append("暴風")
    elif wind_speed_kmh >= 30:
        parts.append("強風")

    if not parts:
        if temperature >= 20:
            parts.append("晴れ・穏やか")
        else:
            parts.append("曇り・穏やか")

    return f"気温{temperature:.0f}°C、{'・'.join(parts)}"


class WeatherService:
    """天気データ取得・キャッシュサービス"""

    def __init__(
        self,
        provider: str = "open-meteo",
        openweathermap_api_key: str = "",
        target_date: str | None = None,
        cache_ttl_minutes: int = 60,
    ):
        """
        Args:
            provider: "open-meteo" | "openweathermap" | "static"
            openweathermap_api_key: OpenWeatherMap APIキー（provider="openweathermap"時のみ必要）
            target_date: 対象日 (YYYY-MM-DD)。Noneの場合は当日
            cache_ttl_minutes: キャッシュ有効期間（分）
        """
        self.provider = provider
        self._owm_api_key = openweathermap_api_key
        self._target_date = target_date
        self._cache_ttl = cache_ttl_minutes * 60
        self._cache: dict[str, PrefectureWeather] = {}
        self._cache_timestamp: float = 0
        self._coordinates = self._load_coordinates()

    def _load_coordinates(self) -> list[dict]:
        """都道府県座標データを読み込む"""
        coords_path = DATA_DIR / "prefecture_coordinates.json"
        try:
            with open(coords_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"座標データなし: {coords_path}、静的モードに切り替え")
            self.provider = "static"
            return []

    def _is_cache_valid(self) -> bool:
        return (
            bool(self._cache)
            and (time.time() - self._cache_timestamp) < self._cache_ttl
        )

    async def fetch_all_prefectures(self) -> dict[str, PrefectureWeather]:
        """全都道府県の天気データを取得（キャッシュ付き）"""
        if self._is_cache_valid():
            return self._cache

        if self.provider == "static":
            self._cache = self._build_all_static()
            self._cache_timestamp = time.time()
            return self._cache

        results: dict[str, PrefectureWeather] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for pref in self._coordinates:
                weather = await self._fetch_weather_for_prefecture(client, pref)
                results[pref["code"]] = weather

        self._cache = results
        self._cache_timestamp = time.time()
        logger.info(f"天気データ取得完了: {len(results)}都道府県 (provider={self.provider})")
        return self._cache

    async def _fetch_weather_for_prefecture(
        self,
        client: httpx.AsyncClient,
        pref: dict,
    ) -> PrefectureWeather:
        """1都道府県の天気を取得（フォールバック付き）"""
        # Open-Meteo を試行
        if self.provider in ("open-meteo", "openweathermap"):
            try:
                return await self._fetch_from_open_meteo(client, pref)
            except Exception as e:
                logger.warning(f"Open-Meteo失敗 ({pref['name']}): {e}")

        # OpenWeatherMap を試行
        if self._owm_api_key:
            try:
                return await self._fetch_from_openweathermap(client, pref)
            except Exception as e:
                logger.warning(f"OpenWeatherMap失敗 ({pref['name']}): {e}")

        # 静的データにフォールバック
        logger.info(f"静的天気データ使用: {pref['name']}")
        return self._get_static_fallback(pref["code"], pref["name"])

    async def _fetch_from_open_meteo(
        self,
        client: httpx.AsyncClient,
        pref: dict,
    ) -> PrefectureWeather:
        """Open-Meteo JMA APIから天気データを取得"""
        params: dict = {
            "latitude": pref["lat"],
            "longitude": pref["lon"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_speed_10m_max",
            "timezone": "Asia/Tokyo",
        }

        if self._target_date:
            params["start_date"] = self._target_date
            params["end_date"] = self._target_date
        else:
            params["forecast_days"] = 1

        response = await client.get(
            "https://api.open-meteo.com/v1/jma",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        daily = data["daily"]
        temp_max = daily["temperature_2m_max"][0] or 0
        temp_min = daily["temperature_2m_min"][0] or 0
        temperature = (temp_max + temp_min) / 2
        precipitation_mm = daily["precipitation_sum"][0] or 0
        snowfall_cm = daily["snowfall_sum"][0] or 0
        wind_speed_kmh = daily["wind_speed_10m_max"][0] or 0

        turnout_mod = _compute_turnout_modifier(
            temperature, precipitation_mm, snowfall_cm, wind_speed_kmh,
        )
        description = _generate_weather_description_ja(
            temperature, precipitation_mm, snowfall_cm, wind_speed_kmh,
        )

        return PrefectureWeather(
            prefecture_code=pref["code"],
            prefecture_name=pref["name"],
            temperature=round(temperature, 1),
            precipitation_mm=round(precipitation_mm, 1),
            snowfall_cm=round(snowfall_cm, 1),
            wind_speed_kmh=round(wind_speed_kmh, 1),
            weather_description_ja=description,
            turnout_modifier=round(turnout_mod, 3),
            source="open-meteo",
        )

    async def _fetch_from_openweathermap(
        self,
        client: httpx.AsyncClient,
        pref: dict,
    ) -> PrefectureWeather:
        """OpenWeatherMap APIから天気データを取得"""
        params = {
            "lat": pref["lat"],
            "lon": pref["lon"],
            "appid": self._owm_api_key,
            "units": "metric",
            "lang": "ja",
        }

        response = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        temperature = data["main"]["temp"]
        wind_speed_kmh = data["wind"]["speed"] * 3.6  # m/s → km/h
        precipitation_mm = data.get("rain", {}).get("1h", 0) * 24  # 1h → 日推定
        snowfall_cm = data.get("snow", {}).get("1h", 0) * 24 / 10  # mm → cm, 日推定

        turnout_mod = _compute_turnout_modifier(
            temperature, precipitation_mm, snowfall_cm, wind_speed_kmh,
        )
        description = _generate_weather_description_ja(
            temperature, precipitation_mm, snowfall_cm, wind_speed_kmh,
        )

        return PrefectureWeather(
            prefecture_code=pref["code"],
            prefecture_name=pref["name"],
            temperature=round(temperature, 1),
            precipitation_mm=round(precipitation_mm, 1),
            snowfall_cm=round(snowfall_cm, 1),
            wind_speed_kmh=round(wind_speed_kmh, 1),
            weather_description_ja=description,
            turnout_modifier=round(turnout_mod, 3),
            source="openweathermap",
        )

    def _get_static_fallback(self, code: str, name: str = "") -> PrefectureWeather:
        """静的（ハードコード）天気データを返す — 既存ロジックとの後方互換"""
        heavy_snow_codes = {"01", "02", "05", "06", "15", "16", "17", "18"}
        moderate_snow_codes = {"03", "04", "07", "20", "31", "32"}

        if code in heavy_snow_codes:
            return PrefectureWeather(
                prefecture_code=code,
                prefecture_name=name,
                temperature=-5.0,
                precipitation_mm=0,
                snowfall_cm=25.0,
                wind_speed_kmh=20.0,
                weather_description_ja="大雪・強烈寒波",
                turnout_modifier=-0.10,
                source="static",
            )
        elif code in moderate_snow_codes:
            return PrefectureWeather(
                prefecture_code=code,
                prefecture_name=name,
                temperature=-1.0,
                precipitation_mm=0,
                snowfall_cm=10.0,
                wind_speed_kmh=15.0,
                weather_description_ja="積雪・寒波",
                turnout_modifier=-0.05,
                source="static",
            )
        else:
            return PrefectureWeather(
                prefecture_code=code,
                prefecture_name=name,
                temperature=5.0,
                precipitation_mm=2.0,
                snowfall_cm=0,
                wind_speed_kmh=10.0,
                weather_description_ja="曇り",
                turnout_modifier=0.0,
                source="static",
            )

    def _build_all_static(self) -> dict[str, PrefectureWeather]:
        """全都道府県の静的天気データを構築"""
        result: dict[str, PrefectureWeather] = {}
        if self._coordinates:
            for pref in self._coordinates:
                result[pref["code"]] = self._get_static_fallback(
                    pref["code"], pref["name"],
                )
        else:
            # 座標データなしの場合、47都道府県コードで生成
            for i in range(1, 48):
                code = str(i).zfill(2)
                result[code] = self._get_static_fallback(code)
        return result

    def get_weather_for_district(self, district_id: str) -> PrefectureWeather | None:
        """選挙区IDから天気データを取得（キャッシュから）"""
        pref_code = district_id.split("_")[0]
        return self._cache.get(pref_code)

    def get_modifier_for_district(self, district_id: str) -> float:
        """選挙区IDから投票率修正値を取得"""
        weather = self.get_weather_for_district(district_id)
        if weather is None:
            return 0.0
        return weather.turnout_modifier

    def get_description_for_district(self, district_id: str) -> str:
        """選挙区IDから天気説明を取得"""
        weather = self.get_weather_for_district(district_id)
        if weather is None:
            return "大雪・強烈寒波"
        return weather.weather_description_ja

    def export_weather_data(self) -> dict:
        """メタデータ保存用に天気データを辞書にエクスポート"""
        return {
            code: {
                "prefecture_name": w.prefecture_name,
                "temperature": w.temperature,
                "precipitation_mm": w.precipitation_mm,
                "snowfall_cm": w.snowfall_cm,
                "wind_speed_kmh": w.wind_speed_kmh,
                "weather_description_ja": w.weather_description_ja,
                "turnout_modifier": w.turnout_modifier,
                "source": w.source,
            }
            for code, w in self._cache.items()
        }
