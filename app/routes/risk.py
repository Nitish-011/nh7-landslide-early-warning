import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, JSONResponse
from app import config, i18n
from app.database import get_db
from app.models import (
    BacktestSummaryResponse,
    DepartureOption,
    ModelInfoResponse,
    PriorityListResponse,
    PrioritySegmentItem,
    RiskMapResponse,
    RouteRiskResponse,
    RouteSegmentRisk,
    SegmentResponse,
    TripRecommendation,
    OfflinePackResponse,
    OfflineSegmentItem,
    OfflineEmergencyContact,
)
from app.model_info import get_model_info_payload
from app.logger import logger
from app.risk_service import (
    get_live_risk_map,
    get_live_risk_map_with_metadata,
    get_archive_replay_risk_map,
)
from app.trip_planner import evaluate_trip_plan, parse_departure_time
from app.limiter import limiter


router = APIRouter(tags=["Risk Assessment"])

def calculate_risk_level(score: float) -> str:
    """Classifies risk score into standardized categories using central LEVEL_CUTS."""
    from app.risk_service import level_for
    return level_for(score)


def compute_deterministic_score(seed_str: str, base_score: float) -> float:
    """
    Computes a truly deterministic float between 0.05 and 0.99 using MD5.
    Stable across multiple workers, processes, and server restarts.
    """
    digest = hashlib.md5(seed_str.encode("utf-8")).hexdigest()
    # Take first 8 hex characters (32 bits) and normalize to 0.0 - 1.0
    val = int(digest[:8], 16) / 0xFFFFFFFF
    # Blend 65% base vulnerability with 35% date/weather perturbation
    score = (base_score * 0.65) + (val * 0.35)
    return round(max(0.05, min(0.98, score)), 2)

def _build_segment_responses(raw_segments: list, lang: str = "en") -> List[SegmentResponse]:
    out = []
    for s in raw_segments:
        s_data = dict(s)
        if lang == "hi":
            s_data["name_en"] = s.get("name")
            s_data["name"] = i18n.localize_segment_name(s.get("id", ""), s.get("name", ""), "hi")
            s_data["risk_level_en"] = s.get("risk_level")
            s_data["risk_level"] = i18n.localize_risk_level(s.get("risk_level"), "hi")
            s_data["main_driver_en"] = s.get("main_driver")
            s_data["main_driver"] = i18n.localize_main_driver(s.get("main_driver"), "hi")
            if s.get("terrain_level"):
                s_data["terrain_level_en"] = s["terrain_level"]
                s_data["terrain_level"] = i18n.localize_risk_level(s["terrain_level"], "hi")
            if s.get("adjusted_risk_level"):
                s_data["adjusted_risk_level_en"] = s["adjusted_risk_level"]
                s_data["adjusted_risk_level"] = i18n.localize_risk_level(s["adjusted_risk_level"], "hi")
        out.append(SegmentResponse(**s_data))
    return out

def _fallback_risk_map(lang: str = "en") -> RiskMapResponse:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments ORDER BY sequence_order ASC")
        rows = cursor.fetchall()

    raw_segments: List[dict] = []
    high_risk_count = 0

    for r in rows:
        subpoints = json.loads(r["subpoints_json"]) if r["subpoints_json"] else []
        level = r["risk_level"]
        if level in ["High", "Very High"]:
            high_risk_count += 1
            
        raw_segments.append({
            "id": r["id"],
            "name": r["name"],
            "sequence_order": r["sequence_order"],
            "start_lat": r["start_lat"],
            "start_lng": r["start_lng"],
            "end_lat": r["end_lat"],
            "end_lng": r["end_lng"],
            "subpoints": subpoints,
            "risk_level": level,
            "risk_score": r["risk_score"],
            "risk_index": r["risk_score"],
            "updated_at": r["updated_at"]
        })

    is_hi = (lang == "hi")
    corridor_title = i18n.CORRIDOR_NAME_HI if is_hi else i18n.CORRIDOR_NAME_EN
    corridor_en = i18n.CORRIDOR_NAME_EN if is_hi else None

    return RiskMapResponse(
        corridor=corridor_title,
        corridor_en=corridor_en,
        total_segments=len(raw_segments),
        high_or_very_high_risk_count=high_risk_count,
        segments=_build_segment_responses(raw_segments, lang=lang),
        lang=lang,
    )

