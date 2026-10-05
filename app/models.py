from typing import List, Optional, Literal
from pydantic import BaseModel, Field

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
    risk_score: float
    updated_at: str
    # Additive fields from trained model & rainfall engine
    terrain_percentile: Optional[float] = None
    terrain_level: Optional[str] = None
    terrain_status: Optional[str] = None
    rain_mm_3d: Optional[float] = None
    rain_status: Optional[str] = None
    main_driver: Optional[str] = None
    method: Optional[str] = None

class RiskMapResponse(BaseModel):
    corridor: str = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
    total_segments: int
    high_or_very_high_risk_count: int
    segments: List[SegmentResponse]

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
    risk_score: float
    # Additive fields
    terrain_percentile: Optional[float] = None
    terrain_level: Optional[str] = None
    terrain_status: Optional[str] = None
    rain_mm_3d: Optional[float] = None
    rain_status: Optional[str] = None
    main_driver: Optional[str] = None
    method: Optional[str] = None

class RouteRiskResponse(BaseModel):
    from_segment: str
    to_segment: str
    from_segment_name: str
    to_segment_name: str
    date: str
    total_segments: int
    max_risk_level: str
    average_risk_score: float
    advisory: str
    segments: List[RouteSegmentRisk]

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
    risk_score: float
    message: str
    channel: str
    issued_at: str
    # Additive fields
    rain_mm_3d: Optional[float] = None
    rain_status: Optional[str] = None
    main_driver: Optional[str] = None

class AlertsResponse(BaseModel):
    user_id: int
    subscriber_name: str
    subscribed_segment: str
    active_alerts_count: int
    alerts: List[AlertItem]

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
