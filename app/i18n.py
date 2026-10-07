"""
app/i18n.py - Localization (English & Hindi) for NH-7 Landslide Early Warning System.

Contains English and Hindi string tables for:
- Standardized risk level names
- Contextual travel and subscriber advisories
- Trip recommendation action codes (GO / CAUTION / DELAY / AVOID)
- Transliterated highway segment and town names (phonetic Devanagari)
- Templated Hindi versions of explainability drivers (slope, local relief, elevation, aspect)
- Compact voice advisory generators (max ~300 chars, short sentences)

All Hindi strings are explicitly marked with '# NEEDS NATIVE REVIEW'.
"""

import re
from typing import Dict, Any, Optional, Tuple

# --- 1. Risk Level Names ---

RISK_LEVEL_NAMES_EN: Dict[str, str] = {
    "Low": "Low",
    "Moderate": "Moderate",
    "High": "High",
    "Very High": "Very High",
}

RISK_LEVEL_NAMES_HI: Dict[str, str] = {
    "Low": "कम",  # NEEDS NATIVE REVIEW
    "Moderate": "मध्यम",  # NEEDS NATIVE REVIEW
    "High": "उच्च",  # NEEDS NATIVE REVIEW
    "Very High": "अत्यधिक",  # NEEDS NATIVE REVIEW
}

# --- 2. Recommendation Action Codes & Disclaimers ---

DISCLAIMER_EN = (
    "Decision-support prototype, not an official warning. Low risk does not mean safe. "
    "Landslides also occur in dry weather. Follow BRO/SDRF/police advisories. Emergency: 112"
)

DISCLAIMER_HI = (
    "निर्णय-समर्थन प्रोटोटाइप, आधिकारिक चेतावनी नहीं। कम जोखिम का अर्थ सुरक्षित नहीं है। "  # NEEDS NATIVE REVIEW
    "सूखे मौसम में भी भूस्खलन हो सकता है। बीआरओ/एसडीआरएफ/पुलिस सलाह का पालन करें। आपातकाल: 112"  # NEEDS NATIVE REVIEW
)

ACTION_CODES_EN: Dict[str, str] = {
    "LOW RISK – proceed with caution": "LOW RISK – proceed with caution",
    "CAUTION": "CAUTION",
    "DELAY": "DELAY",
    "AVOID": "AVOID",
    "GO": "LOW RISK – proceed with caution",
}

ACTION_CODES_HI: Dict[str, str] = {
    "LOW RISK – proceed with caution": "कम जोखिम – सावधानी बरतें",  # NEEDS NATIVE REVIEW
    "CAUTION": "सावधानी बरतें",  # NEEDS NATIVE REVIEW
    "DELAY": "यात्रा में विलंब करें",  # NEEDS NATIVE REVIEW
    "AVOID": "यात्रा से बचें",  # NEEDS NATIVE REVIEW
    "GO": "कम जोखिम – सावधानी बरतें",  # NEEDS NATIVE REVIEW
}

# --- 3. Highway Segment Transliterations (Phonetic Devanagari, Not Machine-Translated) ---

SEGMENT_TRANSLITERATIONS_HI: Dict[str, str] = {
    "seg_01": "ऋषिकेश से शिवपुरी",  # NEEDS NATIVE REVIEW
    "seg_02": "शिवपुरी से ब्यासी",  # NEEDS NATIVE REVIEW
    "seg_03": "ब्यासी से कौड़ियाला",  # NEEDS NATIVE REVIEW
    "seg_04": "कौड़ियाला से देवप्रयाग",  # NEEDS NATIVE REVIEW
    "seg_05": "देवप्रयाग से तीन धारा",  # NEEDS NATIVE REVIEW
    "seg_06": "तीन धारा से कीर्तिनगर",  # NEEDS NATIVE REVIEW
    "seg_07": "कीर्तिनगर से श्रीनगर",  # NEEDS NATIVE REVIEW
    "seg_08": "श्रीनगर से सिरोबगड़",  # NEEDS NATIVE REVIEW
    "seg_09": "सिरोबगड़ से रुद्रप्रयाग",  # NEEDS NATIVE REVIEW
    "seg_10": "रुद्रप्रयाग से गौचर",  # NEEDS NATIVE REVIEW
    "seg_11": "गौचर से कर्णप्रयाग",  # NEEDS NATIVE REVIEW
    "seg_12": "कर्णप्रयाग से लांगासू",  # NEEDS NATIVE REVIEW
    "seg_13": "लांगासू से नंदप्रयाग",  # NEEDS NATIVE REVIEW
    "seg_14": "नंदप्रयाग से चमोली",  # NEEDS NATIVE REVIEW
    "seg_15": "चमोली से बिरही",  # NEEDS NATIVE REVIEW
    "seg_16": "बिरही से पीपलकोटी",  # NEEDS NATIVE REVIEW
    "seg_17": "पीपलकोटी से हेलांग (तंगणी)",  # NEEDS NATIVE REVIEW
    "seg_18": "हेलांग से जोशीमठ",  # NEEDS NATIVE REVIEW
}

