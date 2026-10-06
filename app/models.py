from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# --- Road Closure Models (Task 5) ---

class RoadClosureCreate(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "segment_id": "seg_08",
                "status": "closed",
                "reason": "Active debris clearance and rockfall mitigation near Kaliasaur chute",
                "source": "BRO Project Shivalik",
                "starts_at": "2026-10-06T08:00:00Z",
                "ends_at": "2026-10-06T18:00:00Z",
                "created_by": "Officer-In-Charge"
            }
        }
    }
    segment_id: str = Field(..., description="ID of NH-7 segment affected (e.g. seg_08)")
    status: Literal["closed", "one_way", "restricted"] = Field(..., description="Closure status")
    reason: str = Field(..., min_length=3, description="Official cause of closure")
    source: str = Field(..., min_length=2, description="Issuing agency, e.g. BRO, Uttarakhand Police")
    starts_at: Optional[str] = Field(None, description="ISO-8601 start timestamp (defaults to current time)")
    ends_at: Optional[str] = Field(None, description="ISO-8601 end timestamp (nullable)")
    created_by: Optional[str] = Field("admin", description="Admin username or authority ID")

class RoadClosureResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "id": 1,
                "segment_id": "seg_08",
                "status": "closed",
                "reason": "Active debris clearance and rockfall mitigation near Kaliasaur chute",
                "source": "BRO Project Shivalik",
                "starts_at": "2026-10-06T08:00:00Z",
                "ends_at": "2026-10-06T18:00:00Z",
                "created_by": "Officer-In-Charge",
                "created_at": "2026-10-06T08:05:00Z"
            }
        }
    }
    id: int
    segment_id: str
    status: str
    reason: str
    source: str
    starts_at: str
    ends_at: Optional[str] = None
    created_by: str
    created_at: str

class ClosureDeleteResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "ok": True,
                "deleted_id": 1,
                "segment_id": "seg_08",
                "message": "Road closure #1 on segment seg_08 has been removed and reopened to traffic."
            }
        }
    }
    ok: bool = True
    deleted_id: int
    segment_id: str
    message: str

# --- Segments & Risk Models ---

class SegmentCoords(BaseModel):
    lat: float
    lng: float

class SegmentResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "id": "seg_01",
                "name": "Rishikesh to Shivpuri",
                "sequence_order": 1,
                "start_lat": 30.0869,
                "start_lng": 78.2676,
                "end_lat": 30.1357,
                "end_lng": 78.3892,
                "subpoints": [[30.0869, 78.2676], [30.098, 78.305], [30.115, 78.345], [30.1357, 78.3892]],
                "risk_level": "Moderate",
                "risk_score": 0.42,
                "risk_index": 0.42,
                "updated_at": "2026-10-06T07:00:00Z",
                "terrain_percentile": 0.35,
                "terrain_level": "Low",
                "terrain_status": "calibrated",
                "rain_mm_3d": 24.5,
                "rain_status": "ok",
                "main_driver": "moderate slope wetness and rainfall saturation",
                "method": "terrain model ranking + live-rainfall heuristic",
                "consequence_score": 0.38,
                "nearest_hospital": "Ayurveda Center",
                "nearest_hospital_km": 1.42,
                "nearest_town": "Simaldhandi",
                "priority_score": 0.160
            }
        }
    }
    id: str
    name: str
    sequence_order: int
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    subpoints: List[List[float]] = []
    risk_level: str
    risk_score: float = Field(..., description="Legacy relative risk score (0.0 to 1.0)")
    risk_index: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relative risk index (0.0 to 1.0; 0=lowest relative hazard, 1=highest)")
    updated_at: str
    # Additive fields from trained model & rainfall engine
    terrain_percentile: Optional[float] = None
    terrain_level: Optional[str] = None
    terrain_status: Optional[str] = None
    rain_mm_3d: Optional[float] = None
    rain_status: Optional[str] = None
    main_driver: Optional[str] = None
    method: Optional[str] = None
    # Task 1: Additive Per-Segment Weather & Forecast metrics (optional)
    r3d_mm: Optional[float] = None
    rain_24h_mm: Optional[float] = None
    forecast_24h_mm: Optional[float] = None
    forecast_72h_mm: Optional[float] = None
    peak_hour_utc: Optional[str] = None
    peak_mm: Optional[float] = None
    # Task 4: Additive Consequence & Priority fields (indicative, optional)
    consequence_score: Optional[float] = None
    nearest_hospital_km: Optional[float] = None
    nearest_town: Optional[str] = None
    priority_score: Optional[float] = None
    # Task 5: Additive Official Closure & Verified Ground Report Flywheel fields (optional)
    closure: Optional[RoadClosureResponse] = None
    adjusted_risk_level: Optional[str] = None
    ground_report_count_24h: Optional[int] = None
    adjustment_reason: Optional[str] = None
    # Task 7: Localization fields (additive, optional)
    name_en: Optional[str] = None
    risk_level_en: Optional[str] = None
    main_driver_en: Optional[str] = None

class RiskMapResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
                "total_segments": 18,
                "high_or_very_high_risk_count": 3,
                "weather_source": "live",
                "weather_fetched_at": "2026-10-06T07:00:00Z",
                "weather_age_minutes": 5.2,
                "is_simulated": False,
                "mode": "live",
                "lang": "en",
                "segments": [
                    {
                        "id": "seg_01",
                        "name": "Rishikesh to Shivpuri",
                        "sequence_order": 1,
                        "risk_level": "Moderate",
                        "risk_score": 0.42,
                        "risk_index": 0.42,
                        "rain_mm_3d": 24.5,
                        "main_driver": "moderate slope wetness and rainfall saturation"
                    }
                ]
            }
        }
    }
    corridor: str = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
    corridor_en: Optional[str] = None
    total_segments: int
    high_or_very_high_risk_count: int
    segments: List[SegmentResponse]
    # Task F2 Freshness & Simulation Metadata (additive, optional)
    weather_source: Optional[str] = None
    weather_fetched_at: Optional[str] = None
    weather_age_minutes: Optional[float] = None
    is_simulated: Optional[bool] = False
    stale_warning: Optional[str] = None
    # Task 2 Time Machine & Historical Replay Metadata (additive, optional)
    mode: Optional[str] = None
    as_of: Optional[str] = None
    lang: Optional[str] = "en"

class BacktestSummaryResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "status": "completed",
                "events_count": 14,
                "synthetic_mode": False,
                "metrics": {
                    "terrain_only": {"auc": 0.764, "auc_ci_95": [0.68, 0.84]},
                    "rain_only": {"auc": 0.712, "auc_ci_95": [0.62, 0.79]},
                    "composite": {"auc": 0.841, "auc_ci_95": [0.77, 0.91]}
                },
                "k_rain_optimal": 0.35,
                "k_rain_production": 0.30,
                "caveats": ["Retrospective archive analysis; historical events uncalibrated."]
            }
        }
    }
    status: str
    events_count: int
    synthetic_mode: bool
    metrics: Dict[str, Any]
    k_rain_optimal: float
    k_rain_production: float
    caveats: List[str]
    generated_at: Optional[str] = None
    negatives_count: Optional[int] = None
    k_rain_cv_curve: Optional[Dict[str, float]] = None

# Task 3: Time-Aware Trip Planning Models
class DepartureOption(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "depart_time": "2026-10-06T08:00:00",
                "max_risk_level": "Moderate",
                "summary": "Clear visibility window across river gorges",
                "total_risk_score": 1.84
            }
        }
    }
    depart_time: str
    max_risk_level: str
    summary: str
    total_risk_score: Optional[float] = None