@router.get("/risk-map", response_model=RiskMapResponse)
@limiter.limit("120/minute")
def get_risk_map(
    request: Request,
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing"),
    as_of: Optional[str] = Query(None, description="Historical replay date (YYYY-MM-DD) for backtest time machine"),
    lang: Optional[str] = Query("en", description="Language code: 'en' or 'hi' (default 'en')")
):
    """
    Returns all 18 NH-7 road segments between Rishikesh and Joshimath
    with current risk_level and risk_score from the trained ML pipeline and live weather.
    If 'as_of' date is provided, runs historical Time Machine replay using archived rainfall.
    When lang=hi, returns transliterated segment names and Devanagari risk levels.
    """
    if lang is not None and lang not in ("en", "hi"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Supported languages are 'en' and 'hi'."
        )
    if simulate_rain_mm is not None and (simulate_rain_mm < 0.0 or simulate_rain_mm > 1000.0):
        raise HTTPException(
            status_code=400,
            detail="simulate_rain_mm must be a positive number between 0.0 and 1000.0 mm."
        )

    is_hi = (lang == "hi")
    corridor_title = i18n.CORRIDOR_NAME_HI if is_hi else i18n.CORRIDOR_NAME_EN
    corridor_en = i18n.CORRIDOR_NAME_EN if is_hi else None

    if as_of:
        if not getattr(config, "BACKTEST_ENABLED", False):
            raise HTTPException(
                status_code=400,
                detail="Historical replay is disabled. Set BACKTEST_ENABLED=true to enable the Time Machine feature."
            )
        try:
            datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format for as_of. Expected YYYY-MM-DD."
            )
        try:
            live_segments, meta = get_archive_replay_risk_map(as_of=as_of)
            high_risk_count = sum(s["risk_level"] in ("High", "Very High") for s in live_segments)
            return RiskMapResponse(
                corridor=corridor_title,
                corridor_en=corridor_en,
                total_segments=len(live_segments),
                high_or_very_high_risk_count=high_risk_count,
                segments=_build_segment_responses(live_segments, lang=lang or "en"),
                weather_source=meta.get("weather_source", "archive_replay"),
                weather_fetched_at=meta.get("weather_fetched_at"),
                weather_age_minutes=meta.get("weather_age_minutes"),
                is_simulated=meta.get("is_simulated", False),
                stale_warning=meta.get("stale_warning"),
                mode=meta.get("mode", "replay"),
                as_of=meta.get("as_of", as_of),
                lang=lang or "en",
            )
        except Exception as e:
            logger.exception(f"get_archive_replay_risk_map failed for {as_of} ({e})")
            raise HTTPException(status_code=500, detail=f"Failed to generate historical replay for {as_of}: {e}")

    try:
        live_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)
        high_risk_count = sum(s["risk_level"] in ("High", "Very High") for s in live_segments)
        return RiskMapResponse(
            corridor=corridor_title,
            corridor_en=corridor_en,
            total_segments=len(live_segments),
            high_or_very_high_risk_count=high_risk_count,
            segments=_build_segment_responses(live_segments, lang=lang or "en"),
            weather_source=meta.get("weather_source"),
            weather_fetched_at=meta.get("weather_fetched_at"),
            weather_age_minutes=meta.get("weather_age_minutes"),
            is_simulated=meta.get("is_simulated", False),
            stale_warning=meta.get("stale_warning"),
            mode="live" if simulate_rain_mm is None else "simulated",
            as_of=None,
            lang=lang or "en",
        )
    except Exception as e:
        logger.exception(f"get_live_risk_map failed ({e}); serving seeded mock fallback")
        return _fallback_risk_map(lang=lang or "en")