TOWN_TRANSLITERATIONS_HI: Dict[str, str] = {
    "Rishikesh": "ऋषिकेश",  # NEEDS NATIVE REVIEW
    "Shivpuri": "शिवपुरी",  # NEEDS NATIVE REVIEW
    "Byasi": "ब्यासी",  # NEEDS NATIVE REVIEW
    "Kaudiyala": "कौड़ियाला",  # NEEDS NATIVE REVIEW
    "Devprayag": "देवप्रयाग",  # NEEDS NATIVE REVIEW
    "Teen Dhara": "तीन धारा",  # NEEDS NATIVE REVIEW
    "Kirtinagar": "कीर्तिनगर",  # NEEDS NATIVE REVIEW
    "Srinagar": "श्रीनगर",  # NEEDS NATIVE REVIEW
    "Sirobagarh": "सिरोबगड़",  # NEEDS NATIVE REVIEW
    "Rudraprayag": "रुद्रप्रयाग",  # NEEDS NATIVE REVIEW
    "Gauchar": "गौचर",  # NEEDS NATIVE REVIEW
    "Karnaprayag": "कर्णप्रयाग",  # NEEDS NATIVE REVIEW
    "Langasu": "लांगासू",  # NEEDS NATIVE REVIEW
    "Nandprayag": "नंदप्रयाग",  # NEEDS NATIVE REVIEW
    "Chamoli": "चमोली",  # NEEDS NATIVE REVIEW
    "Birahi": "बिरही",  # NEEDS NATIVE REVIEW
    "Pipalkoti": "पीपलकोटी",  # NEEDS NATIVE REVIEW
    "Helang": "हेलांग",  # NEEDS NATIVE REVIEW
    "Tangani": "तंगणी",  # NEEDS NATIVE REVIEW
    "Joshimath": "जोशीमठ",  # NEEDS NATIVE REVIEW
    "Badrinath": "बद्रीनाथ",  # NEEDS NATIVE REVIEW
    "Kedarnath": "केदारनाथ",  # NEEDS NATIVE REVIEW
}

# --- 4. Corridor & System Strings ---

CORRIDOR_NAME_EN = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
CORRIDOR_NAME_HI = "एनएच-7 उत्तराखंड (ऋषिकेश - कर्णप्रयाग - जोशीमठ)"  # NEEDS NATIVE REVIEW

# --- 5. Main Driver Explainability Strings & Templates ---

FEATURE_HI: Dict[str, str] = {
    "slope": "ढलान",  # NEEDS NATIVE REVIEW
    "local relief": "स्थानीय उच्चावच (राहत)",  # NEEDS NATIVE REVIEW
    "elevation": "ऊंचाई",  # NEEDS NATIVE REVIEW
    "slope aspect (north-south)": "ढलान की दिशा (उत्तर-दक्षिण)",  # NEEDS NATIVE REVIEW
    "rainfall": "वर्षा",  # NEEDS NATIVE REVIEW
}

DIRECTION_HI: Dict[str, str] = {
    "high": "अधिक",  # NEEDS NATIVE REVIEW
    "low": "कम",  # NEEDS NATIVE REVIEW
}

# Template filling in slope and relief numbers:
SLOPE_RELIEF_DRIVER_TEMPLATE_HI = "तीव्र ढलान ({slope_deg:.1f}°) और स्थानीय उच्चावच ({relief_m:.0f} मी)"  # NEEDS NATIVE REVIEW
MAIN_DRIVER_TEMPLATE_HI = "इस मार्ग के लिए असामान्य {feature} ({direction}, z={z})"  # NEEDS NATIVE REVIEW
DEFAULT_TERRAIN_DRIVER_HI = "भौगोलिक भूभाग की ढलान एवं उच्चावच"  # NEEDS NATIVE REVIEW

