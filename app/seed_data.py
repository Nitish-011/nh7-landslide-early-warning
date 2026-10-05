import json
from datetime import datetime, timezone

# 18 Named NH-7 Segments between Rishikesh and Joshimath
# Each segment includes sub-points spaced 2-4 km apart for fine-grained risk modeling
SEED_SEGMENTS = [
    {
        "id": "seg_01",
        "name": "Rishikesh to Shivpuri",
        "sequence_order": 1,
        "start_lat": 30.0869,
        "start_lng": 78.2676,
        "end_lat": 30.1357,
        "end_lng": 78.3892,
        "subpoints": [
            [30.0869, 78.2676],
            [30.0980, 78.3050],
            [30.1150, 78.3450],
            [30.1357, 78.3892]
        ],
        "risk_level": "Low",
        "risk_score": 0.15,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_02",
        "name": "Shivpuri to Byasi",
        "sequence_order": 2,
        "start_lat": 30.1357,
        "start_lng": 78.3892,
        "end_lat": 30.1472,
        "end_lng": 78.4839,
        "subpoints": [
            [30.1357, 78.3892],
            [30.1410, 78.4200],
            [30.1440, 78.4550],
            [30.1472, 78.4839]
        ],
        "risk_level": "Moderate",
        "risk_score": 0.35,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_03",
        "name": "Byasi to Kaudiyala",
        "sequence_order": 3,
        "start_lat": 30.1472,
        "start_lng": 78.4839,
        "end_lat": 30.0765,
        "end_lng": 78.5028,
        "subpoints": [
            [30.1472, 78.4839],
            [30.1200, 78.4900],
            [30.0950, 78.4980],
            [30.0765, 78.5028]
        ],
        "risk_level": "High",
        "risk_score": 0.72,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_04",
        "name": "Kaudiyala to Devprayag",
        "sequence_order": 4,
        "start_lat": 30.0765,
        "start_lng": 78.5028,
        "end_lat": 30.1459,
        "end_lng": 78.5986,
        "subpoints": [
            [30.0765, 78.5028],
            [30.0950, 78.5350],
            [30.1250, 78.5700],
            [30.1459, 78.5986]
        ],
        "risk_level": "Moderate",
        "risk_score": 0.42,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_05",
        "name": "Devprayag to Teen Dhara",
        "sequence_order": 5,
        "start_lat": 30.1459,
        "start_lng": 78.5986,
        "end_lat": 30.2015,
        "end_lng": 78.6820,
        "subpoints": [
            [30.1459, 78.5986],
            [30.1650, 78.6250],
            [30.1850, 78.6550],
            [30.2015, 78.6820]
        ],
        "risk_level": "High",
        "risk_score": 0.78,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_06",
        "name": "Teen Dhara to Kirtinagar",
        "sequence_order": 6,
        "start_lat": 30.2015,
        "start_lng": 78.6820,
        "end_lat": 30.2173,
        "end_lng": 78.7456,
        "subpoints": [
            [30.2015, 78.6820],
            [30.2080, 78.7050],
            [30.2130, 78.7250],
            [30.2173, 78.7456]
        ],
        "risk_level": "Low",
        "risk_score": 0.20,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_07",
        "name": "Kirtinagar to Srinagar",
        "sequence_order": 7,
        "start_lat": 30.2173,
        "start_lng": 78.7456,
        "end_lat": 30.2224,
        "end_lng": 78.7845,
        "subpoints": [
            [30.2173, 78.7456],
            [30.2195, 78.7600],
            [30.2224, 78.7845]
        ],
        "risk_level": "Low",
        "risk_score": 0.18,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_08",
        "name": "Srinagar to Sirobagarh",
        "sequence_order": 8,
        "start_lat": 30.2224,
        "start_lng": 78.7845,
        "end_lat": 30.2390,
        "end_lng": 78.8540,
        "subpoints": [
            [30.2224, 78.7845],
            [30.2280, 78.8100],
            [30.2340, 78.8350],
            [30.2390, 78.8540]
        ],
        "risk_level": "Very High",
        "risk_score": 0.92,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_09",
        "name": "Sirobagarh to Rudraprayag",
        "sequence_order": 9,
        "start_lat": 30.2390,
        "start_lng": 78.8540,
        "end_lat": 30.2844,
        "end_lng": 78.9811,
        "subpoints": [
            [30.2390, 78.8540],
            [30.2520, 78.8950],
            [30.2680, 78.9400],
            [30.2844, 78.9811]
        ],
        "risk_level": "Very High",
        "risk_score": 0.88,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_10",
        "name": "Rudraprayag to Gauchar",
        "sequence_order": 10,
        "start_lat": 30.2844,
        "start_lng": 78.9811,
        "end_lat": 30.2872,
        "end_lng": 79.1557,
        "subpoints": [
            [30.2844, 78.9811],
            [30.2850, 79.0400],
            [30.2860, 79.1000],
            [30.2872, 79.1557]
        ],
        "risk_level": "Moderate",
        "risk_score": 0.48,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_11",
        "name": "Gauchar to Karnaprayag",
        "sequence_order": 11,
        "start_lat": 30.2872,
        "start_lng": 79.1557,
        "end_lat": 30.2587,
        "end_lng": 79.2173,
        "subpoints": [
            [30.2872, 79.1557],
            [30.2780, 79.1800],
            [30.2587, 79.2173]
        ],
        "risk_level": "Low",
        "risk_score": 0.25,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_12",
        "name": "Karnaprayag to Langasu",
        "sequence_order": 12,
        "start_lat": 30.2587,
        "start_lng": 79.2173,
        "end_lat": 30.2980,
        "end_lng": 79.2550,
        "subpoints": [
            [30.2587, 79.2173],
            [30.2780, 79.2380],
            [30.2980, 79.2550]
        ],
        "risk_level": "Moderate",
        "risk_score": 0.38,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_13",
        "name": "Langasu to Nandprayag",
        "sequence_order": 13,
        "start_lat": 30.2980,
        "start_lng": 79.2550,
        "end_lat": 30.3308,
        "end_lng": 79.3242,
        "subpoints": [
            [30.2980, 79.2550],
            [30.3120, 79.2850],
            [30.3308, 79.3242]
        ],
        "risk_level": "Moderate",
        "risk_score": 0.44,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_14",
        "name": "Nandprayag to Chamoli",
        "sequence_order": 14,
        "start_lat": 30.3308,
        "start_lng": 79.3242,
        "end_lat": 30.4074,
        "end_lng": 79.3524,
        "subpoints": [
            [30.3308, 79.3242],
            [30.3600, 79.3350],
            [30.3850, 79.3450],
            [30.4074, 79.3524]
        ],
        "risk_level": "High",
        "risk_score": 0.68,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_15",
        "name": "Chamoli to Birahi",
        "sequence_order": 15,
        "start_lat": 30.4074,
        "start_lng": 79.3524,
        "end_lat": 30.4350,
        "end_lng": 79.3900,
        "subpoints": [
            [30.4074, 79.3524],
            [30.4200, 79.3700],
            [30.4350, 79.3900]
        ],
        "risk_level": "High",
        "risk_score": 0.75,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_16",
        "name": "Birahi to Pipalkoti",
        "sequence_order": 16,
        "start_lat": 30.4350,
        "start_lng": 79.3900,
        "end_lat": 30.4297,
        "end_lng": 79.4304,
        "subpoints": [
            [30.4350, 79.3900],
            [30.4320, 79.4100],
            [30.4297, 79.4304]
        ],
        "risk_level": "Moderate",
        "risk_score": 0.50,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_17",
        "name": "Pipalkoti to Helang (Tangani)",
        "sequence_order": 17,
        "start_lat": 30.4297,
        "start_lng": 79.4304,
        "end_lat": 30.5280,
        "end_lng": 79.5380,
        "subpoints": [
            [30.4297, 79.4304],
            [30.4600, 79.4700],
            [30.4950, 79.5100],
            [30.5280, 79.5380]
        ],
        "risk_level": "Very High",
        "risk_score": 0.94,
        "updated_at": "2026-10-02T10:00:00Z"
    },
    {
        "id": "seg_18",
        "name": "Helang to Joshimath",
        "sequence_order": 18,
        "start_lat": 30.5280,
        "start_lng": 79.5380,
        "end_lat": 30.5564,
        "end_lng": 79.5663,
        "subpoints": [
            [30.5280, 79.5380],
            [30.5400, 79.5500],
            [30.5564, 79.5663]
        ],
        "risk_level": "High",
        "risk_score": 0.81,
        "updated_at": "2026-10-02T10:00:00Z"
    }
]