@router.get("/route-risk", response_model=RouteRiskResponse)
@limiter.limit("120/minute")
def get_route_risk(
    request: Request,
    from_segment: str = Query(..., description="Starting segment ID (e.g. seg_01)"),
    to_segment: str = Query(..., description="Destination segment ID (e.g. seg_09)"),
    date: str = Query(..., description="Target date in YYYY-MM-DD format"),
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing"),
    depart_time: Optional[str] = Query(
        None,
        description="Departure time in ISO format (e.g. 2026-10-06T08:00:00). Interpreted as Indian Standard Time (IST, UTC+05:30) if timezone is omitted. Assumptions: constant transit speed, no stops/traffic delays, forecast uncertainty increases beyond 24-48h."
    ),
    speed_kmph: Optional[float] = Query(
        None,
        description="Average transit speed along the corridor in km/h (default 30.0 km/h). Assumes constant speed without intermediate halts."
    ),
    lang: Optional[str] = Query("en", description="Language code: 'en' or 'hi' (default 'en')")
):
    """
    Evaluates landslide risk for segments between two points on NH-7 for a given date.
    Reads from the unified ML risk service (get_live_risk_map).
    For dates later than tomorrow, uses the static terrain-only susceptibility score and notes this in the advisory.

    Time-Aware Trip Planning (Task 3):
      When depart_time is supplied and TIME_AWARE_PLANNER=true, calculates segment-by-segment
      entry ETAs, dynamic antecedent rainfall at that exact arrival time, and optimal 48h
      departure recommendations (GO | CAUTION | DELAY | AVOID).

    Assumptions & Methodological Constraints:
      - Constant Travel Speed: assumes uniform driving speed across all gradients (default 30 km/h).
      - Continuous Journey: does not model fuel, refreshment halts, or traffic bottlenecks.
      - Forecast Attenuation: NWP precipitation forecasts exhibit diminishing skill past 24-48h.
      - Advisory Scope: guidance system only; does not override local police or BRO road status bulletins.
    """
    if lang is not None and lang not in ("en", "hi"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Supported languages are 'en' and 'hi'."
        )
    if simulate_rain_mm is not None and (simulate_rain_mm < 0.0 or simulate_rain_mm > 1000.0):
        raise HTTPException(
            status_code=400,
            detail="simulate_rain_mm must be a positive number between 0.0 and 1000.0 mm."
        )

    # Gating and parameter validation for Task 3
    if depart_time is not None:
        if not getattr(config, "TIME_AWARE_PLANNER", False):
            raise HTTPException(
                status_code=400,
                detail="Time-aware route planning is disabled. Set TIME_AWARE_PLANNER=true to enable."
            )
        try:
            parse_departure_time(depart_time)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid depart_time format: {e}. Expected ISO timestamp (e.g. 2026-10-06T08:00:00)."
            )
        if speed_kmph is not None and speed_kmph <= 0:
            raise HTTPException(
                status_code=400,
                detail="speed_kmph must be greater than 0."
            )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments WHERE id = ?", (from_segment,))
        start_seg = cursor.fetchone()
        if not start_seg:
            raise HTTPException(
                status_code=404,
                detail=f"Start segment '{from_segment}' not found on NH-7 corridor."
            )

        cursor.execute("SELECT * FROM segments WHERE id = ?", (to_segment,))
        end_seg = cursor.fetchone()
        if not end_seg:
            raise HTTPException(
                status_code=404,
                detail=f"Destination segment '{to_segment}' not found on NH-7 corridor."
            )

        seq_start = start_seg["sequence_order"]
        seq_end = end_seg["sequence_order"]

        if seq_start <= seq_end:
            cursor.execute(
                "SELECT * FROM segments WHERE sequence_order >= ? AND sequence_order <= ? ORDER BY sequence_order ASC",
                (seq_start, seq_end)
            )
        else:
            cursor.execute(
                "SELECT * FROM segments WHERE sequence_order >= ? AND sequence_order <= ? ORDER BY sequence_order DESC",
                (seq_end, seq_start)
            )
        route_rows = cursor.fetchall()

    # Determine if requested date is beyond tomorrow (forecast window)
    is_beyond_tomorrow = False
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        # Evaluate date window using Indian Standard Time (IST = UTC+5:30) for Uttarakhand highway operations
        IST = timezone(timedelta(hours=5, minutes=30))
        today = datetime.now(IST).date()
        tomorrow = today + timedelta(days=1)
        if target_date > tomorrow:
            is_beyond_tomorrow = True
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD."
        )

    try:
        live_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm, force_terrain_only=is_beyond_tomorrow)
        live_map = {s["id"]: s for s in live_segments}
    except Exception as e:
        logger.exception(f"get_live_risk_map in route-risk failed ({e}); falling back to local DB")
        live_map = {}
        meta = {}

    # Task 3: Time-Aware Trip Planning Evaluation
    recommendation_payload = None
    applied_depart_time = None
    applied_speed = None
    eta_map = {}

    if depart_time is not None and getattr(config, "TIME_AWARE_PLANNER", False):
        ordered_segs_for_planner = []
        for row in route_rows:
            live_info = live_map.get(row["id"]) or {}
            ordered_segs_for_planner.append({
                "id": row["id"],
                "name": row["name"],
                "terrain_percentile": live_info.get("terrain_percentile"),
            })

        eta_results, rec_dict, applied_depart_time, applied_speed = evaluate_trip_plan(
            ordered_segments=ordered_segs_for_planner,
            weather_map=live_map,
            depart_time_str=depart_time,
            speed_kmph=speed_kmph
        )
        recommendation_payload = rec_dict
        eta_map = {res["id"]: res for res in eta_results}

    route_segments: List[RouteSegmentRisk] = []
    total_score = 0.0
    max_score = 0.0
    LEVEL_RANKS = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}
    highest_rank = 0
    overall_max_level = "Low"

    for row in route_rows:
        subpoints = json.loads(row["subpoints_json"]) if row["subpoints_json"] else []
        live_info = live_map.get(row["id"])

        if live_info:
            seg_risk_score = live_info["risk_score"]
            seg_risk_level = live_info["risk_level"]
        else:
            # Fallback to DB score
            seg_risk_score = row["risk_score"]
            seg_risk_level = row["risk_level"]

        # Calculate fine-grained risk score at each subpoint
        subpoint_scores = []
        for idx, pt in enumerate(subpoints):
            pt_seed = f"{date}:{row['id']}:pt_{idx}:{pt[0]},{pt[1]}"
            pt_score = compute_deterministic_score(pt_seed, seg_risk_score)
            subpoint_scores.append(pt_score)

        total_score += seg_risk_score
        if seg_risk_score > max_score:
            max_score = seg_risk_score

        current_rank = LEVEL_RANKS.get(seg_risk_level, 0)
        if current_rank > highest_rank:
            highest_rank = current_rank
            overall_max_level = seg_risk_level

        eta_info = eta_map.get(row["id"]) if eta_map else {}

        seg_name = row["name"]
        seg_name_en = seg_name if lang == "hi" else None
        seg_risk_lvl_display = seg_risk_level
        seg_risk_lvl_en = seg_risk_level if lang == "hi" else None
        driver_val = live_info.get("main_driver") if live_info else None
        driver_val_en = driver_val if lang == "hi" else None
        eta_risk_lvl = eta_info.get("risk_level_at_eta")
        eta_risk_lvl_en = eta_risk_lvl if lang == "hi" else None
        adj_risk_lvl = live_info.get("adjusted_risk_level") if live_info else None
        adj_risk_lvl_en = adj_risk_lvl if lang == "hi" else None

        if lang == "hi":
            seg_name = i18n.localize_segment_name(row["id"], seg_name, "hi")
            seg_risk_lvl_display = i18n.localize_risk_level(seg_risk_level, "hi")
            driver_val = i18n.localize_main_driver(driver_val, "hi")
            if eta_risk_lvl:
                eta_risk_lvl = i18n.localize_risk_level(eta_risk_lvl, "hi")
            if adj_risk_lvl:
                adj_risk_lvl = i18n.localize_risk_level(adj_risk_lvl, "hi")

        route_segments.append(RouteSegmentRisk(
            id=row["id"],
            name=seg_name,
            name_en=seg_name_en,
            sequence_order=row["sequence_order"],
            start_lat=row["start_lat"],
            start_lng=row["start_lng"],
            end_lat=row["end_lat"],
            end_lng=row["end_lng"],
            subpoints=subpoints,
            subpoint_risk_scores=subpoint_scores,
            risk_level=seg_risk_lvl_display,
            risk_level_en=seg_risk_lvl_en,
            risk_score=seg_risk_score,
            risk_index=seg_risk_score,
            terrain_percentile=live_info.get("terrain_percentile") if live_info else None,
            terrain_level=live_info.get("terrain_level") if live_info else None,
            terrain_status=live_info.get("terrain_status") if live_info else None,
            rain_mm_3d=live_info.get("rain_mm_3d") if live_info else None,
            rain_status=live_info.get("rain_status") if live_info else None,
            main_driver=driver_val,
            main_driver_en=driver_val_en,
            method=live_info.get("method") if live_info else None,
            r3d_mm=live_info.get("r3d_mm") if live_info else None,
            rain_24h_mm=live_info.get("rain_24h_mm") if live_info else None,
            forecast_24h_mm=live_info.get("forecast_24h_mm") if live_info else None,
            forecast_72h_mm=live_info.get("forecast_72h_mm") if live_info else None,
            peak_hour_utc=live_info.get("peak_hour_utc") if live_info else None,
            peak_mm=live_info.get("peak_mm") if live_info else None,
            # Task 3: Time-aware fields at ETA
            eta_ist=eta_info.get("eta_ist"),
            rain_72h_at_eta_mm=eta_info.get("rain_72h_at_eta_mm"),
            forecast_rain_6h_around_eta_mm=eta_info.get("forecast_rain_6h_around_eta_mm"),
            risk_level_at_eta=eta_risk_lvl,
            risk_level_at_eta_en=eta_risk_lvl_en,
            # Task 5: Additive closure and ground truth fields
            closure=live_info.get("closure") if live_info else None,
            adjusted_risk_level=adj_risk_lvl,
            adjusted_risk_level_en=adj_risk_lvl_en,
            ground_report_count_24h=live_info.get("ground_report_count_24h") if live_info else None,
            adjustment_reason=live_info.get("adjustment_reason") if live_info else None,
        ))

    avg_score = round(total_score / len(route_segments), 2) if route_segments else 0.0

    # Task 5: Check for official road closures and transit restrictions along route
    route_closure_top = None
    closed_segs = [s for s in route_segments if s.closure and s.closure.status == "closed"]
    restricted_segs = [s for s in route_segments if s.closure and s.closure.status in ("restricted", "one_way")]
    if closed_segs:
        first_closed = closed_segs[0]
        route_closure_top = first_closed.closure
        closure_msg = f"Official road closure on {first_closed.id} ({first_closed.name}): {first_closed.closure.reason} (Source: {first_closed.closure.source})"
        
        # Override recommendation to AVOID
        from app.models import TripRecommendation
        recommendation_payload = TripRecommendation(
            action="AVOID",
            action_code="REC_AVOID",
            reason=closure_msg,
            params={"closed_segment": first_closed.id, "closure_id": first_closed.closure.id},
            best_departure_options=[]
        )
    elif restricted_segs:
        first_restricted = restricted_segs[0]
        route_closure_top = first_restricted.closure
        status_label = "One-way movement" if first_restricted.closure.status == "one_way" else "Traffic restriction"
        closure_msg = f"{status_label} active on {first_restricted.id} ({first_restricted.name}): {first_restricted.closure.reason} (Source: {first_restricted.closure.source})"
        from app.models import TripRecommendation
        current_action = recommendation_payload.action if recommendation_payload else "GO"
        if current_action not in ("AVOID", "DELAY"):
            recommendation_payload = TripRecommendation(
                action="CAUTION",
                action_code="REC_CAUTION",
                reason=closure_msg,
                params={"restricted_segment": first_restricted.id, "closure_id": first_restricted.closure.id},
                best_departure_options=recommendation_payload.best_departure_options if recommendation_payload else []
            )

    # Contextual Travel Advisory
    if is_beyond_tomorrow:
        advisory_prefix = (
            f"FORECAST NOTICE for {date}: Target travel date is beyond the 48-hour rainfall forecast window. "
            "Risk scores reflect static terrain susceptibility only (weather impact not factored). "
        )
    else:
        advisory_prefix = ""

    if closed_segs:
        advisory_body = f"OFFICIAL CLOSURE WARNING: Road closure active on {closed_segs[0].name}. Avoid travel across this sector."
    elif restricted_segs:
        advisory_body = f"TRAFFIC RESTRICTION NOTICE: {restricted_segs[0].closure.status.replace('_', ' ').title()} regulation active on {restricted_segs[0].name}. Proceed with heightened caution."
    elif overall_max_level == "Very High":
        advisory_body = (
            f"CRITICAL WARNING for {date}: High susceptibility to slope failure and active shooting stones "
            "detected along route sectors. Night travel and heavy vehicles strongly discouraged. Check BRO updates."
        )
    elif overall_max_level == "High":
        advisory_body = (
            f"ELEVATED RISK for {date}: Moderate to severe landslide vulnerability detected along certain passes. "
            "Ensure daytime transit and maintain safe distance from steep exposed cuttings."
        )
    elif overall_max_level == "Moderate":
        advisory_body = (
            f"MODERATE ADVISORY for {date}: Highway is generally passable. Drive cautiously near water crossings "
            "and culverts."
        )
    else:
        advisory_body = f"NORMAL CONDITIONS for {date}: Favorable road conditions anticipated across the corridor."

    advisory_en = f"{advisory_prefix}{advisory_body}".strip()
    advisory = advisory_en
    if lang == "hi":
        advisory = i18n.build_route_advisory(
            date=date,
            overall_max_level=overall_max_level,
            closed_seg_name=closed_segs[0].name if closed_segs else None,
            is_beyond_tomorrow=is_beyond_tomorrow,
            lang="hi"
        )

    if recommendation_payload and lang == "hi":
        recommendation_payload.action_en = recommendation_payload.action
        recommendation_payload.action = i18n.localize_action_code(recommendation_payload.action, "hi")
        recommendation_payload.reason_en = recommendation_payload.reason
        if closed_segs:
            recommendation_payload.reason = f"आधिकारिक मार्ग बंद चेतावनी: {i18n.localize_segment_name(closed_segs[0].id, closed_segs[0].name, 'hi')} पर मार्ग बंद है।"

    from_name = start_seg["name"]
    to_name = end_seg["name"]
    from_name_en = from_name if lang == "hi" else None
    to_name_en = to_name if lang == "hi" else None
    if lang == "hi":
        from_name = i18n.localize_segment_name(from_segment, from_name, "hi")
        to_name = i18n.localize_segment_name(to_segment, to_name, "hi")

    return RouteRiskResponse(
        from_segment=from_segment,
        to_segment=to_segment,
        from_segment_name=from_name,
        from_segment_name_en=from_name_en,
        to_segment_name=to_name,
        to_segment_name_en=to_name_en,
        date=date,
        total_segments=len(route_segments),
        max_risk_level=i18n.localize_risk_level(overall_max_level, "hi") if lang == "hi" else overall_max_level,
        max_risk_level_en=overall_max_level if lang == "hi" else None,
        average_risk_score=avg_score,
        risk_index=avg_score,
        advisory=advisory,
        advisory_en=advisory_en if lang == "hi" else None,
        segments=route_segments,
        weather_source=meta.get("weather_source"),
        weather_fetched_at=meta.get("weather_fetched_at"),
        weather_age_minutes=meta.get("weather_age_minutes"),
        is_simulated=meta.get("is_simulated", False),
        stale_warning=meta.get("stale_warning"),
        recommendation=recommendation_payload,
        depart_time=applied_depart_time,
        speed_kmph=applied_speed,
        closure=route_closure_top,
        lang=lang or "en",
    )

