# [DORMANT] maps

**沉寂时间**: 2026-11-22T02:34:58.590387+00:00
**原始分类**: productivity
**描述**: Geocode, POIs, routes, timezones via OpenStreetMap/OSRM.
**触发阈值**: 60天未触碰

---

## 技能要点

# Maps Skill

Location intelligence using free, open data sources. 8 commands, 44 POI
categories, zero dependencies (Python stdlib only), no API key required.

Data sources: OpenStreetMap/Nominatim, Overpass API, OSRM, TimeAPI.io.

This skill supersedes the old `find-nearby` skill — all of find-nearby's
functionality is covered by the `nearby` command below, with the same
`--near "<place>"` shortcut and multi-category support.

## When to Use

- User sends a Telegram location pin (latitude/longitude in the message) → `nearby`
- User wants coordinates for a place name → `search`
- User has coordinates and wants the address → `reverse`
- User asks for nearby restaurants, hospitals, pharmacies, hotels, etc. → `nearby`
- User wants driving/walking/cycling distance or travel time → `distance`
- User wants turn-by-turn directions between two places → `directions`
- User wants timezone information for a location → `timezone`
- User wants to search for POIs within a geographic area → `area` + `bbox`

## Prerequisites

Python 3.8+ (stdlib only — no pip installs needed).

Script path: `~/.hermes/skills/maps/scripts/maps_client.py`

## Commands

```bash
MAPS=~/.hermes/skills/maps/scripts/maps_client.py
```

### search — Geocode a place name

```bash
python $MAPS search "Eiffel Tower"
python $MAPS search "1600 Pennsylvania Ave, Washington DC"
```

Returns: lat, lon, display name, type, bounding box, importance score.

### reverse — Coordinates to address

```bash
python $MAPS reverse 48.8584 2.2945
```

Returns: full address breakdown (street, city, state, country, postcode).

### nearby — Find places by category

```bash
# By coordinates (from a Telegram location pin, for example)
python $MAPS nearby 48.8584 2.2945 restaurant --limit 10
python $MAPS nearby 40.7128 -74.0060 hospital --radius 2000

# By address / city / zip / landmark — --near auto-geocodes
python $MAPS nearby --near "Times Square, New York" --category cafe
python $MAPS nearby --near "90210" --category pharmacy


... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("maps")` 即可自动唤醒。