# Seed Subscriptions
SEED_SUBSCRIPTIONS = [
    {
        "name": "Amit Rawat",
        "phone_or_email": "+919876543210",
        "segment_id": "seg_08",
        "channel": "WhatsApp",
        "created_at": "2026-10-01T08:30:00Z"
    },
    {
        "name": "Priya Negi",
        "phone_or_email": "priya.negi@uttarakhand-travel.in",
        "segment_id": "seg_17",
        "channel": "Email",
        "created_at": "2026-10-01T09:15:00Z"
    },
    {
        "name": "Rajesh Bhatt",
        "phone_or_email": "+919812345678",
        "segment_id": "seg_01",
        "channel": "SMS",
        "created_at": "2026-10-01T11:00:00Z"
    }
]

# Seed Field Reports
SEED_FIELD_REPORTS = [
    {
        "lat": 30.2392,
        "lng": 78.8544,
        "description": "Continuous rockfall and debris rolling onto uphill lane near milestone 114 (Sirobagarh). Traffic stopped.",
        "photo_url": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=600&q=80",
        "reporter_name": "Suresh Negi (Commercial Driver)",
        "status": "Pending",
        "decision_notes": "Pending inspection by BRO sector team.",
        "created_at": "2026-10-02T06:45:00Z",
        "updated_at": "2026-10-02T06:45:00Z"
    },
    {
        "lat": 30.4930,
        "lng": 79.5120,
        "description": "Pavement subsidence and longitudinal shear cracks after heavy morning downpour near Tangani slide.",
        "photo_url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=600&q=80",
        "reporter_name": "Vikram Chauhan (NHIDCL Patrol)",
        "status": "Validated",
        "decision_notes": "Confirmed by on-site engineer; heavy vehicles restricted to single-file passage.",
        "created_at": "2026-10-01T14:20:00Z",
        "updated_at": "2026-10-01T15:00:00Z"
    },
    {
        "lat": 30.1465,
        "lng": 78.5990,
        "description": "Gravel accumulation cleared by earthmovers near Devprayag sangam bend; one lane open.",
        "photo_url": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=600&q=80",
        "reporter_name": "Deepak Joshi (Local Volunteer)",
        "status": "Validated",
        "decision_notes": "Cleared and validated by local highway control room.",
        "created_at": "2026-10-01T18:10:00Z",
        "updated_at": "2026-10-01T19:00:00Z"
    }
]