# Regex matching: "unusual slope for this road (low, z=-1.0)"
DRIVER_REGEX = re.compile(r"unusual\s+(.+?)\s+for\s+this\s+road\s*\((high|low),\s*z=([+-]?[0-9.]+)\)", re.IGNORECASE)


def format_slope_relief_driver_hi(slope_deg: float, relief_m: float) -> str:
    """Formats a Hindi driver string explicitly specifying slope in degrees and local relief in meters."""
    return SLOPE_RELIEF_DRIVER_TEMPLATE_HI.format(slope_deg=slope_deg, relief_m=relief_m)


def localize_segment_name(segment_id: str, default_name: str, lang: str = "en") -> str:
    """Returns transliterated segment name if lang='hi', else English name."""
    if lang == "hi":
        return SEGMENT_TRANSLITERATIONS_HI.get(segment_id, default_name)
    return default_name


def transliterate_town(town_name: str, lang: str = "en") -> str:
    """Transliterates known landmark/town names to Hindi."""
    if lang == "hi":
        for en, hi in TOWN_TRANSLITERATIONS_HI.items():
            if en.lower() in town_name.lower():
                town_name = re.sub(re.escape(en), hi, town_name, flags=re.IGNORECASE)
        return town_name
    return town_name


def localize_risk_level(level: Optional[str], lang: str = "en") -> Optional[str]:
    """Returns localized risk level string."""
    if not level:
        return level
    if lang == "hi":
        return RISK_LEVEL_NAMES_HI.get(level, level)
    return RISK_LEVEL_NAMES_EN.get(level, level)


def localize_action_code(action: Optional[str], lang: str = "en") -> Optional[str]:
    """Returns localized action recommendation."""
    if not action:
        return action
    if lang == "hi":
        return ACTION_CODES_HI.get(action, action)
    return ACTION_CODES_EN.get(action, action)


def localize_main_driver(
    driver_en: Optional[str],
    lang: str = "en",
    slope_deg: Optional[float] = None,
    relief_m: Optional[float] = None
) -> Optional[str]:
    """
    Translates or formats the explainability driver.
    If slope_deg and relief_m are provided, uses the numerical template.
    If an existing driver string is given (e.g. from segment_static_scores.json), parses it into Hindi.
    """
    if not driver_en and slope_deg is None and relief_m is None:
        return None

    if lang != "hi":
        if slope_deg is not None and relief_m is not None:
            return f"steep slope ({slope_deg:.1f}°) and local relief ({relief_m:.0f}m)"
        return driver_en

    # Hindi localization:
    if slope_deg is not None and relief_m is not None:
        return format_slope_relief_driver_hi(slope_deg, relief_m)

    if not driver_en:
        return DEFAULT_TERRAIN_DRIVER_HI

    match = DRIVER_REGEX.search(driver_en)
    if match:
        raw_feat, raw_dir, z_val = match.groups()
        raw_feat_lower = raw_feat.lower()
        raw_dir_lower = raw_dir.lower()
        feat_hi = FEATURE_HI.get(raw_feat_lower, raw_feat)
        dir_hi = DIRECTION_HI.get(raw_dir_lower, raw_dir)
        return MAIN_DRIVER_TEMPLATE_HI.format(feature=feat_hi, direction=dir_hi, z=z_val)

    return DEFAULT_TERRAIN_DRIVER_HI


# --- 6. Contextual Travel Advisory Templates ---

ROUTE_ADVISORIES_EN = {
    "closure": "OFFICIAL CLOSURE WARNING: Road closure active on {segment}. Avoid travel across this sector.",
    "Very High": "CRITICAL WARNING for {date}: High susceptibility to slope failure and active shooting stones along route. Check BRO updates.",
    "High": "ELEVATED RISK for {date}: Moderate to severe landslide vulnerability detected along certain passes. Ensure daytime transit.",
    "Moderate": "MODERATE ADVISORY for {date}: Highway is generally passable. Drive cautiously near water crossings and culverts.",
    "Low": "LOW RISK CONDITIONS for {date}: Low landslide hazard modeled across the corridor. Proceed with caution. Low risk does not mean safe.",
    "forecast_prefix": "FORECAST NOTICE for {date}: Target travel date is beyond the 48-hour rainfall forecast window. Risk scores reflect static terrain susceptibility only. ",
}