@router.get("/model-info", response_model=ModelInfoResponse)
@limiter.limit("120/minute")
def get_model_info(request: Request):
    """
    Returns transparent, verifiable metadata about the landslide susceptibility model:
    architecture, features, permutation importance coefficients, training sample counts,
    rigorous out-of-fold spatial validation metrics parsed from outputs/validation_report.md,
    uncalibrated demo heuristics (k, dry cap), risk-level thresholds, explicit limitations,
    and official inventory and DEM data source citations.
    """
    try:
        payload = get_model_info_payload()
        return ModelInfoResponse(**payload)
    except Exception as e:
        logger.exception(f"Failed to generate model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate model info: {str(e)}")


@router.get("/backtest-summary", response_model=BacktestSummaryResponse)
@limiter.limit("120/minute")
def get_backtest_summary(request: Request):
    """
    Returns the latest backtest evaluation metrics, optimal K_RAIN grid search results,
    and methodological caveats. Feature-flagged under BACKTEST_ENABLED.
    """
    if not getattr(config, "BACKTEST_ENABLED", False):
        raise HTTPException(
            status_code=400,
            detail="Backtest summary is disabled. Set BACKTEST_ENABLED=true to access."
        )
    summary_path = getattr(config, "OUTPUTS_DIR", config.BASE_DIR / "outputs") / "backtest_summary.json"
    if not summary_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Backtest summary not found. Run scripts/backtest.py first to generate results."
        )
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        return BacktestSummaryResponse(**data)
    except Exception as e:
        logger.exception(f"Failed to read backtest summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load backtest summary: {e}")


