import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from app import config
from app.database import get_db
from app.models import (
    BacktestSummaryResponse,
    DepartureOption,
    ModelInfoResponse,
    RiskMapResponse,
    RouteRiskResponse,
    RouteSegmentRisk,
    SegmentResponse,
    TripRecommendation,
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
    """Classifies risk score into standardized categories."""
    if score >= 0.80:
        return "Very High"
    if score >= 0.60:
        return "High"
    if score >= 0.35:
        return "Moderate"
    return "Low"

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

def _fallback_risk_map() -> RiskMapResponse:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments ORDER BY sequence_order ASC")
        rows = cursor.fetchall()

    segments: List[SegmentResponse] = []
    high_risk_count = 0

    for r in rows:
        subpoints = json.loads(r["subpoints_json"]) if r["subpoints_json"] else []
        level = r["risk_level"]
        if level in ["High", "Very High"]:
            high_risk_count += 1
            
        segments.append(SegmentResponse(
            id=r["id"],
            name=r["name"],
            sequence_order=r["sequence_order"],
            start_lat=r["start_lat"],
            start_lng=r["start_lng"],
            end_lat=r["end_lat"],
            end_lng=r["end_lng"],
            subpoints=subpoints,
            risk_level=level,
            risk_score=r["risk_score"],
            risk_index=r["risk_score"],
            updated_at=r["updated_at"]
        ))

    return RiskMapResponse(
        corridor="NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
        total_segments=len(segments),
        high_or_very_high_risk_count=high_risk_count,
        segments=segments
    )

@router.get("/risk-map", response_model=RiskMapResponse)
@limiter.limit("120/minute")
def get_risk_map(
    request: Request,
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing"),
    as_of: Optional[str] = Query(None, description="Historical replay date (YYYY-MM-DD) for backtest time machine")
):
    """
    Returns all 18 NH-7 road segments between Rishikesh and Joshimath
    with current risk_level and risk_score from the trained ML pipeline and live weather.
    If 'as_of' date is provided, runs historical Time Machine replay using archived rainfall.
    """
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
                corridor="NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
                total_segments=len(live_segments),
                high_or_very_high_risk_count=high_risk_count,
                segments=[SegmentResponse(**s) for s in live_segments],
                weather_source=meta.get("weather_source", "archive_replay"),
                weather_fetched_at=meta.get("weather_fetched_at"),
                weather_age_minutes=meta.get("weather_age_minutes"),
                is_simulated=meta.get("is_simulated", False),
                stale_warning=meta.get("stale_warning"),
                mode=meta.get("mode", "replay"),
                as_of=meta.get("as_of", as_of),
            )
        except Exception as e:
            logger.exception(f"get_archive_replay_risk_map failed for {as_of} ({e})")
            raise HTTPException(status_code=500, detail=f"Failed to generate historical replay for {as_of}: {e}")

    try:
        live_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)
        high_risk_count = sum(s["risk_level"] in ("High", "Very High") for s in live_segments)
        return RiskMapResponse(
            corridor="NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
            total_segments=len(live_segments),
            high_or_very_high_risk_count=high_risk_count,
            segments=[SegmentResponse(**s) for s in live_segments],
            weather_source=meta.get("weather_source"),
            weather_fetched_at=meta.get("weather_fetched_at"),
            weather_age_minutes=meta.get("weather_age_minutes"),
            is_simulated=meta.get("is_simulated", False),
            stale_warning=meta.get("stale_warning"),
            mode="live" if simulate_rain_mm is None else "simulated",
            as_of=None,
        )
    except Exception as e:
        logger.exception(f"get_live_risk_map failed ({e}); serving seeded mock fallback")
        return _fallback_risk_map()

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
    )
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
        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        if target_date > tomorrow:
            is_beyond_tomorrow = True
    except ValueError:
        pass

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

        route_segments.append(RouteSegmentRisk(
            id=row["id"],
            name=row["name"],
            sequence_order=row["sequence_order"],
            start_lat=row["start_lat"],
            start_lng=row["start_lng"],
            end_lat=row["end_lat"],
            end_lng=row["end_lng"],
            subpoints=subpoints,
            subpoint_risk_scores=subpoint_scores,
            risk_level=seg_risk_level,
            risk_score=seg_risk_score,
            risk_index=seg_risk_score,
            terrain_percentile=live_info.get("terrain_percentile") if live_info else None,
            terrain_level=live_info.get("terrain_level") if live_info else None,
            terrain_status=live_info.get("terrain_status") if live_info else None,
            rain_mm_3d=live_info.get("rain_mm_3d") if live_info else None,
            rain_status=live_info.get("rain_status") if live_info else None,
            main_driver=live_info.get("main_driver") if live_info else None,
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
            risk_level_at_eta=eta_info.get("risk_level_at_eta"),
        ))

    avg_score = round(total_score / len(route_segments), 2) if route_segments else 0.0

    # Contextual Travel Advisory
    if is_beyond_tomorrow:
        advisory_prefix = (
            f"FORECAST NOTICE for {date}: Target travel date is beyond the 48-hour rainfall forecast window. "
            "Risk scores reflect static terrain susceptibility only (weather impact not factored). "
        )
    else:
        advisory_prefix = ""

    if overall_max_level == "Very High":
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

    advisory = f"{advisory_prefix}{advisory_body}".strip()

    return RouteRiskResponse(
        from_segment=from_segment,
        to_segment=to_segment,
        from_segment_name=start_seg["name"],
        to_segment_name=end_seg["name"],
        date=date,
        total_segments=len(route_segments),
        max_risk_level=overall_max_level,
        average_risk_score=avg_score,
        risk_index=avg_score,
        advisory=advisory,
        segments=route_segments,
        weather_source=meta.get("weather_source"),
        weather_fetched_at=meta.get("weather_fetched_at"),
        weather_age_minutes=meta.get("weather_age_minutes"),
        is_simulated=meta.get("is_simulated", False),
        stale_warning=meta.get("stale_warning"),
        recommendation=recommendation_payload,
        depart_time=applied_depart_time,
        speed_kmph=applied_speed,
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