ROUTE_ADVISORIES_HI = {
    "closure": "आधिकारिक मार्ग बंद चेतावनी: {segment} पर मार्ग बंद है। इस क्षेत्र में यात्रा से बचें।",  # NEEDS NATIVE REVIEW
    "Very High": "गंभीर चेतावनी ({date}): मार्ग पर तीव्र ढलान विफलता और गिरते पत्थरों का अत्यधिक खतरा। बीआरओ (BRO) की सूचनाएं जांचें।",  # NEEDS NATIVE REVIEW
    "High": "उच्च जोखिम चेतावनी ({date}): मार्ग पर भूस्खलन का महत्वपूर्ण जोखिम। केवल दिन के समय यात्रा करें और सतर्क रहें।",  # NEEDS NATIVE REVIEW
    "Moderate": "मध्यम सलाह ({date}): राष्ट्रीय राजमार्ग सामान्यतः खुला है। जलभराव और मोड़ों पर सावधानी से वाहन चलाएं।",  # NEEDS NATIVE REVIEW
    "Low": "कम जोखिम स्थिति ({date}): संपूर्ण मार्ग पर कम भूस्खलन जोखिम आंका गया। सावधानी बरतें। कम जोखिम का अर्थ सुरक्षित नहीं है।",  # NEEDS NATIVE REVIEW
    "forecast_prefix": "पूर्वानुमान सूचना ({date}): यात्रा की तिथि 48 घंटे के मौसम पूर्वानुमान से आगे है। जोखिम केवल भूभाग की स्थिरता पर आधारित है। ",  # NEEDS NATIVE REVIEW
}


def build_route_advisory(
    date: str,
    overall_max_level: str,
    closed_seg_name: Optional[str] = None,
    is_beyond_tomorrow: bool = False,
    lang: str = "en"
) -> str:
    """Builds the comprehensive route travel advisory text in the requested language."""
    if lang == "hi":
        table = ROUTE_ADVISORIES_HI
        seg_display = transliterate_town(closed_seg_name, lang="hi") if closed_seg_name else ""
    else:
        table = ROUTE_ADVISORIES_EN
        seg_display = closed_seg_name or ""

    prefix = table["forecast_prefix"].format(date=date) if is_beyond_tomorrow else ""

    if closed_seg_name:
        body = table["closure"].format(segment=seg_display)
    elif overall_max_level in table:
        body = table[overall_max_level].format(date=date)
    else:
        body = table["Low"].format(date=date)

    return f"{prefix}{body}".strip()


# --- 7. Subscriber Alert Message Templates ---

def build_subscriber_alert_message(
    segment_name: str,
    risk_level: str,
    rain_mm: Optional[float] = None,
    main_driver: Optional[str] = None,
    lang: str = "en"
) -> str:
    """Builds short, calm, non-alarmist alert text for subscribers."""
    if lang == "hi":
        seg_hi = transliterate_town(segment_name, lang="hi")
        driver_hi = localize_main_driver(main_driver, lang="hi")
        driver_clause = f" मुख्य कारक: {driver_hi}।" if driver_hi else ""  # NEEDS NATIVE REVIEW
        rain_clause = f" (3 दिवसीय वर्षा: {rain_mm:.1f} मिमी)" if rain_mm is not None else ""  # NEEDS NATIVE REVIEW

        if risk_level in ("Very High", "High"):
            return (  # NEEDS NATIVE REVIEW
                f"उच्च चेतावनी - {seg_hi}: भूगर्भीय अस्थिरता एवं सक्रिय चट्टान गिरने का खतरा{rain_clause}।{driver_clause} "
                "अत्यधिक सावधानी बरतें या अद्यतन तक यात्रा टालें।"
            )
        elif risk_level == "Moderate":
            return (  # NEEDS NATIVE REVIEW
                f"मार्ग सलाह - {seg_hi}: मध्यम ढलान नमी और फिसलन भरी सड़क स्थिति{rain_clause}।{driver_clause} "
                "मोड़ों पर गति सीमा का पालन करें।"
            )
        return f"सामान्य सूचना - {seg_hi}: मार्ग पर स्थिति सामान्य है।"  # NEEDS NATIVE REVIEW

    # English default:
    driver_clause = f" Primary factor: {main_driver}." if main_driver else ""
    rain_clause = f" (3-day rain: {rain_mm:.1f} mm)" if rain_mm is not None else ""

    if risk_level in ("Very High", "High"):
        return (
            f"HIGH ALERT on {segment_name}: Geological instability & active rockfall hazard{rain_clause}.{driver_clause} "
            "Road clearance readiness advised. Travel with extreme caution or check official closure advisories."
        )
    elif risk_level == "Moderate":
        return (
            f"ADVISORY on {segment_name}: Moderate slope wetness and slippery road conditions{rain_clause}.{driver_clause} "
            "Speed limits enforced near drainage outlets."
        )
    return f"NOTICE on {segment_name}: Road conditions normal."