# Real past landslide incidents along NH-7 in Uttarakhand
SEED_LANDSLIDE_HISTORY = [
    {
        "title": "Sirobagarh Chronic Landslide Complex",
        "location": "NH-7 Between Srinagar and Rudraprayag (Km 114)",
        "lat": 30.2390,
        "lng": 78.8540,
        "event_date": "July 2023",
        "description": "One of the most persistent landslide zones in Uttarakhand. Fragile phyllite slopes collapsed during heavy monsoon rain, blocking NH-7 for over 48 hours.",
        "severity": "Very High"
    },
    {
        "title": "Chamoli Rock Avalanche & Debris Surge",
        "location": "Rishi Ganga / Alaknanda Valley, Chamoli",
        "lat": 30.4074,
        "lng": 79.3524,
        "event_date": "February 2021",
        "description": "Massive hanging glacier and rock detachment caused catastrophic flash flooding and riverbank scour, washing away bridges and damaging highway retaining walls along NH-7.",
        "severity": "Catastrophic"
    },
    {
        "title": "Pipalkoti Highway Boulder Slip",
        "location": "NH-7 Near Pipalkoti Market Approach",
        "lat": 30.4297,
        "lng": 79.4304,
        "event_date": "August 2022",
        "description": "Sudden failure of weathered quartzite cliff sent house-sized boulders crashing onto the highway, stranding over 1,200 pilgrimage vehicles.",
        "severity": "High"
    },
    {
        "title": "Tangani / Gulabkoti Slide Zone",
        "location": "NH-7 Valley Slope Below Joshimath",
        "lat": 30.4920,
        "lng": 79.5100,
        "event_date": "July 2023",
        "description": "Active landslide zone triggered by toe erosion from the Alaknanda River, continuously eroding the mountain slope under the highway.",
        "severity": "Very High"
    },
    {
        "title": "Byasi Gorge Rockfall",
        "location": "NH-7 Near Byasi, Tehri Garhwal",
        "lat": 30.1472,
        "lng": 78.4839,
        "event_date": "September 2020",
        "description": "Steep rocky canyon face failure following intense monsoon precipitation, obstructing traffic between Rishikesh and Devprayag.",
        "severity": "Moderate"
    },
    {
        "title": "Nandprayag Confluence Highway Slip",
        "location": "NH-7 Near Nandprayag Sangam",
        "lat": 30.3308,
        "lng": 79.3242,
        "event_date": "August 2019",
        "description": "Cloudburst-triggered debris flow inundated the highway carriageway with 3 meters of mud and tree trunks.",
        "severity": "High"
    },
    {
        "title": "Teen Dhara Debris Flow",
        "location": "NH-7 Between Devprayag and Teen Dhara",
        "lat": 30.2015,
        "lng": 78.6820,
        "event_date": "August 2021",
        "description": "Overnight cloudburst sent tons of loose mountain slurry over roadside dhabas and damaged 150m of tarmac.",
        "severity": "High"
    }
]