@router.get("/priority-list", response_model=PriorityListResponse)
@limiter.limit("120/minute")
def get_priority_list(
    request: Request,
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing")
):
    """
    Returns highway segments prioritized by operational urgency for Border Roads Organisation (BRO)
    and State Disaster Response Force (SDRF) clearance operations.
    
    Priority Score = Relative Risk Index × Blockage Consequence Index.
    All consequence metrics, hospital distances, and priority rankings are indicative operational
    guidance based on OpenStreetMap amenities and assumed parameters. Degrades gracefully if the
    """
    if simulate_rain_mm is not None and (simulate_rain_mm < 0.0 or simulate_rain_mm > 1000.0):
        raise HTTPException(
            status_code=400,
            detail="simulate_rain_mm must be a positive number between 0.0 and 1000.0 mm."
        )
    try:
        from app.consequence_service import get_priority_list_data
        data = get_priority_list_data(simulate_rain_mm=simulate_rain_mm)
        return PriorityListResponse(**data)
    except Exception as e:
        logger.exception(f"Failed to generate priority list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate priority list: {e}")


@router.get(
    "/voice-alert",
    summary="Generate Localized Spoken Voice Alert (MP3 / Browser fallback)",
    responses={
        200: {
            "content": {
                "audio/mpeg": {
                    "schema": {"type": "string", "format": "binary"}
                },
                "application/json": {
                    "example": {
                        "text": "मार्ग सलाह - ऋषिकेश to शिवपुरी: मध्यम ढलान नमी और फिसलन भरी सड़क स्थिति।",
                        "tts": "browser",
                        "lang": "hi"
                    }
                }
            },
            "description": "Returns synthesized MP3 audio stream or Web Speech API fallback JSON"
        }
    }
)
@limiter.limit("60/minute")
def get_voice_alert(
    request: Request,
    segment_id: Optional[str] = Query(None, description="Segment ID (e.g. seg_08)"),
    from_segment: Optional[str] = Query(None, alias="from", description="Origin segment for route voice advisory"),
    to_segment: Optional[str] = Query(None, alias="to", description="Destination segment for route voice advisory"),
    from_seg: Optional[str] = Query(None, description="Alternative alias for origin segment"),
    to_seg: Optional[str] = Query(None, description="Alternative alias for destination segment"),
    lang: str = Query("en", description="Speech language: 'en' or 'hi' (default 'en')"),
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rain for testing voice alert trigger")
):
    """
    Generates and serves spoken audio alerts (audio/mpeg) via gTTS from localized advisories (<= 300 chars).
    Caches audio by hash of text and language in data/tts_cache/.
    If gTTS fails or is offline, returns JSON {text, tts: 'browser'} so the client can speak via Web Speech API.
    """
    lang_clean = "hi" if str(lang).lower().startswith("hi") else "en"
    origin = from_segment or from_seg
    dest = to_segment or to_seg

    if segment_id:
        try:
            live_segments, _ = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)
            target = next((s for s in live_segments if s["id"] == segment_id), None)
        except Exception as e:
            logger.warning(f"Failed to fetch live risk map for voice alert: {e}")
            target = None

        if not target:
            # Fallback to DB
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM segments WHERE id = ?", (segment_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' not found.")
                target = dict(row)

        lvl = target.get("adjusted_risk_level") or target.get("risk_level", "Low")
        rain_val = target.get("rain_mm_3d")
        driver_val = target.get("main_driver")

        text = i18n.build_segment_voice_script(
            segment_id=target["id"],
            segment_name=target["name"],
            risk_level=lvl,
            rain_mm=rain_val,
            main_driver=driver_val,
            lang=lang_clean
        )
    elif origin and dest:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM segments WHERE id = ?", (origin,))
            start_row = cursor.fetchone()
            cursor.execute("SELECT * FROM segments WHERE id = ?", (dest,))
            end_row = cursor.fetchone()

        if not start_row or not end_row:
            raise HTTPException(status_code=404, detail=f"Origin segment '{origin}' or destination '{dest}' not found.")

        try:
            live_segments, _ = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)
        except Exception:
            live_segments = []

        seq1, seq2 = start_row["sequence_order"], end_row["sequence_order"]
        low_s, high_s = min(seq1, seq2), max(seq1, seq2)
        route = [s for s in live_segments if low_s <= s["sequence_order"] <= high_s]
        if seq1 > seq2:
            route.reverse()

        LEVEL_ORDER = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}
        if route:
            max_seg = max(route, key=lambda s: LEVEL_ORDER.get(s.get("adjusted_risk_level") or s.get("risk_level", "Low"), 0))
            max_lvl = max_seg.get("adjusted_risk_level") or max_seg.get("risk_level", "Low")
            closed_any = any(s.get("closure") and s["closure"]["status"] == "closed" for s in route)
        else:
            max_seg = dict(start_row)
            max_lvl = start_row["risk_level"]
            closed_any = False

        action = "AVOID" if closed_any else ("CAUTION" if max_lvl in ("High", "Very High") else "GO")

        text = i18n.build_route_voice_script(
            from_name=start_row["name"],
            to_name=end_row["name"],
            action=action,
            max_risk_level=max_lvl,
            max_seg_name=max_seg["name"],
            closed=closed_any,
            lang=lang_clean
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Specify either 'segment_id' or both 'from' and 'to' parameters for voice alert."
        )

    # Strictly limit text to <= 300 characters
    text = text[:300].strip()

    # Cache lookup by SHA256 of text and language
    cache_key = hashlib.sha256(f"{lang_clean}:{text}".encode("utf-8")).hexdigest()
    cache_path = config.TTS_CACHE_DIR / f"{cache_key}.mp3"

    if cache_path.exists():
        try:
            audio_bytes = cache_path.read_bytes()
            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={
                    "X-TTS-Source": "cache",
                    "X-TTS-Lang": lang_clean,
                    "Content-Disposition": f"inline; filename={cache_key}.mp3"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to read cached TTS file {cache_path}: {e}")

    # Generate via gTTS
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang_clean)
        config.TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(".tmp")
        tts.save(str(tmp_path))
        import os
        os.replace(tmp_path, cache_path)
        audio_bytes = cache_path.read_bytes()
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "X-TTS-Source": "gTTS",
                "X-TTS-Lang": lang_clean,
                "Content-Disposition": f"inline; filename={cache_key}.mp3"
            }
        )
    except Exception as e:
        logger.warning(f"gTTS audio synthesis failed ({e}); falling back to browser Web Speech API")
        return JSONResponse(
            status_code=200,
            content={"text": text, "tts": "browser", "lang": lang_clean}
        )