# --- 8. Short Voice Alert Message Generator (Capped ~300 Chars) ---

def build_segment_voice_script(
    segment_id: str,
    segment_name: str,
    risk_level: str,
    rain_mm: Optional[float] = None,
    main_driver: Optional[str] = None,
    lang: str = "en"
) -> str:
    """Generates a concise voice alert script for an individual highway sector (<= 300 chars)."""
    if lang == "hi":
        seg_hi = SEGMENT_TRANSLITERATIONS_HI.get(segment_id, transliterate_town(segment_name, "hi"))
        lvl_hi = RISK_LEVEL_NAMES_HI.get(risk_level, risk_level)

        if risk_level in ("Very High", "High"):
            adv = "सक्रिय भूस्खलन खतरा। यात्रा से बचें।"  # NEEDS NATIVE REVIEW
        elif risk_level == "Moderate":
            adv = "सावधानी से वाहन चलाएं।"  # NEEDS NATIVE REVIEW
        else:
            adv = "कम जोखिम आंका गया। सावधानी बरतें।"  # NEEDS NATIVE REVIEW

        script = f"एनएच-7 बुलेटिन। {seg_hi}। जोखिम: {lvl_hi}। {adv} {DISCLAIMER_HI}"  # NEEDS NATIVE REVIEW
        return script[:300].strip()

    # English:
    lvl_en = risk_level.upper()
    if risk_level in ("Very High", "High"):
        adv = "Active rockfall hazard. Avoid travel."
    elif risk_level == "Moderate":
        adv = "Drive cautiously near steep cuts."
    else:
        adv = "Low risk modeled. Proceed with caution."

    script = f"NH-7 bulletin. {segment_name}. Risk: {lvl_en}. {adv} {DISCLAIMER_EN}"
    return script[:300].strip()


def build_route_voice_script(
    from_name: str,
    to_name: str,
    action: str,
    max_risk_level: str,
    max_seg_name: str,
    closed: bool = False,
    lang: str = "en"
) -> str:
    """Generates a concise voice alert script for a highway route journey (<= 300 chars)."""
    if lang == "hi":
        from_hi = transliterate_town(from_name, "hi")
        to_hi = transliterate_town(to_name, "hi")
        action_hi = ACTION_CODES_HI.get(action, action)
        lvl_hi = RISK_LEVEL_NAMES_HI.get(max_risk_level, max_risk_level)

        if closed:
            script = f"एनएच-7 {from_hi} से {to_hi}। मार्ग बंद है। यात्रा से बचें। {DISCLAIMER_HI}"  # NEEDS NATIVE REVIEW
        else:
            script = (  # NEEDS NATIVE REVIEW
                f"एनएच-7 {from_hi} से {to_hi}। सलाह: {action_hi}। "
                f"अधिकतम जोखिम: {lvl_hi}। {DISCLAIMER_HI}"
            )
        return script[:300].strip()

    # English:
    if closed:
        script = f"NH-7 {from_name} to {to_name}. Road closure active. Avoid travel. {DISCLAIMER_EN}"
    else:
        script = (
            f"NH-7 {from_name} to {to_name}. Action: {action}. "
            f"Max risk: {max_risk_level}. {DISCLAIMER_EN}"
        )
    return script[:300].strip()