class TripRecommendation(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "action": "CAUTION",
                "action_code": "REC_CAUTION",
                "reason": "Moderate risk along river gorge sector. Recommended daytime transit.",
                "best_departure_options": [
                    {
                        "depart_time": "2026-10-06T08:00:00",
                        "max_risk_level": "Moderate",
                        "summary": "Clear visibility window across river gorges"
                    }
                ]
            }
        }
    }
    action: str  # GO, CAUTION, DELAY, AVOID
    action_code: str  # REC_GO, REC_CAUTION, REC_DELAY, REC_AVOID
    reason: str
    params: Dict[str, Any] = {}
    best_departure_options: List[DepartureOption] = []
    # Task 7 Localization fields (additive, optional)
    action_en: Optional[str] = None
    reason_en: Optional[str] = None

class RouteSegmentRisk(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "id": "seg_01",
                "name": "Rishikesh to Shivpuri",
                "sequence_order": 1,
                "start_lat": 30.0869,
                "start_lng": 78.2676,
                "end_lat": 30.1357,
                "end_lng": 78.3892,
                "risk_level": "Moderate",
                "risk_score": 0.42,
                "risk_index": 0.42,
                "rain_mm_3d": 24.5,
                "eta_ist": "2026-10-06T08:15:00+05:30",
                "rain_72h_at_eta_mm": 24.5,
                "risk_level_at_eta": "Moderate"
            }
        }
    }
    id: str
    name: str
    sequence_order: int
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    subpoints: List[List[float]] = []
    subpoint_risk_scores: List[float] = Field(
        default_factory=list,
        description="Deterministic spatial visualization interpolation along polyline geometry derived from segment RF terrain & live rainfall"
    )
    visualized_subpoint_risk: Optional[List[float]] = Field(
        default=None,
        description="Alias for subpoint_risk_scores providing transparently labelled visualization gradient interpolation"
    )
    risk_level: str
    risk_score: float = Field(..., description="Legacy relative risk score (0.0 to 1.0)")
    risk_index: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relative risk index (0.0 to 1.0; 0=lowest relative hazard, 1=highest)")
    # Additive fields
    terrain_percentile: Optional[float] = None
    terrain_level: Optional[str] = None
    terrain_status: Optional[str] = None
    rain_mm_3d: Optional[float] = None
    rain_status: Optional[str] = None
    main_driver: Optional[str] = None
    method: Optional[str] = None
    # Task 1: Additive Per-Segment Weather & Forecast metrics (optional)
    r3d_mm: Optional[float] = None
    rain_24h_mm: Optional[float] = None
    forecast_24h_mm: Optional[float] = None
    forecast_72h_mm: Optional[float] = None
    peak_hour_utc: Optional[str] = None
    peak_mm: Optional[float] = None
    # Task 3: Additive Time-Aware Forecast metrics (optional)
    eta_ist: Optional[str] = None
    rain_72h_at_eta_mm: Optional[float] = None
    forecast_rain_6h_around_eta_mm: Optional[float] = None
    risk_level_at_eta: Optional[str] = None
    # Task 5: Additive Official Closure & Verified Ground Report Flywheel fields (optional)
    closure: Optional[RoadClosureResponse] = None
    adjusted_risk_level: Optional[str] = None
    ground_report_count_24h: Optional[int] = None
    adjustment_reason: Optional[str] = None
    # Task 7 Localization fields (additive, optional)
    name_en: Optional[str] = None
    risk_level_en: Optional[str] = None
    main_driver_en: Optional[str] = None
    risk_level_at_eta_en: Optional[str] = None

class RouteRiskResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "from_segment": "seg_01",
                "to_segment": "seg_05",
                "from_segment_name": "Rishikesh to Shivpuri",
                "to_segment_name": "Devprayag to Teen Dhara",
                "date": "2026-10-06",
                "total_segments": 5,
                "max_risk_level": "Moderate",
                "average_risk_score": 0.38,
                "risk_index": 0.38,
                "advisory": "MODERATE ADVISORY for 2026-10-06: Highway is generally passable. Drive cautiously near water crossings.",
                "weather_source": "live",
                "depart_time": "2026-10-06T08:00:00",
                "speed_kmph": 30.0,
                "recommendation": {
                    "action": "CAUTION",
                    "action_code": "REC_CAUTION",
                    "reason": "Moderate risk along river gorge sector. Recommended daytime departure.",
                    "best_departure_options": [
                        {"depart_time": "2026-10-06T08:00:00", "max_risk_level": "Moderate", "summary": "Clear visibility window"}
                    ]
                },
                "segments": []
            }
        }
    }
    from_segment: str
    to_segment: str
    from_segment_name: str
    to_segment_name: str
    date: str
    total_segments: int
    max_risk_level: str
    average_risk_score: float = Field(..., description="Legacy average relative risk score (0.0 to 1.0)")
    risk_index: Optional[float] = Field(None, ge=0.0, le=1.0, description="Corridor journey relative risk index (0.0 to 1.0)")
    advisory: str
    segments: List[RouteSegmentRisk]
    # Task F2 Freshness & Simulation Metadata (additive, optional)
    weather_source: Optional[str] = None
    weather_fetched_at: Optional[str] = None
    weather_age_minutes: Optional[float] = None
    is_simulated: Optional[bool] = False
    stale_warning: Optional[str] = None
    # Task 3: Additive Time-Aware Recommendation & Trip metadata (optional)
    recommendation: Optional[TripRecommendation] = None
    depart_time: Optional[str] = None
    speed_kmph: Optional[float] = None
    # Task 5: Additive Route-Level Closure (optional)
    closure: Optional[RoadClosureResponse] = None
    # Task 7 Localization fields (additive, optional)
    from_segment_name_en: Optional[str] = None
    to_segment_name_en: Optional[str] = None
    max_risk_level_en: Optional[str] = None
    advisory_en: Optional[str] = None
    lang: Optional[str] = "en"

# --- Subscription Models ---

class SubscribeRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Ramesh Negi",
                "phone_or_email": "+91-9876543210",
                "segment_id": "seg_08",
                "channel": "SMS",
                "consent": True
            }
        }
    }
    name: str = Field(..., min_length=2, description="Full name of subscriber")
    phone_or_email: str = Field(..., min_length=5, description="Mobile number with country code or email address")
    segment_id: str = Field(..., description="ID of NH-7 segment to monitor (e.g., seg_08)")
    channel: Literal["SMS", "WhatsApp", "Email"] = Field(..., description="Alert channel")
    consent: Optional[bool] = Field(default=True, description="Consent for emergency alerts and data processing")

class SubscriptionDetail(BaseModel):
    id: int
    name: str
    phone_or_email: str
    segment_id: str
    segment_name: str
    channel: str
    consent: Optional[bool] = True
    created_at: str

class SubscribeResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "subscription_id": 42,
                "status": "Active",
                "message": "Subscription created successfully for sector seg_08 (Srinagar to Sirobagarh).",
                "subscription": {
                    "id": 42,
                    "name": "Ramesh Negi",
                    "phone_or_email": "+91-9876543210",
                    "segment_id": "seg_08",
                    "segment_name": "Srinagar to Sirobagarh",
                    "channel": "SMS",
                    "consent": True,
                    "created_at": "2026-10-06T07:10:00Z"
                }
            }
        }
    }
    subscription_id: int
    status: str = "Active"
    message: str
    subscription: SubscriptionDetail

# --- Alerts Models ---