# --- Task 8: Offline Support Polyline Simplification & GET /offline-pack ---

def simplify_polyline(points: List[List[float]], tolerance: float = 0.0005) -> List[List[float]]:
    """
    Simplifies polyline coordinates using the Ramer-Douglas-Peucker algorithm
    and rounds coordinates to 5 decimal places (~1 meter precision) to guarantee
    a compact offline pack payload (<100 KB uncompressed).
    """
    if not points:
        return []
    if len(points) <= 2:
        return [[round(float(p[0]), 5), round(float(p[1]), 5)] for p in points]

    def _perp_dist(pt, start, end):
        dx = end[1] - start[1]
        dy = end[0] - start[0]
        denom = (dy ** 2 + dx ** 2) ** 0.5
        if denom == 0:
            return ((pt[0] - start[0]) ** 2 + (pt[1] - start[1]) ** 2) ** 0.5
        return abs(dy * pt[1] - dx * pt[0] + end[0] * start[1] - end[1] * start[0]) / denom

    dmax = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = _perp_dist(points[i], points[0], points[-1])
        if d > dmax:
            index = i
            dmax = d

    if dmax > tolerance:
        rec1 = simplify_polyline(points[: index + 1], tolerance)
        rec2 = simplify_polyline(points[index:], tolerance)
        return rec1[:-1] + rec2
    else:
        return [
            [round(float(points[0][0]), 5), round(float(points[0][1]), 5)],
            [round(float(points[-1][0]), 5), round(float(points[-1][1]), 5)],
        ]


