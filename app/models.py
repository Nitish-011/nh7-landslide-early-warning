from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# --- Road Closure Models (Task 5) ---

class RoadClosureCreate(BaseModel):
    model_config = {"extra": "ignore"}
    segment_id: str = Field(..., description="ID of NH-7 segment affected (e.g. seg_08)")
    status: Literal["closed", "one_way", "restricted"] = Field(..., description="Closure status")
    reason: str = Field(..., min_length=3, description="Official cause of closure")
    source: str = Field(..., min_length=2, description="Issuing agency, e.g. BRO, Uttarakhand Police")
    starts_at: Optional[str] = Field(None, description="ISO-8601 start timestamp (defaults to current time)")
    ends_at: Optional[str] = Field(None, description="ISO-8601 end timestamp (nullable)")
    created_by: Optional[str] = Field("admin", description="Admin username or authority ID")

class RoadClosureResponse(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    segment_id: str
    status: str
    reason: str
    source: str
    starts_at: str
    ends_at: Optional[str] = None
    created_by: str
    created_at: str

# --- Segments & Risk Models ---

class SegmentCoords(BaseModel):
    lat: float
    lng: float

class SegmentResponse(BaseModel):
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
    model_config = {"extra": "ignore"}
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
    model_config = {"extra": "ignore"}
    depart_time: str
    max_risk_level: str
    summary: str
    total_risk_score: Optional[float] = None

class TripRecommendation(BaseModel):
    model_config = {"extra": "ignore"}
    action: str  # GO, CAUTION, DELAY, AVOID
    action_code: str  # REC_GO, REC_CAUTION, REC_DELAY, REC_AVOID
    reason: str
    params: Dict[str, Any] = {}
    best_departure_options: List[DepartureOption] = []
    # Task 7 Localization fields (additive, optional)
    action_en: Optional[str] = None
    reason_en: Optional[str] = None

class RouteSegmentRisk(BaseModel):
    id: str
    name: str
    sequence_order: int
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    subpoints: List[List[float]] = []
    subpoint_risk_scores: List[float] = []
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
    subscription_id: int
    status: str = "Active"
    message: str
    subscription: SubscriptionDetail

# --- Alerts Models ---

class AlertItem(BaseModel):
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
    text: str
    tts: str = "browser"
    lang: str = "en"

# --- Field Reports Models ---

class FieldReportCreate(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of landslide observation")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude of landslide observation")
    description: str = Field(..., min_length=5, max_length=500, description="Details of rockfall, debris, road blockage")
    photo_url: Optional[str] = Field(None, max_length=500, description="Optional photo URL of the slide site")
    reporter_name: str = Field(..., min_length=2, max_length=100, description="Name of traveler, driver, or official")

class FieldReportResponse(BaseModel):
    report_id: int
    status: str
    message: str
    submitted_at: str

# --- Admin Validation Models ---

class AdminValidateRequest(BaseModel):
    report_id: int = Field(..., description="ID of field report to validate")
    decision: Literal["Validated", "Rejected"] = Field(..., description="Decision status: Validated or Rejected")
    notes: Optional[str] = Field(None, description="Admin verification notes")

class AdminValidateResponse(BaseModel):
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
    model_config = {"extra": "ignore"}
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
    model_config = {"extra": "ignore"}
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
    name: str
    number: str = ""

class OfflineSegmentItem(BaseModel):
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
    version: str
    generated_at: str
    corridor: str = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
    total_segments: int
    emergency_contacts: List[OfflineEmergencyContact]
    segments: List[OfflineSegmentItem]