class AlertItem(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "alert_id": "ALT-NH7-SEG_08-01",
                "segment_id": "seg_08",
                "segment_name": "Srinagar to Sirobagarh",
                "severity": "High",
                "risk_score": 0.72,
                "risk_index": 0.72,
                "message": "HIGH ALERT on Srinagar to Sirobagarh: Geological instability & active rockfall hazard (3-day rain: 38.2 mm). Road clearance teams deployed.",
                "channel": "SMS",
                "issued_at": "2026-10-06T07:10:00Z",
                "rain_mm_3d": 38.2,
                "rain_status": "ok"
            }
        }
    }
    alert_id: str
    segment_id: str
    segment_name: str
    severity: str
    risk_score: float = Field(..., description="Legacy relative risk score (0.0 to 1.0)")
    risk_index: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relative risk index (0.0 to 1.0)")
    message: str
    channel: str
    issued_at: str
    # Additive fields
    rain_mm_3d: Optional[float] = None
    rain_status: Optional[str] = None
    main_driver: Optional[str] = None
    # Task 7 Localization fields (additive, optional)
    segment_name_en: Optional[str] = None
    severity_en: Optional[str] = None
    message_en: Optional[str] = None
    main_driver_en: Optional[str] = None

class AlertsResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 42,
                "subscriber_name": "Ramesh Negi",
                "subscribed_segment": "seg_08 (Srinagar to Sirobagarh)",
                "active_alerts_count": 1,
                "weather_source": "live",
                "is_simulated": False,
                "lang": "en",
                "alerts": [
                    {
                        "alert_id": "ALT-NH7-SEG_08-01",
                        "segment_id": "seg_08",
                        "segment_name": "Srinagar to Sirobagarh",
                        "severity": "High",
                        "risk_score": 0.72,
                        "risk_index": 0.72,
                        "message": "HIGH ALERT on Srinagar to Sirobagarh: Geological instability & active rockfall hazard (3-day rain: 38.2 mm).",
                        "channel": "SMS",
                        "issued_at": "2026-10-06T07:10:00Z",
                        "rain_mm_3d": 38.2,
                        "rain_status": "ok"
                    }
                ]
            }
        }
    }
    user_id: int
    subscriber_name: str
    subscribed_segment: str
    active_alerts_count: int
    alerts: List[AlertItem]
    # Task F2 Freshness & Simulation Metadata (additive, optional)
    weather_source: Optional[str] = None
    weather_fetched_at: Optional[str] = None
    weather_age_minutes: Optional[float] = None
    is_simulated: Optional[bool] = False
    stale_warning: Optional[str] = None
    # Task 7 Localization fields (additive, optional)
    subscribed_segment_en: Optional[str] = None
    lang: Optional[str] = "en"

# Task 7: Voice Alert Models
class VoiceAlertFallbackResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "मार्ग सलाह - ऋषिकेश to शिवपुरी: मध्यम ढलान नमी और फिसलन भरी सड़क स्थिति।",
                "tts": "browser",
                "lang": "hi"
            }
        }
    }
    text: str
    tts: str = "browser"
    lang: str = "en"

# --- Field Reports Models ---

class FieldReportCreate(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "lat": 30.2642,
                "lng": 79.2215,
                "description": "Loose scree and minor debris falling across northbound carriageway near milestone km 112.",
                "reporter_name": "Anil Joshi",
                "photo_url": "https://example.com/photos/rockfall_seg08.jpg"
            }
        }
    }
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of landslide observation")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude of landslide observation")
    description: str = Field(..., min_length=5, max_length=500, description="Details of rockfall, debris, road blockage")
    photo_url: Optional[str] = Field(None, max_length=500, description="Optional photo URL of the slide site")
    reporter_name: str = Field(..., min_length=2, max_length=100, description="Name of traveler, driver, or official")

class FieldReportResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "report_id": 101,
                "status": "Pending",
                "message": "Field report submitted successfully. Queued for verification by BRO / SDRF patrol.",
                "submitted_at": "2026-10-06T07:15:00Z"
            }
        }
    }
    report_id: int
    status: str
    message: str
    submitted_at: str

# --- Admin Validation Models ---

class AdminValidateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "report_id": 101,
                "decision": "Validated",
                "notes": "Verified by BRO Sector Patrol; road clearing teams deployed."
            }
        }
    }
    report_id: int = Field(..., description="ID of field report to validate")
    decision: Literal["Validated", "Rejected"] = Field(..., description="Decision status: Validated or Rejected")
    notes: Optional[str] = Field(None, description="Admin verification notes")

class AdminValidateResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "report_id": 101,
                "status": "Validated",
                "updated_at": "2026-10-06T07:18:00Z",
                "message": "Report #101 validated successfully and assigned to segment seg_08."
            }
        }
    }
    report_id: int
    status: str
    updated_at: str
    message: str

# --- Landslide History Models ---

class LandslideHistoryItem(BaseModel):
    id: int
    title: str
    location: str
    lat: float
    lng: float
    event_date: str
    description: str
    severity: str

class HistoryResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "corridor": "NH-7 Uttarakhand",
                "total_events": 309,
                "events": [
                    {
                        "id": 1,
                        "title": "Kaliasaur Major Rockfall",
                        "location": "NH-7 Km 147 near Kaliasaur Chute",
                        "lat": 30.2642,
                        "lng": 79.2215,
                        "event_date": "2024-08-14",
                        "description": "Massive debris flow triggered by 120mm rainfall over 24 hours. Highway closed for 36 hours.",
                        "severity": "Major"
                    }
                ]
            }
        }
    }
    corridor: str = "NH-7 Uttarakhand"
    total_events: int
    events: List[LandslideHistoryItem]

# --- Model Transparency & Info Models (Task F3) ---

class TrainingSampleSizes(BaseModel):
    presence_count: int = Field(..., description="Observed landslide events from published inventory")
    absence_count: int = Field(..., description="Sampled highway corridor background negative locations")
    total_count: int = Field(..., description="Total training and evaluation sample points")
    sampling_ratio: str = Field(..., description="Ratio of presence to absence samples")

class ValidationMetrics(BaseModel):
    spearman_rank_correlation: float = Field(..., description="Spearman rank correlation against surveyed landslide density")
    spearman_p_value: float = Field(..., description="P-value of Spearman rank correlation")
    pooled_auc: float = Field(..., description="Out-of-fold pooled ROC-AUC across spatial evaluation folds")
    pooled_auc_ci_95: List[float] = Field(..., description="95% block-bootstrap confidence interval for pooled AUC")
    block_auc_mean: float = Field(..., description="Mean ROC-AUC across spatial cross-validation blocks")
    block_auc_ci_95: List[float] = Field(..., description="95% block-bootstrap confidence interval for block AUC mean")
    average_precision: float = Field(..., description="Precision-Recall Area Under Curve (PR-AUC)")
    top_20_percent_capture: float = Field(..., description="Percentage of landslides captured in top 20% highest-ranked road length")
    negative_separation_distance_m: int = Field(..., description="Minimum metric buffer distance between negatives and scars (meters)")
    spatial_evaluation: str = Field(..., description="Spatial cross-validation grouping and buffer specification")

class ModelKWeights(BaseModel):
    k_rain: float = Field(..., description="Weight of rainfall term in composite relative risk index (0.0 to 1.0)")
    k_terrain: float = Field(..., description="Weight of static terrain percentile in composite relative risk index")
    rain_ref_mm: float = Field(..., description="3-day rainfall (mm) at which rainfall term reaches saturation")

class ThresholdItem(BaseModel):
    threshold: float = Field(..., description="Minimum relative risk index for this warning tier")
    level: str = Field(..., description="Categorical warning level label")

class ModelInfoResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "model_version": "RandomForestRegressor-v1.0-spatial-cv",
                "features_used": ["slope_deg", "relief_m", "elevation_m", "aspect_sin", "aspect_cos"],
                "coefficients": {"slope_deg": 0.42, "relief_m": 0.31, "elevation_m": 0.18},
                "training_sample_sizes": {
                    "presence_count": 309,
                    "absence_count": 618,
                    "total_count": 927,
                    "sampling_ratio": "1:2"
                },
                "validation_metrics": {
                    "spearman_rank_correlation": 0.68,
                    "spearman_p_value": 0.0001,
                    "pooled_auc": 0.812,
                    "pooled_auc_ci_95": [0.74, 0.88],
                    "block_auc_mean": 0.795,
                    "block_auc_ci_95": [0.72, 0.86],
                    "average_precision": 0.74,
                    "top_20_percent_capture": 0.61,
                    "negative_separation_distance_m": 250,
                    "spatial_evaluation": "5-fold spatial block cross-validation"
                },
                "thresholds": [
                    {"threshold": 0.80, "level": "Very High"},
                    {"threshold": 0.60, "level": "High"},
                    {"threshold": 0.35, "level": "Moderate"},
                    {"threshold": 0.00, "level": "Low"}
                ],
                "k": {"k_rain": 0.30, "k_terrain": 0.70, "rain_ref_mm": 100.0},
                "dry_cap": 0.35,
                "limitations": ["Heuristic rainfall weighting; NWP forecast skill attenuates past 48h."],
                "data_sources": {"inventory": "Mey et al. (2024)", "dem": "Copernicus 30m GLO-30", "weather": "Open-Meteo"},
                "scope": "NH-7 Rishikesh to Joshimath (247.37 km)"
            }
        }
    }
    model_version: str = Field(..., description="Model version tag and architecture")
    features_used: List[str] = Field(..., description="List of topographic/hydrological features used by model")
    coefficients: Dict[str, float] = Field(..., description="Permutation importance delta-AUC on held-out spatial blocks")
    training_sample_sizes: TrainingSampleSizes = Field(..., description="Training and cross-validation sample counts")
    validation_metrics: ValidationMetrics = Field(..., description="Rigorous out-of-fold spatial validation metrics")
    thresholds: List[ThresholdItem] = Field(..., description="Risk-level threshold boundaries")
    k: ModelKWeights = Field(..., description="Weights used in composite relative risk index")
    dry_cap: float = Field(..., description="Rainfall threshold below which risk is capped at Moderate during dry weather")
    limitations: List[str] = Field(..., description="Transparent scientific limitations and operational boundaries")
    data_sources: Dict[str, str] = Field(..., description="Citations and data sources for inventory, DEM, and meteorology")
    scope: str = Field(..., description="Evaluated geographical corridor scope")


# --- Task 4: Consequence & BRO Operational Priority Models ---

class PrioritySegmentItem(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "id": "seg_03",
                "name": "Byasi to Kaudiyala",
                "sequence_order": 3,
                "risk_level": "High",
                "risk_score": 0.72,
                "risk_index": 0.72,
                "consequence_score": 0.556,
                "priority_score": 0.400,
                "nearest_town": "Chaundli",
                "nearest_town_km": 2.21,
                "nearest_hospital": "Government Hospital, Katghar",
                "nearest_hospital_km": 13.91,
                "lodging_count_5km": 0,
                "has_alternate_route": False,
                "traffic_index": 3,
                "recommended_action": "Pre-position earthmover at Byasi transit yard",
                "rank": 1
            }
        }
    }
    id: str
    name: str
    sequence_order: int
    risk_level: str
    risk_score: float = Field(..., description="Legacy relative risk score (0.0 to 1.0)")
    risk_index: float = Field(..., description="Relative risk index (0.0 to 1.0)")
    consequence_score: float = Field(..., description="Indicative blockage consequence index (0.0 to 1.0)")
    priority_score: float = Field(..., description="Indicative BRO operational priority score (risk_index * consequence_score)")
    nearest_town: Optional[str] = None
    nearest_town_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    nearest_hospital_km: Optional[float] = None
    lodging_count_5km: Optional[int] = None
    has_alternate_route: Optional[bool] = None
    traffic_index: Optional[int] = None
    recommended_action: str = Field(..., description="Indicative recommended operational action template")
    rank: int = Field(..., description="Corridor priority ranking (1 = highest urgency)")

class PriorityListResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
                "total_segments": 18,
                "status": "indicative",
                "disclaimer": "Indicative BRO / SDRF operational priority list combining landslide hazard and blockage consequence metrics. Traffic index and alternate route availability are indicative assumptions. Does not replace physical field reconnaissance.",
                "is_simulated": False,
                "segments": [
                    {
                        "id": "seg_03",
                        "name": "Byasi to Kaudiyala",
                        "sequence_order": 3,
                        "risk_level": "High",
                        "risk_score": 0.72,
                        "risk_index": 0.72,
                        "consequence_score": 0.556,
                        "priority_score": 0.400,
                        "nearest_town": "Chaundli",
                        "nearest_town_km": 2.21,
                        "nearest_hospital": "Government Hospital, Katghar",
                        "nearest_hospital_km": 13.91,
                        "recommended_action": "Pre-position earthmover at Byasi transit yard",
                        "rank": 1
                    }
                ]
            }
        }
    }
    corridor: str = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
    total_segments: int
    status: str = "indicative"
    disclaimer: str = (
        "Indicative BRO / SDRF operational priority list combining landslide hazard "
        "and blockage consequence metrics. Traffic index and alternate route availability "
        "are indicative assumptions. Does not replace physical field reconnaissance."
    )
    is_simulated: bool = False
    segments: List[PrioritySegmentItem]


# --- Task 8: Offline Pack Models ---

class OfflineEmergencyContact(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "National Emergency Helpline",
                "number": "112"
            }
        }
    }
    name: str
    number: str = ""

class OfflineSegmentItem(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "seg_01",
                "name": "Rishikesh to Shivpuri",
                "simplified_polyline": [[30.0869, 78.2676], [30.1357, 78.3892]],
                "current_risk_level": "Moderate",
                "risk_level": "Moderate",
                "terrain_risk_level": "Low",
                "advisory_en": "ADVISORY on Rishikesh to Shivpuri: Moderate slope wetness and slippery road conditions.",
                "advisory_hi": "मार्ग सलाह - ऋषिकेश to शिवपुरी: मध्यम ढलान नमी और फिसलन भरी सड़क स्थिति।",
                "nearest_hospital": "Ayurveda Center"
            }
        }
    }
    id: str
    name: str
    simplified_polyline: List[List[float]] = []
    current_risk_level: str
    risk_level: Optional[str] = None
    terrain_risk_level: str
    advisory_en: str
    advisory_hi: str
    nearest_hospital: Optional[str] = None

class OfflinePackResponse(BaseModel):
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "version": "8b0d64dcc91a80ac",
                "generated_at": "2026-10-06T07:15:00Z",
                "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
                "total_segments": 18,
                "emergency_contacts": [
                    {"name": "National Emergency Helpline", "number": "112"},
                    {"name": "State Disaster Management (SDMA Uttarakhand)", "number": ""}
                ],
                "segments": [
                    {
                        "id": "seg_01",
                        "name": "Rishikesh to Shivpuri",
                        "simplified_polyline": [[30.0869, 78.2676], [30.1357, 78.3892]],
                        "current_risk_level": "Moderate",
                        "risk_level": "Moderate",
                        "terrain_risk_level": "Low",
                        "advisory_en": "ADVISORY on Rishikesh to Shivpuri: Moderate slope wetness.",
                        "advisory_hi": "मार्ग सलाह - ऋषिकेश to शिवपुरी: मध्यम ढलान नमी।",
                        "nearest_hospital": "Ayurveda Center"
                    }
                ]
            }
        }
    }
    version: str
    generated_at: str
    corridor: str = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
    total_segments: int
    emergency_contacts: List[OfflineEmergencyContact]
    segments: List[OfflineSegmentItem]


# --- Health Probe Model ---

class HealthResponse(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "system": "NH-7 Landslide Risk Backend",
                "corridor": "Rishikesh-Joshimath",
                "app_version": "1.0.0",
                "db_ok": True,
                "weather_source": "live",
                "scheduler_last_run": "2026-10-06T07:30:00Z"
            }
        }
    }
    status: str
    system: str
    corridor: str
    app_version: str
    db_ok: bool
    weather_source: str
    scheduler_last_run: Optional[str] = None