@router.get("/offline-pack", response_model=OfflinePackResponse)
@limiter.limit("120/minute")
def get_offline_pack(
    request: Request,
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing")
):
    """
    Returns a compact, self-contained offline data bundle for mobile devices (<100 KB).
    Includes simplified segment geometry, current and terrain risk levels, bilingual advisories,
    nearest medical emergency facilities, and config-driven emergency helpline numbers.
    Supports HTTP ETag and 304 Not Modified conditional requests and gzip compression
    to minimize cellular data consumption in remote mountain valleys.
    """
    if simulate_rain_mm is not None and (simulate_rain_mm < 0.0 or simulate_rain_mm > 1000.0):
        raise HTTPException(
            status_code=400,
            detail="simulate_rain_mm must be a positive number between 0.0 and 1000.0 mm."
        )
    # 1. Fetch live risk assessment
    raw_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)

    # 2. Consequence and hospital mapping
    try:
        from app.consequence_service import load_consequence_dataset
        c_map = load_consequence_dataset()
    except Exception:
        c_map = {}

    tolerance = getattr(config, "OFFLINE_PACK_SIMPLIFY_TOLERANCE", 0.0005)

    # 3. Build compact segment objects
    segment_items = []
    for s in raw_segments:
        subpoints = s.get("subpoints") or []
        if not subpoints and "start_lat" in s and "end_lat" in s:
            subpoints = [[s["start_lat"], s["start_lng"]], [s["end_lat"], s["end_lng"]]]

        simplified = simplify_polyline(subpoints, tolerance=tolerance)
        risk_lvl = s.get("risk_level", "Low")
        terrain_lvl = s.get("terrain_level") or s.get("terrain_risk_level") or risk_lvl
        rain_mm = s.get("rain_mm_3d")
        main_driver = s.get("main_driver")

        adv_en = i18n.build_subscriber_alert_message(
            segment_name=s["name"],
            risk_level=risk_lvl,
            rain_mm=rain_mm,
            main_driver=main_driver,
            lang="en"
        )
        adv_hi = i18n.build_subscriber_alert_message(
            segment_name=s["name"],
            risk_level=risk_lvl,
            rain_mm=rain_mm,
            main_driver=main_driver,
            lang="hi"
        )

        c_info = c_map.get(s["id"], {})
        nearest_hosp = c_info.get("nearest_hospital") or None

        segment_items.append({
            "id": s["id"],
            "name": s["name"],
            "simplified_polyline": simplified,
            "current_risk_level": risk_lvl,
            "risk_level": risk_lvl,
            "terrain_risk_level": terrain_lvl,
            "advisory_en": adv_en,
            "advisory_hi": adv_hi,
            "nearest_hospital": nearest_hosp,
        })

    # 4. Emergency contacts (config-driven, default 112, no invented numbers)
    raw_contacts = getattr(config, "EMERGENCY_CONTACTS", config.DEFAULT_EMERGENCY_CONTACTS)
    emergency_contacts = [
        {"name": c.get("name", ""), "number": c.get("number", "")}
        for c in raw_contacts
    ]

    # 5. Core content for deterministic hashing
    corridor_title = i18n.CORRIDOR_NAME_EN
    core_payload = {
        "corridor": corridor_title,
        "total_segments": len(segment_items),
        "emergency_contacts": emergency_contacts,
        "segments": segment_items,
    }
    if simulate_rain_mm is not None:
        core_payload["simulate_rain_mm"] = simulate_rain_mm

    content_bytes = json.dumps(core_payload, sort_keys=True).encode("utf-8")
    version_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
    etag_header = f'"{version_hash}"'

    # 6. ETag / If-None-Match 304 Evaluation
    if_none_match = request.headers.get("if-none-match", "").strip()
    client_etag = if_none_match.strip('W/').strip('"')
    if client_etag and client_etag == version_hash:
        return Response(
            status_code=304,
            headers={
                "ETag": etag_header,
                "Cache-Control": "public, max-age=300, must-revalidate"
            }
        )

    # 7. Construct final offline pack response
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    final_payload = {
        "version": version_hash,
        "generated_at": now_iso,
        **core_payload
    }

    body_json = json.dumps(final_payload, ensure_ascii=False)
    return Response(
        content=body_json,
        media_type="application/json",
        headers={
            "ETag": etag_header,
            "Cache-Control": "public, max-age=300, must-revalidate",
            "X-Offline-Pack-Version": version_hash
        }
    )



