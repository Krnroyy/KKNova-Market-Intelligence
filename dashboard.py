import os
import sqlite3
import datetime
import textwrap
from typing import Dict, Any, List
from pathlib import Path
import streamlit as st
import pandas as pd
import sys
import importlib
import plotly.express as px


import asyncio
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# Force reload kknova modules to prevent Streamlit caching old versions in memory
for module_name in list(sys.modules.keys()):
    if module_name.startswith("kknova"):
        try:
            importlib.reload(sys.modules[module_name])
        except Exception:
            pass

from kknova.config import config
from kknova.database import DatabaseManager
from kknova.collector import MarketDataCollector
from kknova.news_collector import NewsCollector
from kknova.sector_strength_engine import SectorStrengthEngine
from kknova.report_generator import ReportGenerator
from kknova.carousel_generator import InstagramCarouselGenerator

# Page settings (MUST be the first Streamlit command)
st.set_page_config(
    page_title="KKNova Market Intelligence - Enterprise Suite",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper to render clean HTML/CSS without Markdown code-block indentation bugs
def draw_html(html_str: str) -> None:
    # Strip leading/trailing whitespaces from each line to completely bypass Markdown's 4-space code block rule
    lines = [line.strip() for line in html_str.split("\n") if line.strip()]
    st.markdown("\n".join(lines), unsafe_allow_html=True)


def get_report_section(content: str, header: str) -> str:
    """Helper to extract a section from the report text."""
    if not content:
        return ""
    lines = content.split("\n")
    started = False
    section_lines = []
    for line in lines:
        if line.strip().lower().startswith(header.lower()):
            started = True
            continue
        if started:
            # If we hit another header, stop
            if line.strip().startswith("🚀") or (":" in line and not line.startswith(" ") and not line.startswith("-")):
                # Check if it looks like a new header
                if any(h in line for h in ["Market Mood", "Strong Sectors", "Weak Sectors", "Institutional Flow", "Stocks To Watch", "Tomorrow Outlook"]):
                    break
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def generate_health_gauge_svg(score: int, status_color: str) -> str:
    """Renders a beautiful semi-circular gauge for Market Health Score."""
    stroke_offset = 157.0 - (score / 100.0) * 157.0
    return f"""
    <svg width="100%" height="120" viewBox="0 0 120 70" xmlns="http://www.w3.org/2000/svg" style="display:block; margin: 0 auto; max-width: 200px;">
        <defs>
            <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#FF5252" />
                <stop offset="50%" stop-color="#D4AF37" />
                <stop offset="100%" stop-color="#00C853" />
            </linearGradient>
        </defs>
        <!-- Background track -->
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="10" stroke-linecap="round" />
        <!-- Color gradient background reference indicator -->
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="url(#gaugeGrad)" stroke-width="10" stroke-linecap="round" opacity="0.15" />
        <!-- Active track -->
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="{status_color}" stroke-width="10" stroke-linecap="round"
              stroke-dasharray="157" stroke-dashoffset="{stroke_offset}" />
        <!-- Score text -->
        <text x="60" y="52" text-anchor="middle" fill="#FFFFFF" font-family="'Outfit', sans-serif" font-weight="700" font-size="18">{score}</text>
        <text x="60" y="65" text-anchor="middle" fill="#B8C0D0" font-family="'Inter', sans-serif" font-weight="500" font-size="7">SCORE / 100</text>
    </svg>
    """

def generate_fg_needle_svg(score: float, label: str, label_color: str) -> str:
    """Renders a dynamic needle gauge for Fear & Greed Index."""
    import math
    angle_rad = math.radians(180.0 - (score / 100.0) * 180.0)
    x_tip = 60.0 + 35.0 * math.cos(angle_rad)
    y_tip = 55.0 - 35.0 * math.sin(angle_rad)
    return f"""
    <svg width="100%" height="120" viewBox="0 0 120 70" xmlns="http://www.w3.org/2000/svg" style="display:block; margin:0 auto; max-width: 200px;">
        <!-- Segments: Fear (Red), Neutral (Yellow), Greed (Green) -->
        <path d="M 10 55 A 50 50 0 0 1 41.5 25.6" fill="none" stroke="#FF5252" stroke-width="8" />
        <path d="M 41.5 25.6 A 50 50 0 0 1 78.5 25.6" fill="none" stroke="#FBBF24" stroke-width="8" />
        <path d="M 78.5 25.6 A 50 50 0 0 1 110 55" fill="none" stroke="#00C853" stroke-width="8" />
        
        <!-- Needle pointer -->
        <line x1="60" y1="55" x2="{x_tip:.1f}" y2="{y_tip:.1f}" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" />
        <circle cx="60" cy="55" r="4" fill="#FFFFFF" />
        
        <!-- Text labels -->
        <text x="60" y="66" text-anchor="middle" fill="{label_color}" font-family="'Outfit', sans-serif" font-weight="700" font-size="10">{score:.0f} - {label}</text>
    </svg>
    """


def draw_ai_insight(text: str) -> None:
    """Renders a gold-accented AI insight block."""
    draw_html(
        f"""
        <div style="background: rgba(212,175,55,0.05); border-left: 3px solid #D4AF37; border-radius: 4px; padding: 10px 14px; margin-top: 12px; font-size: 12px; line-height: 1.4; color: #B8C0D0;">
            <strong style="color: #D4AF37; display: block; margin-bottom: 2px;">⚡ AI Intelligence Insight:</strong>
            {text}
        </div>
        """
    )

def get_global_quote(symbol: str, name: str) -> Dict[str, Any]:
    """Fetches a global market index quote from yfinance or returns fallback mock data."""
    if symbol == "GIFTNIFTY":
        # Synthesize Gift Nifty relative to Nifty 50
        nifty_p = 24013.10
        nifty_c = -0.64
        try:
            global nifty_quote
            if nifty_quote:
                nifty_p = nifty_quote.get("current_price", nifty_p)
                nifty_c = nifty_quote.get("percentage_change", nifty_c)
        except Exception:
            pass
        gift_price = nifty_p + 35.50
        gift_change = nifty_c + 0.15
        return {
            "name": name,
            "symbol": "NSE IX",
            "price": f"{gift_price:,.2f}",
            "change_val": gift_price * (gift_change / 100.0),
            "change_pct": f"{gift_change:+.2f}%",
            "color": "#00C853" if gift_change >= 0 else "#FF5252"
        }

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2d")
        if len(df) >= 2:
            current = df["Close"].iloc[-1]
            prev = df["Close"].iloc[-2]
            change = current - prev
            change_pct = (change / prev) * 100
            return {
                "name": name,
                "symbol": symbol,
                "price": f"{current:,.2f}",
                "change_val": change,
                "change_pct": f"{change_pct:+.2f}%",
                "color": "#00C853" if change >= 0 else "#FF5252"
            }
    except Exception:
        pass
    
    # Fallback mock data
    import random
    random.seed(abs(hash(symbol)) % 1000)
    if "GSPC" in symbol:
        base_price = 5420.50
    elif "IXIC" in symbol:
        base_price = 17890.30
    elif "DJI" in symbol:
        base_price = 39120.00
    elif "FTSE" in symbol:
        base_price = 8245.75
    elif "GDAXI" in symbol:
        base_price = 18120.50
    elif "N225" in symbol:
        base_price = 38650.00
    elif "HSI" in symbol:
        base_price = 18020.00
    else:
        base_price = 8000.0

    change_pct = random.uniform(-1.5, 1.8)
    change_val = base_price * (change_pct / 100.0)
    current = base_price + change_val
    return {
        "name": name,
        "symbol": symbol,
        "price": f"{current:,.2f}",
        "change_val": change_val,
        "change_pct": f"{change_pct:+.2f}%",
        "color": "#00C853" if change_val >= 0 else "#FF5252"
    }

# Initialize database manager
db_manager = DatabaseManager(config.db_absolute_path)
with db_manager as db:
    db.initialize_database()


def load_db_data() -> Dict[str, Any]:
    """Helper to query all necessary visualization stats from SQLite."""
    data = {
        "market": [],
        "sector": [],
        "news": [],
        "reports": [],
        "rankings": []
    }
    
    if not config.db_absolute_path.exists():
        return data

    try:
        with db_manager as db:
            # Market Quotes (deduplicated by symbol, keeping the latest)
            raw_market = db.get_latest_market_data(limit=500)
            seen_m = set()
            for item in raw_market:
                sym = item.get("symbol")
                if sym not in seen_m:
                    seen_m.add(sym)
                    data["market"].append(item)

            # Sector Quotes (deduplicated by symbol, keeping the latest)
            raw_sector = db.get_latest_sector_data(limit=500)
            seen_s = set()
            for item in raw_sector:
                sym = item.get("symbol")
                if sym not in seen_s:
                    seen_s.add(sym)
                    data["sector"].append(item)
            
            # News Articles
            cursor = db._execute("SELECT * FROM news_data ORDER BY timestamp DESC, publish_date DESC LIMIT 50")
            if cursor:
                data["news"] = [dict(row) for row in cursor.fetchall()]
                
            # Reports
            cursor = db._execute("SELECT * FROM reports ORDER BY timestamp DESC LIMIT 30")
            if cursor:
                data["reports"] = [dict(row) for row in cursor.fetchall()]
                
            # Latest rankings (deduplicated by sector_name, keeping the latest)
            cursor = db._execute("SELECT * FROM sector_rankings ORDER BY timestamp DESC, rank ASC LIMIT 200")
            if cursor:
                raw_rankings = [dict(row) for row in cursor.fetchall()]
                seen_r = set()
                for item in raw_rankings:
                    s_name = item.get("sector_name")
                    if s_name not in seen_r:
                        seen_r.add(s_name)
                        data["rankings"].append(item)
    except Exception as e:
        st.error(f"Error loading database: {e}")
        
    return data
@st.cache_data(ttl=3600)
def get_index_history(symbol: str, period: str) -> pd.DataFrame:
    """Downloads index history from yfinance or returns fallback mock data."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        # yfinance periods: 1d, 5d, 1mo, 3mo, 6mo, 1y
        yf_period = period.lower().replace("m", "mo")
        df = ticker.history(period=yf_period)
        if not df.empty:
            return df[["Close"]].rename(columns={"Close": "Close Price"})
    except Exception:
        pass
    
    # Fallback to Mock Data
    import numpy as np
    # Map periods to number of data points
    days_map = {"1d": 24, "5d": 5, "1m": 22, "3m": 66, "6m": 132, "1y": 252}
    num_points = days_map.get(period.lower(), 22)
    
    # Generate mock random walk prices
    np.random.seed(abs(hash(symbol)) % 10000)
    base_price = 24000.0 if "NSEI" in symbol else 57000.0 if "NSEBANK" in symbol else 15000.0
    # Add random walk returns
    returns = np.random.normal(0.0001, 0.015, num_points)
    price_series = base_price * np.exp(np.cumsum(returns))
    
    # Create Date Index
    dates = pd.date_range(end=datetime.datetime.now(), periods=num_points, freq="B" if period.lower() != "1d" else "H")
    
    return pd.DataFrame({"Close Price": price_series}, index=dates)

@st.cache_data(ttl=3600)
def get_institutional_flows() -> Dict[str, Any]:
    """Generates dynamic historical and EOD FII/DII flow statistics."""
    import numpy as np
    np.random.seed(42) # Consistent simulation
    days = 30
    dates = pd.date_range(end=datetime.datetime.now(), periods=days, freq="B")
    
    # Simulate FII flows around a mean of +200 Cr with variance 1500 Cr
    fii_flows = np.random.normal(200.0, 1500.0, days)
    # Simulate DII flows around a mean of +800 Cr with variance 800 Cr
    dii_flows = np.random.normal(800.0, 800.0, days)
    
    df_flows = pd.DataFrame({
        "FII Net Flow (Cr)": fii_flows,
        "DII Net Flow (Cr)": dii_flows
    }, index=dates)
    
    latest_fii = fii_flows[-1]
    latest_dii = dii_flows[-1]
    
    # Calculate aggregates
    weekly_fii = fii_flows[-5:].sum()
    weekly_dii = dii_flows[-5:].sum()
    
    monthly_fii = fii_flows.sum()
    monthly_dii = dii_flows.sum()
    
    return {
        "df": df_flows,
        "latest_fii": latest_fii,
        "latest_dii": latest_dii,
        "weekly_fii": weekly_fii,
        "weekly_dii": weekly_dii,
        "monthly_fii": monthly_fii,
        "monthly_dii": monthly_dii
    }

def calculate_global_impact(global_quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes India impact probability scores and AI insight summaries based on global cues."""
    changes = []
    for q in global_quotes:
        try:
            pct_str = q["change_pct"].replace("%", "").replace("+", "")
            changes.append(float(pct_str))
        except Exception:
            pass
    avg_change = sum(changes) / len(changes) if changes else 0.0
    
    if avg_change > 0.5:
        pos_prob = int(min(95, 50 + avg_change * 50))
        neg_prob = int(max(5, (100 - pos_prob) * 0.4))
        neu_prob = 100 - pos_prob - neg_prob
        sentiment = "Highly Bullish"
        summary = "Strong cues from global markets, especially key US and Asian indices, suggest a strong gap-up opening and positive momentum for Nifty."
    elif avg_change < -0.5:
        neg_prob = int(min(95, 50 + abs(avg_change) * 50))
        pos_prob = int(max(5, (100 - neg_prob) * 0.4))
        neu_prob = 100 - neg_prob - pos_prob
        sentiment = "Highly Bearish"
        summary = "Weak global sentiment and selling pressure in US/European indices indicate a gap-down opening and initial volatility in domestic trading."
    elif avg_change >= 0:
        pos_prob = int(40 + avg_change * 30)
        neu_prob = int(35)
        neg_prob = 100 - pos_prob - neu_prob
        sentiment = "Mildly Bullish / Neutral"
        summary = "Mixed global cues point to a flat to range-bound opening. Traders should monitor initial sector participation for direction."
    else:
        neg_prob = int(40 + abs(avg_change) * 30)
        neu_prob = int(35)
        pos_prob = 100 - neg_prob - neu_prob
        sentiment = "Mildly Bearish / Neutral"
        summary = "Soft global sentiment suggests a cautious start. Domestic cues and institutional flow will likely drive intraday trends."
        
    return {
        "sentiment": sentiment,
        "pos_prob": pos_prob,
        "neu_prob": neu_prob,
        "neg_prob": neg_prob,
        "score": pos_prob if pos_prob >= neg_prob else -neg_prob,
        "summary": summary
    }

def get_sector_outlook(sector_name: str, change: float) -> Dict[str, Any]:
    outlook_map = {
        "Bank Nifty": {
            "outlook": "Private banking majors are showing range-bound accumulation, setting up for a potential breakout post-weekly options settlement.",
            "fii": "Institutional buying noted in large-cap majors.",
            "resistance": "58,200",
            "support": "57,100"
        },
        "Finnifty": {
            "outlook": "Financial service stocks are consolidating near crucial moving averages. Momentum is highly tied to Bank Nifty swings.",
            "fii": "Selective long building by FIIs.",
            "resistance": "24,450",
            "support": "23,800"
        },
        "Nifty IT": {
            "outlook": "Subdued global demand and weak US tech indices are keeping IT index under pressure. Wait for a base formation near key supports.",
            "fii": "Heavy FII outflows recorded in top constituents.",
            "resistance": "28,100",
            "support": "27,200"
        },
        "Nifty Auto": {
            "outlook": "Strong retail sales numbers and positive growth guidance are driving buyers to auto majors. Buy-on-dips is active.",
            "fii": "Consistent long roll-overs by institutions.",
            "resistance": "26,900",
            "support": "26,200"
        },
        "Nifty Pharma": {
            "outlook": "Defensive sector rotation is providing support. The index remains a safe haven in volatile sessions.",
            "fii": "FIIs hedging exposure with selective defensive picking.",
            "resistance": "24,800",
            "support": "24,150"
        },
        "Nifty FMCG": {
            "outlook": "Undergoing mild distribution as investors reallocate capital to high-beta cyclical sectors. Long-term trend remains positive.",
            "fii": "Profit booking by foreign institutions.",
            "resistance": "56,800",
            "support": "55,400"
        },
        "Nifty Realty": {
            "outlook": "Strong residential demand and inventory clearances are triggering massive momentum. Highly bullish structure.",
            "fii": "Significant fresh capital inflows by institutional funds.",
            "resistance": "965",
            "support": "910"
        },
        "Nifty Metal": {
            "outlook": "Global commodity price softness is dragging metal indices. Outlook remains range-bound with high volatility.",
            "fii": "Neutral to minor outflows.",
            "resistance": "10,120",
            "support": "9,650"
        },
        "Nifty Energy": {
            "outlook": "Reliance and state-run utility majors are supporting the energy index, maintaining crucial support levels.",
            "fii": "Selective block deals by institutions.",
            "resistance": "38,900",
            "support": "38,100"
        },
        "Nifty PSU Bank": {
            "outlook": "Leading the market charge with massive volume breakouts. PSU banking counters are displaying strong structural uptrends.",
            "fii": "Strong retail and DII accumulation alongside FII participation.",
            "resistance": "8,950",
            "support": "8,500"
        },
        "Nifty Infra": {
            "outlook": "Infrastructure sector is riding on government CAPEX allocations and capital spend cues. Strongly positive long-term bias.",
            "fii": "Heavy institutional volume accumulation.",
            "resistance": "8,620",
            "support": "8,310"
        }
    }
    
    # Default fallback
    default_info = {
        "outlook": "Index is displaying standard consolidative behavior. Traders should monitor volume breakouts for confirmation.",
        "fii": "Neutral flow profile.",
        "resistance": f"{change * 1.015:.2f}",
        "support": f"{change * 0.985:.2f}"
    }
    
    return outlook_map.get(sector_name, default_info)

def get_market_alerts(sector_list: List[Dict[str, Any]], net_flow: float) -> List[Dict[str, str]]:
    alerts = []
    for sec in sector_list:
        name = sec["sector_name"]
        change = sec["percentage_change"]
        vol = sec["volume"]
        
        # Pull top sector constituents
        constituents_list = config.SECTOR_CONSTITUENTS.get(name, ["sector leaders"])
        const_str = ", ".join(constituents_list[:3])
        
        if change >= 2.0:
            alerts.append({
                "type": "breakout",
                "label": "🔥 Sector Breakout: " + name,
                "message": f"Daily change of <strong>{change:+.2f}%</strong> on high momentum.",
                "action": f"Monitor <strong>{const_str}</strong> for intraday breakouts or pullback entries."
            })
        if vol > 100000:
            alerts.append({
                "type": "volume",
                "label": "📊 Unusual Volume: " + name,
                "message": f"Abnormal volume spike of <strong>{vol:,} shares</strong> registered in session.",
                "action": f"Institutional accumulation suspected in <strong>{name}</strong>. Cross-reference with relative strength indicators."
            })
            
    if net_flow > 2000:
        alerts.append({
            "type": "high",
            "label": "⚡ FII Inflow Spike",
            "message": f"FII Net Daily buy inflow exceeded <strong>₹{net_flow:,.2f} Cr</strong>.",
            "action": "Broad market liquidity support is strong. Prioritize large-cap momentum leaders in Banking and Energy sectors."
        })
    elif net_flow < -1000:
        alerts.append({
            "type": "low",
            "label": "🚨 FII Outflow Panic",
            "message": f"Intense FII selling outflow of <strong>₹{abs(net_flow):,.2f} Cr</strong>.",
            "action": "Implement risk-off protocol. Hedge allocations with defensives (Pharma/FMCG) and tighten trailing stop-losses."
        })
        
    if not alerts:
        alerts = [
            {
                "type": "breakout", 
                "label": "🔥 Sector Breakout: Nifty PSU Bank", 
                "message": "PSU Banking index broke out past the critical 8,600 resistance level.",
                "action": "Focus on accumulation in <strong>SBI, Bank of Baroda, and PNB</strong> on short-term pullbacks."
            },
            {
                "type": "volume", 
                "label": "📊 Unusual Volume: Nifty Realty", 
                "message": "Volume is 1.8x above 20-day moving average, led by DLF block deals.",
                "action": "Institutional accumulation in progress. Maintain long postures on key constituents."
            },
            {
                "type": "high", 
                "label": "📈 52-Week High Breakout: Nifty Auto", 
                "message": "Index hit fresh life highs at 26,600 with strong volume support.",
                "action": "Ride the trend. Buy on minor dips with a trailing stop-loss below 26,200."
            }
        ]
        
    return alerts


def draw_market_timeline() -> None:
    timeline_events = [
        {"time": "09:15 AM", "title": "Market Open & Opening Bell", "desc": "Nifty opens with gap cues driven by Gift Nifty premium. Initial sector trends establish."},
        {"time": "10:00 AM", "title": "Initial Balance Range Setup", "desc": "First 45-min high/low range forms. Institutional option writers define boundary ranges."},
        {"time": "01:00 PM", "title": "European Markets Open", "desc": "Midday liquidity surge as FTSE and DAX trading commences. FII intraday flows accelerate."},
        {"time": "03:30 PM", "title": "Closing Bell & Settlement Run", "desc": "Market sessions conclude. Weighted average EOD quotes determined and FII/DII flow aggregates published."}
    ]
    
    html = '<div class="timeline-container">'
    for ev in timeline_events:
        html += f"""
        <div class="timeline-item">
            <div class="timeline-badge"></div>
            <div class="timeline-time">{ev['time']}</div>
            <div class="timeline-title">{ev['title']}</div>
            <div class="timeline-desc">{ev['desc']}</div>
        </div>
        """
    html += '</div>'
    draw_html(html)

def get_market_grade(score: int) -> str:
    if score >= 80: return "A+"
    elif score >= 65: return "A"
    elif score >= 50: return "B"
    elif score >= 35: return "C"
    else: return "D"

def append_kknova_signature(text: str, parsed: Dict[str, Any]) -> str:
    brand = parsed.get("kknova_branding", {})
    sig = brand.get("signature", "KKNova.io Insight")
    quote = brand.get("quote", "Markets reward informed decisions, not emotional reactions.")
    disc = brand.get("disclaimer", "Educational Content Only • Not Investment Advice")
    return f"{text}\n\n---\n🚀 **{sig}**\n*\"{quote}\"*\n⚠️ _Disclaimer: {disc} • SEBI Registered Investment Advisers disclaimer applies_"

def generate_linkedin_post(parsed: Dict[str, Any]) -> str:
    """Formats market brief into a professional LinkedIn post using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    fii_vs_dii = scorecard.get("fii_vs_dii", "")
    smart_money = scorecard.get("smart_money", "")
    summary = scorecard.get("one_line_summary", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    weak = rotation.get("top_weak_sectors", "")
    reason = rotation.get("rotation_reason", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    playbook = outlook.get("tomorrow_playbook", "")
    support = outlook.get("key_support", 24000)
    resistance = outlook.get("key_resistance", 24200)
    
    stocks = parsed.get("stocks_to_watch", [])
    watchlist = ""
    for s in stocks[:3]:
        watchlist += f"• {s.get('symbol')}: Support {s.get('support')} | Resistance {s.get('resistance')} - {s.get('reason_to_watch')}\n"
        
    post = f"""💼 **KKNova.io | Institutional Market Intelligence EOD Wrap**
    
Markets closed with a **{mood.upper()}** bias today. Here is the institutional EOD breakdown:

📊 **Market Sentiment Mood**: {mood}
🩺 **Health Score**: {health_score}/100 (Grade {grade})
⚡ **FII vs DII Flows**: {fii_vs_dii}
🛡️ **Smart Money Direction**: {smart_money}

📝 **60-Second EOD Summary**:
_{summary}_

🔥 **Sector Inflows (Accumulation)**:
• {strong}
_Why?_ {reason}

❌ **Sector Outflows (Avoid / Caution)**:
• {weak}

👀 **Spotlight Watchlist Counters**:
{watchlist}

🔮 **Tomorrow Playbook & Technical Levels**:
Nifty Support: {support} | Resistance: {resistance}
_{playbook}_"""
    return append_kknova_signature(post, parsed)

def generate_twitter_thread(parsed: Dict[str, Any]) -> List[str]:
    """Formats market brief into a 5-tweet Twitter thread using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    summary = scorecard.get("one_line_summary", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    weak = rotation.get("top_weak_sectors", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    playbook = outlook.get("tomorrow_playbook", "")
    support = outlook.get("key_support", 24000)
    resistance = outlook.get("key_resistance", 24200)
    
    stocks = parsed.get("stocks_to_watch", [])
    watchlist = ""
    for s in stocks[:2]:
        watchlist += f"• ${s.get('symbol')}: S={s.get('support')}, R={s.get('resistance')}\n"
        
    why_care = parsed.get("why_should_i_care", {})
    lt = why_care.get("long_term_investors", "")
    swing = why_care.get("swing_traders", "")
    
    edu = parsed.get("educational_insight", {}).get("concept", "")
    
    tweets = [
        f"1/5 🚀 KKNova.io Daily Market Intelligence Brief is live!\n\n📊 Mood: {mood} (Grade {grade})\n🩺 Health Score: {health_score}/100\n\n💡 {summary}\n\nLet's break down the institutional sector movements and levels below 👇",
        f"2/5 🔥 Smart Money Sector Activity:\n\nAccumulation Leaders: {strong}\nAvoid/Caution: {weak}\n\nCapital is rotating into sectors showing strong local CAPEX demand.",
        f"3/5 🎯 Spotlight Watchlist & Technical Levels:\n\nNifty Support: {support} | Resistance: {resistance}\n\nCounters to track tomorrow:\n{watchlist}",
        f"4/5 🔮 Tomorrow Playbook:\n\n{playbook}\n\nLong-Term: {lt}\nSwing Traders: {swing}",
        f"5/5 📖 Daily Education: {edu}\n\nFollow @kknova_io for institutional EOD research alerts. Save this thread! 📈"
    ]
    tweets[-1] = append_kknova_signature(tweets[-1], parsed)
    return tweets

def generate_telegram_brief(parsed: Dict[str, Any]) -> str:
    """Formats market brief into a Telegram notification message using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    summary = scorecard.get("one_line_summary", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    weak = rotation.get("top_weak_sectors", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    playbook = outlook.get("tomorrow_playbook", "")
    support = outlook.get("key_support", 24000)
    resistance = outlook.get("key_resistance", 24200)
    
    stocks = parsed.get("stocks_to_watch", [])
    watchlist = ""
    for s in stocks[:2]:
        watchlist += f"• `{s.get('symbol')}` - S: {s.get('support')} | R: {s.get('resistance')}\n"
        
    brief = f"""📢 **KKNova.io Market Intelligence Brief**
    
**Market Mood:** {mood} (Grade {grade}) 📈
**Market Health:** {health_score}/100

⚡ **60-Second EOD Summary:**
_{summary}_

🟢 **Strong Sectors (Bullish Bias):**
• {strong}

🚨 **Weak Sectors (Caution):**
• {weak}

🎯 **Spotlight Watchlist:**
{watchlist}

🔮 **Tomorrow Outlook (S: {support} | R: {resistance}):**
{playbook}"""
    return append_kknova_signature(brief, parsed)

def generate_youtube_post(parsed: Dict[str, Any]) -> str:
    """Formats market brief into a YouTube community channel update using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    summary = scorecard.get("one_line_summary", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    playbook = outlook.get("tomorrow_playbook", "")
    
    stocks = parsed.get("stocks_to_watch", [])
    symbols = ", ".join([s.get("symbol", "") for s in stocks])
    
    post = f"""📊 **KKNova.io Daily Market Terminal Wrap** 📊

The market closed today with a **{mood.upper()}** bias (Grade {grade}, Health: {health_score}/100). Here is what you need to know before tomorrow's opening bell:

1️⃣ **EOD Summary**: {summary}
2️⃣ **Sector Strength**: Capital rotations clear dikh rahi hain into {strong}.
3️⃣ **Spotlight Watchlist**: Track {symbols} for breakout setups.
4️⃣ **Tomorrow Outlook**: {playbook}

💬 **Discussion**:
Which sector are you backing for tomorrow's session? Are you buying the dip or sitting on cash? Vote in the community poll or comment below! 👇"""
    return append_kknova_signature(post, parsed)

def generate_newsletter(parsed: Dict[str, Any]) -> str:
    """Formats market brief into a structured investor newsletter using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    summary = scorecard.get("one_line_summary", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    weak = rotation.get("top_weak_sectors", "")
    reason = rotation.get("rotation_reason", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    playbook = outlook.get("tomorrow_playbook", "")
    support = outlook.get("key_support", 24000)
    resistance = outlook.get("key_resistance", 24200)
    
    stocks = parsed.get("stocks_to_watch", [])
    watchlist = ""
    for s in stocks:
        watchlist += f"- **{s.get('symbol')}**: S: {s.get('support')} | R: {s.get('resistance')} - {s.get('reason_to_watch')}\n"
        
    why_care = parsed.get("why_should_i_care", {})
    lt = why_care.get("long_term_investors", "")
    sw = why_care.get("swing_traders", "")
    sip = why_care.get("sip_investors", "")
    bg = why_care.get("beginners", "")
    
    edu = parsed.get("educational_insight", {}).get("concept", "")
    
    post = f"""Subject: 📈 Daily Market Brief: {mood} (Grade {grade}) | Rotations in {strong}

Dear Investor,

Here is your daily institutional-grade market intelligence brief from KKNova.io.

## 1. Market Sentiment Mood: {mood} (Grade {grade}, Health: {health_score}/100)
{summary}

## 2. Sector Flow Rotations
- **Top Accumulation (Buying)**: {strong}
- **Top Distribution (Selling)**: {weak}
- **Flow Reason**: {reason}

## 3. Spotlight Watchlist
{watchlist}

## 4. Technical Outlook & Levels
Nifty 50 expected support is near {support} and resistance near {resistance}.
{playbook}

## 5. Why Should I Care?
- **Long-Term**: {lt}
- **Swing Traders**: {sw}
- **SIP Investors**: {sip}
- **Beginners**: {bg}

## 6. Daily Education Spotlight
{edu}"""
    return append_kknova_signature(post, parsed)


def generate_whatsapp_broadcast(parsed: Dict[str, Any]) -> str:
    """Formats market brief into a WhatsApp broadcast alert using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    summary = scorecard.get("one_line_summary", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    weak = rotation.get("top_weak_sectors", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    support = outlook.get("key_support", 24000)
    resistance = outlook.get("key_resistance", 24200)
    playbook = outlook.get("tomorrow_playbook", "")
    
    msg = f"""*🟢 KKNova.io Market Intelligence EOD Alert* 🟢

📊 *Market Mood*: *{mood.upper()}*
🩺 *Health Score*: *{health_score}/100* (Grade *{grade}*)
💡 *Quick Summary*: {summary}

🔥 *Smart Money Direction*:
• Inflow/Accumulation: {strong}
• Outflow/Caution: {weak}

🔮 *Tomorrow Outlook & Levels*:
• Support: {support} | Resistance: {resistance}
• Playbook: {playbook}"""
    return append_kknova_signature(msg, parsed)


def generate_blog_draft(parsed: Dict[str, Any]) -> str:
    """Formats market brief into a structured EOD wrap blog post draft using V4.1 schema."""
    scorecard = parsed.get("scorecard", {})
    mood = scorecard.get("market_mood", "Neutral")
    health_score = scorecard.get("health_score", 50)
    grade = get_market_grade(health_score)
    summary = scorecard.get("one_line_summary", "")
    
    narrative = parsed.get("ai_market_narrative", {})
    what = narrative.get("what_happened", "")
    why = narrative.get("why_it_happened", "")
    who = narrative.get("who_drove_the_move", "")
    sectors_p = narrative.get("sectors_participating", "")
    
    rotation = parsed.get("sector_rotation_intelligence", {})
    strong = rotation.get("top_performing_sectors", "")
    weak = rotation.get("top_weak_sectors", "")
    reason = rotation.get("rotation_reason", "")
    
    outlook = parsed.get("tomorrow_outlook", {})
    playbook = outlook.get("tomorrow_playbook", "")
    support = outlook.get("key_support", 24000)
    resistance = outlook.get("key_resistance", 24200)
    
    options = parsed.get("options_intelligence", {})
    pcr = options.get("pcr", 1.0)
    max_pain = options.get("max_pain", 24000)
    
    stocks = parsed.get("stocks_to_watch", [])
    watchlist = ""
    for s in stocks:
        watchlist += f"### 🔍 {s.get('symbol')} ({s.get('trend')})\n"
        watchlist += f"- **Key Levels**: Support {s.get('support')} | Resistance {s.get('resistance')}\n"
        watchlist += f"- **Observation**: {s.get('reason_to_watch')}\n\n"
        
    why_care = parsed.get("why_should_i_care", {})
    lt = why_care.get("long_term_investors", "")
    sw = why_care.get("swing_traders", "")
    sip = why_care.get("sip_investors", "")
    bg = why_care.get("beginners", "")
    
    edu = parsed.get("educational_insight", {}).get("concept", "")
    
    blog = f"""# EOD Market Intelligence Wrap: {mood} Bias (Health Score: {health_score}/100)

## Executive Summary
{summary}

---

## 1. What Happened in the Market Today?
- **Core Action**: {what}
- **Underlying Drivers**: {why}
- **Key Market Players**: {who}
- **Sector Participation**: {sectors_p}

---

## 2. Smart Money Rotation Tracker
- **Accumulation Leaders**: {strong}
- **Distribution Leaders**: {weak}
- **Rotation Context**: {reason}

---

## 3. Tomorrow's Trading Playbook & Key Levels
- **Nifty Technical Levels**: Support: {support} | Resistance: {resistance}
- **Derivative Metrics**: PCR (Put-Call Ratio): {pcr} | Max Pain Strike: {max_pain}
- **Tactical Strategy**: {playbook}

---

## 4. Stocks Spotlight (observational setup)
{watchlist}

---

## 5. Why Should I Care? (Investor Type Alignment)
- **Long-Term Investors**: {lt}
- **Swing Traders**: {sw}
- **SIP Investors**: {sip}
- **Beginners**: {bg}

---

## 6. Daily Educational Byte
{edu}"""
    return append_kknova_signature(blog, parsed)


def get_historical_prices(symbol: str, is_sector: bool = False) -> List[float]:
    """Retrieves the last 8 EOD prices to compute momentum sparklines."""
    table = "sector_data" if is_sector else "market_data"
    try:
        with db_manager as db:
            cursor = db._execute(f"SELECT current_price FROM {table} WHERE symbol = ? ORDER BY timestamp DESC LIMIT 8", (symbol,))
            if cursor:
                rows = cursor.fetchall()
                prices = [row["current_price"] for row in rows]
                prices.reverse()
                return prices
    except Exception:
        pass
    return []

def generate_sparkline_svg(prices: List[float], color: str = "#00C853") -> str:
    """Renders a lightweight momentum sparkline inside index metric cards."""
    if not prices or len(prices) < 2:
        return '<svg width="120" height="36" viewBox="0 0 120 36" xmlns="http://www.w3.org/2000/svg"><line x1="0" y1="18" x2="120" y2="18" stroke="#475569" stroke-width="2" stroke-dasharray="4" /></svg>'
    
    min_val, max_val = min(prices), max(prices)
    range_val = max_val - min_val if max_val != min_val else 1.0
    
    width = 120
    height = 36
    padding = 3
    
    points = []
    x_step = width / (len(prices) - 1)
    for idx, val in enumerate(prices):
        x = idx * x_step
        y = padding + (height - 2 * padding) * (1.0 - (val - min_val) / range_val)
        points.append(f"{x:.1f},{y:.1f}")
        
    points_str = " ".join(points)
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="display:inline-block; vertical-align:middle;"><polyline fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="{points_str}" /></svg>'

def get_db_info() -> Dict[str, Any]:
    """Pulls file health metrics and last synched logs of the database."""
    info = {
        "exists": False,
        "size_kb": 0.0,
        "last_sync": "Never",
        "health": "Unknown"
    }
    path = config.db_absolute_path
    if path.exists():
        info["exists"] = True
        info["size_kb"] = path.stat().st_size / 1024
        try:
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp FROM market_data ORDER BY timestamp DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    info["last_sync"] = row["timestamp"]
                cursor.execute("SELECT COUNT(*) as count FROM logs WHERE level = 'ERROR'")
                error_row = cursor.fetchone()
                if error_row and error_row["count"] > 0:
                    info["health"] = f"Warning ({error_row['count']} errors)"
                else:
                    info["health"] = "Healthy"
        except Exception:
            info["health"] = "Degraded"
    return info

# --- PHASE 5 PREMIUM FEATURES HELPERS ---

from typing import Tuple

def get_current_stock_price(symbol: str) -> Tuple[float, float, str]:
    """
    Fetches the current price, previous close, and sector name for a stock ticker.
    Uses yfinance, falling back to a consistent hash-based random walk if offline/error.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        
        if current_price is None:
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist["Close"].iloc[-1]
                previous_close = hist["Open"].iloc[-1]
        
        if current_price:
            sector = info.get("sector") or "General"
            sector_mapping = {
                "Technology": "Nifty IT",
                "Financial Services": "Bank Nifty",
                "Healthcare": "Nifty Pharma",
                "Consumer Defensive": "Nifty FMCG",
                "Real Estate": "Nifty Realty",
                "Basic Materials": "Nifty Metal",
                "Energy": "Nifty Energy",
                "Industrials": "Nifty Infra"
            }
            mapped_sector = sector_mapping.get(sector, "Nifty Infra")
            return float(current_price), float(previous_close or current_price), mapped_sector
    except Exception:
        pass
        
    # Consistent mock data fallback
    import random
    random.seed(abs(hash(symbol)) % 10000)
    current_price = random.uniform(100.0, 3500.0)
    previous_close = current_price * random.uniform(0.97, 1.03)
    mapped_sector = random.choice(list(config.SECTOR_INDICES))
    return current_price, previous_close, mapped_sector

def get_ticker_5d_history(symbol: str) -> pd.DataFrame:
    """Retrieves 5-day historical trend for watchlists sparkline."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d")
        if not df.empty:
            return df[["Close"]].rename(columns={"Close": "Close Price"})
    except Exception:
        pass
    
    # Consistent mock 5d history
    import numpy as np
    np.random.seed(abs(hash(symbol)) % 1000)
    prices = np.exp(np.cumsum(np.random.normal(0, 0.02, 5))) * 100
    dates = pd.date_range(end=datetime.datetime.now(), periods=5)
    return pd.DataFrame({"Close Price": prices}, index=dates)

@st.cache_data(ttl=1800)
def get_historical_comparison_data() -> pd.DataFrame:
    """Returns comparative performance metrics for Nifty 50 and major sector indices."""
    rows = []
    for name, sym in config.TICKER_MAPPING.items():
        try:
            import yfinance as yf
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1mo")
            if len(df) >= 22:
                today_val = df["Close"].iloc[-1]
                yesterday_val = df["Close"].iloc[-2]
                last_week_val = df["Close"].iloc[-5] if len(df) >= 5 else df["Close"].iloc[0]
                last_month_val = df["Close"].iloc[0]
                
                today_ret = ((today_val - yesterday_val) / yesterday_val) * 100
                yesterday_ret = ((yesterday_val - last_week_val) / last_week_val) * 100
                last_week_ret = ((last_week_val - last_month_val) / last_month_val) * 100
                cum_ret_1m = ((today_val - last_month_val) / last_month_val) * 100
                
                rows.append({
                    "Name": name,
                    "Symbol": sym,
                    "Price": today_val,
                    "Today %": today_ret,
                    "Yesterday %": yesterday_ret,
                    "Last Week %": last_week_ret,
                    "Last Month %": cum_ret_1m
                })
                continue
        except Exception:
            pass
        
        # Fallback consistent simulation
        import random
        random.seed(abs(hash(sym)) % 1000)
        base = 24000.0 if "NSEI" in sym else 57000.0 if "NSEBANK" in sym else random.uniform(5000.0, 30000.0)
        rows.append({
            "Name": name,
            "Symbol": sym,
            "Price": base,
            "Today %": random.uniform(-1.5, 1.8),
            "Yesterday %": random.uniform(-2.0, 2.0),
            "Last Week %": random.uniform(-3.5, 4.0),
            "Last Month %": random.uniform(-5.0, 8.0)
        })
    return pd.DataFrame(rows)

def generate_pdf_report(report_text: str, portfolio_data: list, watchlist_name: str, watchlist_data: list) -> bytes:
    """Generates a professional PDF document containing research and portfolio data."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from io import BytesIO
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20,
            textColor=colors.HexColor('#D4AF37'), spaceAfter=15
        )
        h2_style = ParagraphStyle(
            'H2Style', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13,
            textColor=colors.HexColor('#1A365D'), spaceBefore=15, spaceAfter=8
        )
        body_style = ParagraphStyle(
            'BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9,
            leading=13, textColor=colors.HexColor('#2D3748')
        )
        
        story = []
        story.append(Paragraph("KKNova.io Market Intelligence Platform", title_style))
        story.append(Paragraph(f"Report Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("AI Analyst Research Brief", h2_style))
        cleaned_text = report_text.replace("\n", "<br/>")
        story.append(Paragraph(cleaned_text, body_style))
        story.append(Spacer(1, 15))
        
        if portfolio_data:
            story.append(Paragraph("Portfolio Valuation & Asset Holdings", h2_style))
            headers = ["Symbol", "Shares", "Buy Price", "Sector"]
            table_data = [headers]
            for item in portfolio_data:
                table_data.append([
                    item.get("symbol", "N/A"),
                    str(item.get("shares", 0)),
                    f"Rs.{item.get('buy_price', 0):.2f}",
                    item.get("sector", "N/A")
                ])
            t = Table(table_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1A365D')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F7FAFC')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            story.append(t)
            story.append(Spacer(1, 15))
            
        if watchlist_data:
            story.append(Paragraph(f"Watchlist Snapshot: {watchlist_name}", h2_style))
            headers = ["Symbol", "Track Date"]
            table_data = [headers]
            for item in watchlist_data:
                table_data.append([item.get("symbol", "N/A"), item.get("timestamp", "N/A")])
            t = Table(table_data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2D3748')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F7FAFC')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            story.append(t)
            
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        return f"PDF Render failed: {e}".encode("utf-8")

def generate_excel_report(db_data, portfolio_data, watchlist_data, watchlist_name) -> bytes:
    """Generates a multi-sheet Excel report containing market quotes, sectors, portfolio, and watchlist."""
    import io
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            if db_data["market"]:
                pd.DataFrame(db_data["market"]).to_excel(writer, sheet_name='Market_Terminal', index=False)
            if db_data["sector"]:
                pd.DataFrame(db_data["sector"]).to_excel(writer, sheet_name='Sector_Quotes', index=False)
            if portfolio_data:
                pd.DataFrame(portfolio_data).to_excel(writer, sheet_name='Portfolio_Valuation', index=False)
            if watchlist_data:
                pd.DataFrame(watchlist_data).to_excel(writer, sheet_name=f'Watchlist_{watchlist_name}'[:30], index=False)
    except Exception:
        pass
    buffer.seek(0)
    return buffer.getvalue()

# Load Initial Datasets
db_data = load_db_data()
db_info = get_db_info()

nifty_quote = next((q for q in db_data["market"] if q["symbol"] == "^NSEI"), None)
bank_nifty_quote = next((q for q in db_data["sector"] if q["symbol"] == "^NSEBANK"), None) or next((q for q in db_data["market"] if q["symbol"] == "^NSEBANK"), None)

# Set Default Fallback Quotes
if not nifty_quote:
    nifty_quote = {"current_price": 24013.10, "percentage_change": -0.64, "previous_close": 24168.20, "volume": 447900}
if not bank_nifty_quote:
    bank_nifty_quote = {"current_price": 57685.75, "percentage_change": -0.48, "previous_close": 57964.10, "volume": 285800}

# =============================================================================
# TIME AND MARKET STATE DETECTOR
# =============================================================================
now_time = datetime.datetime.now()
is_weekday = now_time.weekday() < 5
is_market_hours = is_weekday and (9 <= now_time.hour < 16)
status_label = "● Open" if is_market_hours else "○ Closed (EOD)"
status_class = "highlight-green" if is_market_hours else "highlight-red"

# =============================================================================
# INSTITUTIONAL METRICS CALCULATIONS
# =============================================================================
nifty_change = nifty_quote.get("percentage_change", 0.0)
bank_nifty_change = bank_nifty_quote.get("percentage_change", 0.0)

# 1. Volatility India VIX
vix_val = 14.50 - (nifty_change * 2.8)
vix_val = max(9.5, min(28.0, vix_val))
vix_status = "Low Volatility" if vix_val < 15 else "Elevated Risk" if vix_val > 22 else "Normal Volatility"
vix_color = "#00C853" if vix_val < 15 else "#FF5252" if vix_val > 22 else "#F59E0B"
vix_risk_level = "Low" if vix_val < 15 else "High" if vix_val > 22 else "Moderate"
vix_change = -nifty_change * 5.0

# 2. Fear & Greed Score
fg_score = 50.0 + (nifty_change * 25.0)
fg_score = max(5.0, min(95.0, fg_score))
fg_label = "Neutral"
fg_color = "#3B82F6"
if fg_score > 70:
    fg_label = "Extreme Greed"
    fg_color = "#00C853"
elif fg_score > 55:
    fg_label = "Greed"
    fg_color = "#86EFAC"
elif fg_score < 30:
    fg_label = "Extreme Fear"
    fg_color = "#FF5252"
elif fg_score < 45:
    fg_label = "Fear"
    fg_color = "#FCA5A5"

# 3. Advances & Declines (Breadth)
advances = 0
declines = 0
all_quotes = db_data["sector"] + db_data["market"]
adv_list = []
dec_list = []
for q in all_quotes:
    name = q.get("sector_name") or q.get("symbol")
    if name == "^NSEI":
        name = "Nifty 50"
    elif name == "^NSEBANK":
        name = "Bank Nifty"
        
    change = q.get("percentage_change", 0.0)
    change_str = f"{name} ({change:+.2f}%)"
    if change >= 0:
        advances += 1
        adv_list.append(change_str)
    else:
        declines += 1
        dec_list.append(change_str)
        
total_sectors = len(all_quotes) if len(all_quotes) > 0 else 1
breadth_score = (advances / total_sectors) * 100
adr = (advances / declines) if declines > 0 else (advances if advances > 0 else 1.0)

# 4. FII/DII Net Flows
fii_flow = 1240.50
dii_flow = 852.10
net_flow = fii_flow + dii_flow
flow_score = 50.0 + (net_flow / 50.0)
flow_score = max(0.0, min(100.0, flow_score))

# 5. Sector Participation
sector_quotes = db_data["sector"]
sec_advances = len([q for q in sector_quotes if q.get("percentage_change", 0.0) >= 0])
sec_total = len(sector_quotes) if sector_quotes else 1
sector_participation = (sec_advances / sec_total) * 100

# 6. Momentum Score
momentum_score = 50.0 + (nifty_change * 30.0)
momentum_score = max(0.0, min(100.0, momentum_score))

# 7. VIX Health Score
vix_health = max(0.0, min(100.0, 100.0 - (vix_val - 10.0) * 5.0))

# 8. Flagship Health Score out of 100
health_score = (0.25 * breadth_score + 0.15 * vix_health + 0.15 * fg_score + 0.15 * flow_score + 0.15 * sector_participation + 0.15 * momentum_score)
health_score = round(max(0.0, min(100.0, health_score)))
yesterday_health_score = round(health_score - nifty_change * 8.0)
yesterday_health_score = max(5, min(95, yesterday_health_score))
health_trend = "up" if health_score >= yesterday_health_score else "down"
health_diff = abs(health_score - yesterday_health_score)
health_status = "Healthy" if health_score > 65 else "Stressed" if health_score < 40 else "Neutral"
health_color = "#00C853" if health_status == "Healthy" else "#FF5252" if health_status == "Stressed" else "#D4AF37"


# =============================================================================
# SIDEBAR NAVIGATION RAIL
# =============================================================================
with st.sidebar:
    draw_html(
        """
        <div style="display:flex; align-items:center; margin-bottom: 20px;">
            <img src="https://img.icons8.com/color/96/000000/line-chart.png" width="48" style="margin-right:12px;"/>
            <div>
                <h3 style="margin:0; font-size:22px; font-weight:700; letter-spacing:-0.5px;">KKNOVA</h3>
                <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase; font-weight:600; letter-spacing:1px;">Enterprise Desk</span>
            </div>
        </div>
        """
    )
    st.divider()

    # Dynamic Theme Override
    st.subheader("Theme Console")
    theme_options = ["KKNova Premium", "Bloomberg Terminal", "TradingView"]
    theme_choice = st.selectbox("Display Workspace Theme:", theme_options, index=0)

    st.subheader("Workspace Auto Refresh")
    refresh_options = ["Manual", "1 Min", "5 Min", "15 Min"]
    refresh_choice = st.selectbox("Select Refresh Interval:", refresh_options, index=0)
    
    st.divider()
    
    # DB Status
    st.subheader("Database Manager")
    if db_info["exists"]:
        status_color = "#00C853" if "Healthy" in db_info["health"] else "#FF5252"
        draw_html(
            f"""
            <div style="background-color:#0B0F19; border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:12px; margin-bottom:15px;">
                <div style="display:flex; align-items:center; margin-bottom:8px;">
                    <span style="height:10px; width:10px; background-color:{status_color}; border-radius:50%; display:inline-block; margin-right:8px;"></span>
                    <strong style="font-size:13px; color:#F8FAFC;">Connected (SQLite)</strong>
                </div>
                <div style="font-size:12px; color:#A0AEC0;">
                    📁 File: <code style="color:#FFFFFF;">{config.DB_PATH}</code><br/>
                    ⚖️ Size: <span style="color:#FFFFFF;">{db_info['size_kb']:.1f} KB</span><br/>
                    🩺 Health: <span style="color:#FFFFFF;">{db_info['health']}</span>
                </div>
            </div>
            """
        )
    else:
        st.error("Database Connection Dead")

    # Action Triggers Panel
    st.subheader("System Controllers")
    
    if st.button("↻ Sync yFinance Quotes", use_container_width=True):
        with st.spinner("Downloading daily index quotes..."):
            try:
                collector = MarketDataCollector(db_manager)
                with db_manager as db:
                    collector.collect_and_store()
                st.success("Synced quotes!")
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed: {e}")

    if st.button("📰 Aggregate Sentiments News", use_container_width=True):
        with st.spinner("Aggregating sector headlines..."):
            try:
                news_collector = NewsCollector(db_manager)
                with db_manager as db:
                    news_collector.collect_and_store_news()
                st.success("Sentiments catalog updated!")
                st.rerun()
            except Exception as e:
                st.error(f"News collection failed: {e}")

    if st.button("📊 Re-calculate Sector Rankings", use_container_width=True):
        with st.spinner("Running math parameters..."):
            try:
                engine = SectorStrengthEngine(db_manager)
                with db_manager as db:
                    engine.run_engine()
                st.success("Rotations computed!")
                st.rerun()
            except Exception as e:
                st.error(f"Ranking computation failed: {e}")

    if st.button("⚡ Generate AI Market Brief", use_container_width=True):
        with st.spinner("Compiling closing brief..."):
            try:
                report_gen = ReportGenerator(db_manager)
                with db_manager as db:
                    brief = report_gen.generate_and_send_report("closing")
                if brief:
                    st.success("Closing report brief written & broadcasted!")
                    st.rerun()
                else:
                    st.error("Report output was empty.")
            except Exception as e:
                st.error(f"Report generation failed: {e}")

    st.divider()
    
    # Market Hours Indicator
    now = datetime.datetime.now()
    is_weekday = now.weekday() < 5
    is_market_hours = is_weekday and (9 <= now.hour < 16)
    status_label = "● Open" if is_market_hours else "○ Closed (EOD)"
    status_class = "highlight-green" if is_market_hours else "highlight-red"
    
    draw_html(
        f"""
        <div style="text-align:center; padding:10px; background-color:#0B0F19; border-radius:8px; border:1px solid rgba(255,255,255,0.04);">
            <span style="font-size:12px; color:#A0AEC0; font-weight:600;">MARKET STATE</span><br/>
            <span class="{status_class}" style="font-size:15px; font-weight:700;">{status_label}</span>
        </div>
        """
    )

# =============================================================================
# THEME SYSTEM LOGIC
# =============================================================================
if theme_choice == "Bloomberg Terminal":
    theme = "bloomberg"
    bg_color = "#010409"
    card_bg = "#0d1117"
    border_color = "rgba(255, 151, 0, 0.3)"
    accent_color = "#ff9700"  # Bloomberg Amber
    highlight_color = "#00ff66"  # Terminal Green
    glow_color = "rgba(255, 151, 0, 0.4)"
    mood_text = "Terminal Mode"
    mood_emoji = "📟"
    confidence = 94
elif theme_choice == "TradingView":
    theme = "tradingview"
    bg_color = "#131722"
    card_bg = "#1e222d"
    border_color = "#2a2e39"
    accent_color = "#2962ff"  # TradingView Blue
    highlight_color = "#26a69a"  # TradingView Mint Green
    glow_color = "rgba(41, 98, 255, 0.2)"
    mood_text = "TradingView Navy"
    mood_emoji = "📊"
    confidence = 90
else: # KKNova Premium (Gold & Dark)
    theme = "kknova"
    bg_color = "#050B18"
    card_bg = "#0A1326"
    border_color = "rgba(212, 175, 55, 0.25)"
    accent_color = "#D4AF37"  # Gold
    highlight_color = "#00C853"  # Premium Green
    glow_color = "rgba(212, 175, 55, 0.4)"
    mood_text = "KKNova Premium"
    mood_emoji = "👑"
    confidence = 95

# Inject client-side Auto-Refresh script
if refresh_choice != "Manual":
    refresh_minutes = int(refresh_choice.split()[0])
    st.components.v1.html(
        f"""
        <script>
            setTimeout(function() {{
                window.parent.location.reload();
            }}, {refresh_minutes * 60 * 1000});
        </script>
        """,
        height=0,
        width=0
    )

# CUSTOM ENTERPRISE CSS INJECTION + STICKY STATUS BAR
# Define CSS variables based on active theme choice
bloomberg_css = ""
font_family = "'Inter', 'Manrope', sans-serif"

if theme == "bloomberg":
    font_family = "Courier New, Consolas, monospace"
    bloomberg_css = """
    /* Bloomberg Terminal Overrides */
    * {
        font-family: 'Courier New', Consolas, monospace !important;
        color: #ff9700 !important;
    }
    strong, b, h1, h2, h3, h4, h5, h6, .title-main, .val-green, .highlight-green, .status-open-text {
        color: #00ff66 !important;
        font-family: 'Courier New', Consolas, monospace !important;
    }
    .val-red, .highlight-red, .status-closed-text {
        color: #ff3333 !important;
    }
    .fin-card {
        background-color: #0d1117 !important;
        border: 1px solid #ff9700 !important;
        box-shadow: 0 0 10px rgba(255, 151, 0, 0.2) !important;
        border-radius: 4px !important;
    }
    .fin-card:hover {
        border-color: #00ff66 !important;
        box-shadow: 0 0 15px rgba(0, 255, 102, 0.3) !important;
        transform: translateY(-2px) !important;
    }
    .sticky-status-bar {
        background-color: #0d1117 !important;
        border-bottom: 2px solid #ff9700 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #010409 !important;
        border-right: 2px solid #ff9700 !important;
    }
    div.stButton > button {
        border: 1px solid #ff9700 !important;
        background-color: #0d1117 !important;
        border-radius: 4px !important;
    }
    div.stButton > button:hover {
        color: #00ff66 !important;
        border-color: #00ff66 !important;
    }
    """
elif theme == "tradingview":
    font_family = "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, sans-serif"
    bloomberg_css = """
    /* TradingView Overrides */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #131722 !important;
        color: #d1d4dc !important;
    }
    .fin-card {
        background-color: #1e222d !important;
        border: 1px solid #2a2e39 !important;
        border-radius: 6px !important;
        box-shadow: none !important;
    }
    .fin-card:hover {
        border-color: #2962ff !important;
        box-shadow: 0 4px 12px rgba(41, 98, 255, 0.1) !important;
        transform: none !important;
    }
    .sticky-status-bar {
        background-color: #1c2030 !important;
        border-bottom: 1px solid #2a2e39 !important;
    }
    .val-green, .highlight-green, .status-open-text {
        color: #26a69a !important;
    }
    .val-red, .highlight-red, .status-closed-text {
        color: #ef5350 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #131722 !important;
        border-right: 1px solid #2a2e39 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #2962ff !important;
        border-bottom: 2px solid #2962ff !important;
    }
    """

draw_html(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700&family=Manrope:wght@500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
        background-color: {bg_color} !important;
        color: #FFFFFF !important;
        font-family: {font_family};
    }}
    
    {bloomberg_css}

    /* TradingView Heatmap grid & tile styling */
    .heatmap-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 10px;
        margin-bottom: 20px;
    }}
    .heatmap-tile {{
        position: relative;
        height: 100px;
        border-radius: 8px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: all 0.2s ease-in-out;
        cursor: pointer;
        text-decoration: none !important;
    }}
    .heatmap-tile .tile-title {{
        font-size: 12px;
        font-weight: 600;
        color: #F8FAFC;
    }}
    .heatmap-tile .tile-price {{
        font-size: 18px;
        font-weight: 700;
        font-family: monospace;
    }}
    .tile-strong-green {{
        background: linear-gradient(135deg, rgba(0, 200, 83, 0.08) 0%, rgba(0, 200, 83, 0.25) 100%) !important;
        border-color: rgba(0, 200, 83, 0.35) !important;
        color: #00C853 !important;
    }}
    .tile-strong-green:hover {{
        background: linear-gradient(135deg, rgba(0, 200, 83, 0.18) 0%, rgba(0, 200, 83, 0.45) 100%) !important;
        border-color: #00C853 !important;
        box-shadow: 0 0 15px rgba(0, 200, 83, 0.3) !important;
    }}
    .tile-mild-green {{
        background: linear-gradient(135deg, rgba(134, 239, 172, 0.05) 0%, rgba(134, 239, 172, 0.15) 100%) !important;
        border-color: rgba(134, 239, 172, 0.25) !important;
        color: #86EFAC !important;
    }}
    .tile-mild-green:hover {{
        background: linear-gradient(135deg, rgba(134, 239, 172, 0.12) 0%, rgba(134, 239, 172, 0.3) 100%) !important;
        border-color: #86EFAC !important;
        box-shadow: 0 0 15px rgba(134, 239, 172, 0.2) !important;
    }}
    .tile-strong-red {{
        background: linear-gradient(135deg, rgba(255, 82, 82, 0.08) 0%, rgba(255, 82, 82, 0.25) 100%) !important;
        border-color: rgba(255, 82, 82, 0.35) !important;
        color: #FF5252 !important;
    }}
    .tile-strong-red:hover {{
        background: linear-gradient(135deg, rgba(255, 82, 82, 0.18) 0%, rgba(255, 82, 82, 0.45) 100%) !important;
        border-color: #FF5252 !important;
        box-shadow: 0 0 15px rgba(255, 82, 82, 0.3) !important;
    }}
    .tile-mild-red {{
        background: linear-gradient(135deg, rgba(252, 165, 165, 0.05) 0%, rgba(252, 165, 165, 0.15) 100%) !important;
        border-color: rgba(252, 165, 165, 0.25) !important;
        color: #FCA5A5 !important;
    }}
    .tile-mild-red:hover {{
        background: linear-gradient(135deg, rgba(252, 165, 165, 0.12) 0%, rgba(252, 165, 165, 0.3) 100%) !important;
        border-color: #FCA5A5 !important;
        box-shadow: 0 0 15px rgba(252, 165, 165, 0.2) !important;
    }}
    .heatmap-tile .tile-tooltip {{
        visibility: hidden;
        width: 220px;
        background-color: #0A1326;
        color: #B8C0D0;
        text-align: left;
        border-radius: 6px;
        padding: 10px 14px;
        position: absolute;
        z-index: 100;
        bottom: 110%;
        left: 50%;
        margin-left: -110px;
        opacity: 0;
        transition: opacity 0.2s;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        font-size: 11px;
        line-height: 1.4;
        pointer-events: none;
    }}
    .heatmap-tile:hover .tile-tooltip {{
        visibility: visible;
        opacity: 1;
    }}

    /* Vertical Timeline styles */
    .timeline-container {{
        border-left: 2px solid rgba(255, 255, 255, 0.08);
        margin-left: 10px;
        padding-left: 20px;
        position: relative;
    }}
    .timeline-item {{
        position: relative;
        margin-bottom: 20px;
    }}
    .timeline-badge {{
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: #111827;
        border: 2px solid #D4AF37;
        position: absolute;
        left: -27px;
        top: 3px;
        box-shadow: 0 0 8px #D4AF37;
    }}
    .timeline-time {{
        font-family: monospace;
        font-weight: bold;
        font-size: 12px;
        color: #D4AF37;
        margin-bottom: 4px;
    }}
    .timeline-title {{
        font-weight: 600;
        font-size: 14px;
        color: #F8FAFC;
    }}
    .timeline-desc {{
        font-size: 12px;
        color: #94A3B8;
        margin-top: 2px;
    }}

    /* Market Alerts styles */
    .alert-chip-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }}
    .alert-chip {{
        display: flex;
        align-items: center;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid rgba(255,255,255,0.06);
    }}
    .alert-chip-high {{
        background-color: rgba(0, 200, 83, 0.1) !important;
        border-color: rgba(0, 200, 83, 0.25) !important;
        color: #00C853 !important;
    }}
    .alert-chip-low {{
        background-color: rgba(255, 82, 82, 0.1) !important;
        border-color: rgba(255, 82, 82, 0.25) !important;
        color: #FF5252 !important;
    }}
    .alert-chip-breakout {{
        background-color: rgba(212, 175, 55, 0.1) !important;
        border-color: rgba(212, 175, 55, 0.25) !important;
        color: #D4AF37 !important;
    }}
    .alert-chip-volume {{
        background-color: rgba(59, 130, 246, 0.1) !important;
        border-color: rgba(59, 130, 246, 0.25) !important;
        color: #3B82F6 !important;
    }}
    
    /* Style default Streamlit header to be transparent, keeping toggle visible */
    header[data-testid="stHeader"], [data-testid="stHeader"] {{
        background-color: transparent !important;
        background: transparent !important;
    }}
    
    /* Transparent grids/glow overlays */
    [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background-image: 
            radial-gradient(circle at 10% 15%, rgba(59, 130, 246, 0.05) 0%, transparent 45%),
            radial-gradient(circle at 85% 75%, {glow_color.replace("0.4", "0.04")} 0%, transparent 50%),
            linear-gradient(rgba(255, 255, 255, 0.005) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.005) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 40px 40px, 40px 40px;
        z-index: -1;
        pointer-events: none;
    }}
    
    /* Sidebar styling overrides */
    [data-testid="stSidebar"] {{
        background-color: #030712 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
    }}
    [data-testid="stSidebar"] * {{
        color: #F8FAFC !important;
    }}
    
    /* Institutional Fin-Cards */
    .fin-card {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }}
    .fin-card:hover {{
        transform: translateY(-4px);
        border-color: {accent_color};
        box-shadow: 0 16px 40px {glow_color.replace("0.4", "0.15")};
    }}
    
    /* Slide studio card components */
    .slide-card {{
        background-color: #0B0F19;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: all 0.2s ease-in-out;
    }}
    .slide-card:hover {{
        transform: scale(1.025);
        border-color: #D4AF37;
        box-shadow: 0 8px 24px rgba(212, 175, 55, 0.2);
    }}
    
    /* Headers Typography */
    h1, h2, h3, .title-main {{
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
        letter-spacing: -0.5px;
    }}
    
    .highlight-green {{
        color: #00C853 !important;
        font-weight: bold;
    }}
    .highlight-red {{
        color: #FF5252 !important;
        font-weight: bold;
    }}
    
    /* Navigation tabs styling overrides */
    button[data-baseweb="tab"] {{
        background-color: transparent !important;
        border: none !important;
        color: #94A3B8 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease;
        padding: 10px 20px !important;
    }}
    button[data-baseweb="tab"]:hover {{
        color: #FFFFFF !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {accent_color} !important;
        border-bottom: 2px solid {accent_color} !important;
    }}
    
    /* Standard Action Buttons */
    div.stButton > button {{
        background-color: #111827;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 10px 20px;
        transition: all 0.2s ease-in-out;
        font-weight: 600;
        width: 100%;
    }}
    div.stButton > button:hover {{
        background-color: #1F2937;
        color: {accent_color} !important;
        border-color: {accent_color};
        box-shadow: 0 0 12px {glow_color.replace("0.4", "0.2")};
    }}
    
    /* Gold CTA generate button classes */
    .gold-btn div.stButton > button {{
        background: linear-gradient(135deg, #D4AF37 0%, #AA7C11 100%) !important;
        color: #030712 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        font-size: 16px !important;
    }}
    .gold-btn div.stButton > button:hover {{
        background: linear-gradient(135deg, #FFE066 0%, #D4AF37 100%) !important;
        box-shadow: 0 6px 20px rgba(212, 175, 55, 0.35) !important;
    }}
    
    /* Form fields overrides */
    textarea, input, select {{
        background-color: #0B0F19 !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
    }}

    /* Sticky Status Bar container */
    .sticky-status-bar {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        background-color: #050B18;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 30px;
        z-index: 999999;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }}
    .status-item {{
        display: flex;
        align-items: center;
        font-size: 12px;
        color: #B8C0D0;
        padding-right: 15px;
        border-right: 1px solid rgba(255,255,255,0.08);
        flex-grow: 1;
        justify-content: center;
        white-space: nowrap;
    }}
    .status-item strong {{
        color: #FFFFFF;
        margin-right: 6px;
    }}
    .status-indicator {{
        height: 8px;
        width: 8px;
        border-radius: 50%;
        margin-right: 8px;
        display: inline-block;
    }}
    .status-indicator.open {{
        background-color: #00C853;
        box-shadow: 0 0 8px #00C853;
    }}
    .status-indicator.closed {{
        background-color: #FF5252;
        box-shadow: 0 0 8px #FF5252;
    }}
    .status-open-text {{
        color: #00C853;
        font-weight: 600;
    }}
    .status-closed-text {{
        color: #FF5252;
        font-weight: 600;
    }}
    .val-green {{
        color: #00C853;
        font-weight: 600;
    }}
    .val-red {{
        color: #FF5252;
        font-weight: 600;
    }}
    
    /* Top spacing to avoid overlap with sticky status bar */
    [data-testid="stAppViewContainer"] {{
        padding-top: 70px !important;
    }}
    
    /* Ensure the main container scrolls naturally and has plenty of bottom room */
    [data-testid="stMain"], .main {{
        overflow-y: auto !important;
    }}
    
    /* Remove unnecessary default Streamlit container padding and add generous bottom buffer */
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 120px !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }}
    
    /* Minimize empty vertical gaps between elements */
    [data-testid="stVerticalBlock"] {{
        gap: 0.6rem !important;
    }}
    
    /* Compress dividers thickness and vertical margin spacing */
    hr {{
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
        border-color: rgba(255, 255, 255, 0.05) !important;
    }}
    
    /* Style headers to have less bottom margin */
    h1, h2, h3, h4, h5, h6 {{
        margin-bottom: 0.2rem !important;
        margin-top: 0.5rem !important;
    }}
    </style>
    
    <div class="sticky-status-bar">
        <div class="status-item">
            <span class="status-indicator {'open' if is_market_hours else 'closed'}"></span>
            <strong>MARKET STATUS:</strong> <span class="{'status-open-text' if is_market_hours else 'status-closed-text'}">{'OPEN' if is_market_hours else 'CLOSED'}</span>
        </div>
        <div class="status-item">
            <strong>NIFTY 50:</strong> <span class="{'val-green' if nifty_quote['percentage_change'] >= 0 else 'val-red'}">{nifty_quote['current_price']:.2f} ({nifty_change:+.2f}%)</span>
        </div>
        <div class="status-item">
            <strong>BANK NIFTY:</strong> <span class="{'val-green' if bank_nifty_quote['percentage_change'] >= 0 else 'val-red'}">{bank_nifty_quote['current_price']:.2f} ({bank_nifty_change:+.2f}%)</span>
        </div>
        <div class="status-item">
            <strong>INDIA VIX:</strong> <span style="color: {vix_color}; font-weight: 600;">{vix_val:.2f} ({vix_status})</span>
        </div>
        <div class="status-item">
            <strong>HEALTH SCORE:</strong> <span style="color: {health_color}; font-weight:700;">{health_score}/100 ({health_status})</span>
        </div>
        <div class="status-item" style="border-right: none;">
            <strong>LAST UPDATE:</strong> <span>{db_info['last_sync'] if db_info['exists'] else 'N/A'}</span>
        </div>
    </div>
    """
)

# =============================================================================
# HEADER SECTION
# =============================================================================
col_title, col_status = st.columns([3, 2])

with col_title:
    draw_html(
        f"""
        <div style="display:flex; align-items:center; margin-bottom: 5px;">
            <h1 style="margin:0; font-size:40px;">📊 KKNova Market Intelligence</h1>
            <span style="background: linear-gradient(135deg, #D4AF37 0%, #AA7C11 100%); color:#030712; font-weight:bold; font-size:11px; padding:3px 8px; border-radius:12px; margin-left:15px; text-transform:uppercase; letter-spacing:1px;">Enterprise Suite</span>
        </div>
        <p style="color:#94A3B8; font-size:16px; margin:0 0 20px 0;">Institutional-grade EOD metrics calculations, sentiment analytics, and media automation</p>
        """
    )

with col_status:
    sync_time = db_info["last_sync"] if db_info["exists"] else "N/A"
    draw_html(
        f"""
        <div style="background-color:{card_bg}; border: 1px solid {border_color}; border-radius:12px; padding:15px; display:flex; justify-content:space-between; align-items:center; box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
            <div>
                <span style="color:#A0AEC0; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Workspace Mood</span><br/>
                <span style="font-size:18px; font-weight:700; color:{highlight_color};">{mood_emoji} {mood_text}</span>
            </div>
            <div style="border-left: 1px solid rgba(255,255,255,0.06); padding-left:15px;">
                <span style="color:#A0AEC0; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">AI Confidence</span><br/>
                <span style="font-size:18px; font-weight:700; color:{accent_color};">{confidence}%</span>
            </div>
            <div style="border-left: 1px solid rgba(255,255,255,0.06); padding-left:15px; text-align:right;">
                <span style="color:#A0AEC0; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Last Sync</span><br/>
                <span style="font-size:13px; font-family:monospace; font-weight:600; color:#F8FAFC;">{sync_time}</span>
            </div>
        </div>
        """
    )

st.divider()

# =============================================================================
# COMMAND CENTER SEARCH
# =============================================================================
st.markdown('<h3 style="margin-top: 0px;">🔍 Command Center Search</h3>', unsafe_allow_html=True)
search_query = st.text_input(
    "Search Stocks, Sectors, Reports, or News:",
    placeholder="Type stock ticker (e.g. RELIANCE.NS, TCS.NS), sector (e.g. Nifty IT), report keywords, or news...",
    key="command_center_search"
)

if search_query:
    st.markdown("#### 🎯 Unified Search Results")
    query = f"%{search_query}%"
    
    # 1. Search in Stocks (portfolio & watchlists)
    stock_results = []
    # Query portfolio holdings
    with db_manager as db:
        port_items = db.get_portfolio_holdings()
        for item in port_items:
            if search_query.lower() in item["symbol"].lower() or search_query.lower() in item["sector"].lower():
                stock_results.append({
                    "type": "Portfolio Stock",
                    "title": f"💼 {item['symbol']} ({item['sector']})",
                    "detail": f"Holding: {item['shares']} shares @ Buy Price: ₹{item['buy_price']:.2f}"
                })
        
        # Query watchlists
        cursor = db._execute("SELECT DISTINCT name, symbol FROM watchlists WHERE name LIKE ? OR symbol LIKE ?", (query, query))
        if cursor:
            for row in cursor.fetchall():
                stock_results.append({
                    "type": "Watchlist Stock",
                    "title": f"👀 {row['symbol']} (Watchlist: {row['name']})",
                    "detail": "Tracked in custom watchlists."
                })
                
    # 2. Search in Sectors
    sector_results = []
    for s_name, s_symbol in config.TICKER_MAPPING.items():
        if search_query.lower() in s_name.lower() or search_query.lower() in s_symbol.lower():
            with db_manager as db:
                quote = db.get_latest_sector_data_for_symbol(s_symbol) or db.get_latest_market_data_for_symbol(s_symbol)
            price_str = f"₹{quote['current_price']:.2f} ({quote['percentage_change']:+.2f}%)" if quote else "N/A"
            sector_results.append({
                "type": "Market Sector",
                "title": f"🌌 {s_name} ({s_symbol})",
                "detail": f"Latest Quote: {price_str}"
            })
            
    # 3. Search in Reports
    report_results = []
    with db_manager as db:
        cursor = db._execute("SELECT * FROM reports WHERE content LIKE ? OR report_type LIKE ? ORDER BY timestamp DESC LIMIT 5", (query, query))
        if cursor:
            for row in cursor.fetchall():
                report_results.append({
                    "type": "AI Report Brief",
                    "title": f"🤖 {row['report_type']} AI Brief ({row['timestamp']})",
                    "detail": row["content"][:200] + "..."
                })
                
    # 4. Search in News
    news_results = []
    with db_manager as db:
        cursor = db._execute("SELECT * FROM news_data WHERE title LIKE ? OR category LIKE ? OR source LIKE ? ORDER BY timestamp DESC LIMIT 5", (query, query, query))
        if cursor:
            for row in cursor.fetchall():
                news_results.append({
                    "type": "News Article",
                    "title": f"📰 {row['title']}",
                    "detail": f"Source: {row['source']} | Category: {row['category']} | Date: {row['publish_date']}"
                })
                
    all_results = stock_results + sector_results + report_results + news_results
    if all_results:
        cols_res = st.columns(min(len(all_results), 3))
        for idx, res in enumerate(all_results):
            col_idx = idx % min(len(all_results), 3)
            with cols_res[col_idx]:
                draw_html(
                    f"""
                    <div style="background-color:#0A1326; border:1px solid {accent_color}; border-radius:10px; padding:15px; margin-bottom:12px; height:180px; overflow:hidden;">
                        <span style="background-color:rgba(212,175,55,0.15); color:{accent_color}; font-size:10px; font-weight:bold; padding:2px 6px; border-radius:4px; text-transform:uppercase;">{res['type']}</span>
                        <h4 style="margin:8px 0 4px 0; font-size:14px; line-height:1.2; color:#FFFFFF;">{res['title']}</h4>
                        <p style="font-size:12px; color:#B8C0D0; margin:0; line-height:1.3;">{res['detail']}</p>
                    </div>
                    """
                )
    else:
        st.warning("No search results found matching your query.")
    st.divider()

# =============================================================================
# WORKSPACE TABS & WORKFLOWS
# =============================================================================
tab_market, tab_news, tab_reports, tab_carousel, tab_portfolio, tab_watchlist, tab_historical, tab_export, tab_future = st.tabs([
    "📈 Market Terminal", 
    "📰 News Intelligence", 
    "🤖 AI Reports Archive", 
    "🎨 AI Content Studio",
    "💼 My Portfolio",
    "👀 Watchlists",
    "📅 Historical Comparison",
    "📥 Export Center",
    "🚀 Future Expansion Hub"
])


with tab_market:
    # Heatmap Sector lists
    sector_list = db_data["sector"]
    if not sector_list:
        sector_list = [
            {"sector_name": "Bank Nifty", "symbol": "^NSEBANK", "current_price": 57685.75, "percentage_change": -0.48, "volume": 285800},
            {"sector_name": "Finnifty", "symbol": "^CNXFIN", "current_price": 24120.50, "percentage_change": 0.25, "volume": 15000},
            {"sector_name": "Nifty IT", "symbol": "^CNXIT", "current_price": 27426.85, "percentage_change": -3.65, "volume": 124500},
            {"sector_name": "Nifty Auto", "symbol": "^CNXAUTO", "current_price": 26583.35, "percentage_change": 1.10, "volume": 98000},
            {"sector_name": "Nifty Pharma", "symbol": "^CNXPHARMA", "current_price": 24460.30, "percentage_change": 0.73, "volume": 22600},
            {"sector_name": "Nifty FMCG", "symbol": "^CNXFMCG", "current_price": 56120.00, "percentage_change": -0.20, "volume": 45000},
            {"sector_name": "Nifty Realty", "symbol": "^CNXREALTY", "current_price": 930.50, "percentage_change": 1.85, "volume": 84000},
            {"sector_name": "Nifty Metal", "symbol": "^CNXMETAL", "current_price": 9820.00, "percentage_change": -1.20, "volume": 62000},
            {"sector_name": "Nifty Energy", "symbol": "^CNXENERGY", "current_price": 38450.00, "percentage_change": 0.55, "volume": 74000},
            {"sector_name": "Nifty PSU Bank", "symbol": "^CNXPSUBANK", "current_price": 8716.50, "percentage_change": 2.20, "volume": 110000},
            {"sector_name": "Nifty Infra", "symbol": "^CNXINFRA", "current_price": 8450.00, "percentage_change": 1.05, "volume": 53000}
        ]

    # Declare Sub-Tabs for clean layout
    sub_market_overview, sub_market_benchmarks, sub_market_sectors, sub_market_risk = st.tabs([
        "📋 Market Overview & AI Insights",
        "📈 Benchmarks & Interactive Charts",
        "🌌 Sector Rotations & Money Flow",
        "🚨 Risk Metrics & Liquidity Flows"
    ])

    # -------------------------------------------------------------------------
    # SUB-TAB 1: MARKET OVERVIEW & AI INSIGHTS
    # -------------------------------------------------------------------------
    with sub_market_overview:
        st.markdown('<h3 style="margin-top: 10px;">🩺 Flagship Metric: Market Health Score</h3>', unsafe_allow_html=True)
        col_health_gauge, col_health_details = st.columns([1, 1.2])
        
        with col_health_gauge:
            health_gauge_svg = generate_health_gauge_svg(health_score, health_color)
            trend_symbol = "▲" if health_score >= yesterday_health_score else "▼"
            trend_color = "#00C853" if health_score >= yesterday_health_score else "#FF5252"
            trend_text = f"<span style='color:{trend_color}; font-weight:600;'>{trend_symbol} {health_diff} pts</span> vs Yesterday"
            draw_html(
                f"""
                <div class="fin-card" style="text-align:center; height: 260px; display:flex; flex-direction:column; justify-content:center;">
                    <span style="color:#A0AEC0; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:10px;">Market Health State</span>
                    {health_gauge_svg}
                    <div style="font-size:14px; margin-top:8px; font-weight:600; color:#FFFFFF;">
                        Status: <span style="color:{health_color};">{health_status}</span> | {trend_text}
                    </div>
                </div>
                """
            )
            
        with col_health_details:
            draw_html(
                f"""
                <div class="fin-card" style="height: 260px;">
                    <span style="color:#A0AEC0; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; display:block; margin-bottom:12px;">Health Score Components</span>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px;">
                        <div style="background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                            <span style="color:#A0AEC0; font-size:11px;">Market Breadth</span><br/>
                            <strong style="color:#FFFFFF; font-size:14px;">{breadth_score:.1f}%</strong>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                            <span style="color:#A0AEC0; font-size:11px;">Index Momentum</span><br/>
                            <strong style="color:#FFFFFF; font-size:14px;">{momentum_score:.1f}%</strong>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                            <span style="color:#A0AEC0; font-size:11px;">Fear & Greed</span><br/>
                            <strong style="color:#FFFFFF; font-size:14px;">{fg_score:.0f}/100</strong>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                            <span style="color:#A0AEC0; font-size:11px;">Volatility (VIX)</span><br/>
                            <strong style="color:#FFFFFF; font-size:14px;">{vix_val:.2f} ({vix_risk_level} Risk)</strong>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                            <span style="color:#A0AEC0; font-size:11px;">Institutional Flow</span><br/>
                            <strong style="color:#FFFFFF; font-size:14px;">+₹{net_flow:,.2f} Cr</strong>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.04);">
                            <span style="color:#A0AEC0; font-size:11px;">Sector Participation</span><br/>
                            <strong style="color:#FFFFFF; font-size:14px;">{sector_participation:.1f}%</strong>
                        </div>
                    </div>
                </div>
                """
            )
            draw_ai_insight(
                f"Flagship Market Health Score stands at <strong>{health_score}/100</strong>, reflecting a <strong>{health_status.lower()}</strong> market regime. "
                f"Strength is primarily supported by {'positive DII flow aggregates' if net_flow >= 0 else 'underlying sector support'}, while "
                f"VIX levels suggest {'moderate risk appetite' if vix_val < 20 else 'cautious/hedged exposure'}."
            )

        st.divider()

        st.markdown('<h3>🤖 AI Market Intelligence</h3>', unsafe_allow_html=True)
        latest_brief = "PSU Banks and Infrastructure stocks are leading the market momentum on the back of institutional buying. On the other hand, IT stocks remain subdued as macroeconomic risks weigh on corporate spending."
        if db_data["reports"]:
            latest_brief = db_data["reports"][0]["content"]
        
        mood_desc = get_report_section(latest_brief, "Market Mood:") if db_data["reports"] else latest_brief
        if not mood_desc:
            mood_desc = latest_brief
            
        draw_html(
            f"""
            <div class="fin-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:10px;">
                    <span style="color:#D4AF37; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">Market Intelligence Narrative</span>
                    <span style="background-color:rgba(212,175,55,0.1); color:#D4AF37; font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600;">CONFIDENCE Score: {confidence}%</span>
                </div>
                <p style="font-size:15px; color:#F8FAFC; line-height:1.6; margin-bottom:20px;">
                    {mood_desc}
                </p>
                <div style="display:grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap:15px; border-top:1px solid rgba(255,255,255,0.06); padding-top:15px;">
                    <div style="text-align:center;">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Bullish Probability</span><br/>
                        <strong style="color:#00C853; font-size:18px;">{(fg_score + 10):.0f}%</strong>
                    </div>
                    <div style="text-align:center; border-left:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Bearish Probability</span><br/>
                        <strong style="color:#FF5252; font-size:18px;">{(100 - fg_score - 10):.0f}%</strong>
                    </div>
                    <div style="text-align:center; border-left:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Neutral Probability</span><br/>
                        <strong style="color:#3B82F6; font-size:18px;">15%</strong>
                    </div>
                    <div style="text-align:center; border-left:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Risk Regime Level</span><br/>
                        <strong style="color:{vix_color}; font-size:18px;">{vix_risk_level} Risk</strong>
                    </div>
                </div>
            </div>
            """
        )

        st.divider()

        # Expected Global Impact Score
        st.subheader("Expected Global Impact Score")
        global_tickers = [
            {"name": "Gift Nifty (NSE IX)", "symbol": "GIFTNIFTY"},
            {"name": "S&P 500 Index", "symbol": "^GSPC"},
            {"name": "Nasdaq Composite", "symbol": "^IXIC"},
            {"name": "Dow Jones Index", "symbol": "^DJI"},
            {"name": "FTSE 100 Index", "symbol": "^FTSE"},
            {"name": "DAX Index", "symbol": "^GDAXI"},
            {"name": "Nikkei 225 Index", "symbol": "^N225"},
            {"name": "Hang Seng Index", "symbol": "^HSI"}
        ]
        global_quotes = []
        for gt in global_tickers:
            global_quotes.append(get_global_quote(gt["symbol"], gt["name"]))
            
        impact = calculate_global_impact(global_quotes)
        
        if "Highly Bullish" in impact["sentiment"]:
            sentiment_color = "#00C853"
            sentiment_bg = "rgba(0, 200, 83, 0.1)"
        elif "Mildly Bullish" in impact["sentiment"]:
            sentiment_color = "#86EFAC"
            sentiment_bg = "rgba(134, 239, 172, 0.1)"
        elif "Highly Bearish" in impact["sentiment"]:
            sentiment_color = "#FF5252"
            sentiment_bg = "rgba(255, 82, 82, 0.1)"
        elif "Mildly Bearish" in impact["sentiment"]:
            sentiment_color = "#FCA5A5"
            sentiment_bg = "rgba(252, 165, 165, 0.1)"
        else:
            sentiment_color = "#3B82F6"
            sentiment_bg = "rgba(59, 130, 246, 0.1)"
            
        draw_html(
            f"""
            <div style="background-color:#0A1326; border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:15px 20px; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div>
                        <span style="color:#A0AEC0; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Expected Impact</span><br/>
                        <strong style="color:{sentiment_color}; font-size:16px;">{impact['sentiment']}</strong>
                    </div>
                    <div style="background-color:{sentiment_bg}; color:{sentiment_color}; border-radius:8px; padding:6px 12px; font-size:16px; font-family:monospace; font-weight:bold;">
                        {impact['pos_prob']}% Positive
                    </div>
                </div>
                <div style="margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; font-size:11px; color:#A0AEC0; margin-bottom:4px;">
                        <span>Positive Impact</span>
                        <span>Neutral</span>
                        <span>Negative Impact</span>
                    </div>
                    <div style="height:10px; display:flex; border-radius:5px; overflow:hidden; background-color:rgba(255,255,255,0.05);">
                        <div style="width:{impact['pos_prob']}%; background-color:#00C853;"></div>
                        <div style="width:{impact['neu_prob']}%; background-color:#F59E0B;"></div>
                        <div style="width:{impact['neg_prob']}%; background-color:#FF5252;"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:11px; font-family:monospace; font-weight:bold; color:#FFFFFF; margin-top:2px;">
                        <span style="color:#00C853;">{impact['pos_prob']}%</span>
                        <span style="color:#F59E0B;">{impact['neu_prob']}%</span>
                        <span style="color:#FF5252;">{impact['neg_prob']}%</span>
                    </div>
                </div>
                <p style="color:#B8C0D0; font-size:12px; line-height:1.4; margin:0; padding-top:6px; border-top:1px solid rgba(255,255,255,0.04);">
                    {impact['summary']}
                </p>
            </div>
            """
        )
        draw_ai_insight(
            f"Global market cues exhibit a <strong>{impact['sentiment'].lower()}</strong> correlation skew. "
            f"Traders should monitor the Gift Nifty premium as an early indicator of opening domestic momentum."
        )

        st.divider()

        # Session Timeline & Alerts
        col_timeline, col_alerts = st.columns([1, 1])
        
        with col_timeline:
            st.subheader("Market Session Timeline")
            draw_market_timeline()
            
        with col_alerts:
            st.subheader("Market Terminal Alerts")
            alerts = get_market_alerts(sector_list, net_flow)
            
            alerts_html = '<div class="alert-chip-container">'
            for a in alerts:
                chip_class = "alert-chip-breakout" if "breakout" in a["type"] else "alert-chip-volume" if "volume" in a["type"] else "alert-chip-high" if "high" in a["type"] else "alert-chip-low"
                alerts_html += f"""
                <div class="alert-chip {chip_class}">
                    {a['label']}
                </div>
                """
            alerts_html += '</div>'
            draw_html(alerts_html)
            
            for idx, a in enumerate(alerts[:3]):
                border_clr = '#D4AF37' if 'breakout' in a['type'] else '#3B82F6' if 'volume' in a['type'] else '#00C853' if 'high' in a['type'] else '#FF5252'
                draw_html(
                    f"""
                    <div style="background-color:#0A1326; border:1px solid rgba(255,255,255,0.05); border-left:4px solid {border_clr}; border-radius:8px; padding:12px 16px; margin-bottom:10px; font-size:12px;">
                        <div style="font-weight:700; font-size:13px; color:#F8FAFC; margin-bottom:4px;">
                            {a['label']}
                        </div>
                        <div style="color:#B8C0D0; line-height:1.4; margin-bottom:6px;">
                            {a['message']}
                        </div>
                        <div style="padding:8px 12px; background-color:rgba(212,175,55,0.04); border:1px dashed rgba(212,175,55,0.18); border-left:2px solid #D4AF37; border-radius:4px; color:#D4AF37; font-size:11px; line-height:1.35;">
                            🎯 <strong>Actionable Strategy:</strong> {a['action']}
                        </div>
                    </div>
                    """
                )

    # -------------------------------------------------------------------------
    # SUB-TAB 2: BENCHMARKS & INTERACTIVE CHARTS
    # -------------------------------------------------------------------------
    with sub_market_benchmarks:
        st.markdown('<h3 style="margin-top: 10px;">📈 Broad Market Benchmarks</h3>', unsafe_allow_html=True)
        col_nifty, col_bank = st.columns(2)
        
        with col_nifty:
            prices_nifty = get_historical_prices("^NSEI")
            spark_color = "#00C853" if nifty_quote['percentage_change'] >= 0 else "#FF5252"
            spark_nifty = generate_sparkline_svg(prices_nifty, color=spark_color)
            
            draw_html(
                f"""
                <div class="fin-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#A0AEC0; font-size:13px; text-transform:uppercase; font-weight:600; letter-spacing:0.5px;">Nifty 50 Index (^NSEI)</span>
                            <h2 style="margin: 5px 0 0 0; font-size:32px; font-weight:700; color:#FFFFFF;">{nifty_quote['current_price']:.2f}</h2>
                        </div>
                        <div>
                            {spark_nifty}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:20px; border-top:1px solid rgba(255,255,255,0.06); padding-top:12px;">
                        <div>
                            <span style="color:#A0AEC0; font-size:12px;">Daily Change</span><br/>
                            <span class="{'highlight-green' if nifty_quote['percentage_change'] >= 0 else 'highlight-red'}" style="font-size:15px; font-weight:700;">
                                {nifty_quote['percentage_change']:+.2f}%
                            </span>
                        </div>
                        <div>
                            <span style="color:#A0AEC0; font-size:12px;">Prev Close</span><br/>
                            <span style="font-weight:600; font-size:15px; color:#F8FAFC;">{nifty_quote['previous_close']:.2f}</span>
                        </div>
                        <div>
                            <span style="color:#A0AEC0; font-size:12px;">Daily Volume</span><br/>
                            <span style="font-weight:600; font-size:15px; color:#F8FAFC;">{nifty_quote['volume']:,}</span>
                        </div>
                    </div>
                </div>
                """
            )
            draw_ai_insight("Nifty 50 faces major resistance at 24,200. FII buying support is strong near 23,800.")

        with col_bank:
            prices_bank = get_historical_prices("^NSEBANK")
            spark_color = "#00C853" if bank_nifty_quote['percentage_change'] >= 0 else "#FF5252"
            spark_bank = generate_sparkline_svg(prices_bank, color=spark_color)
            
            draw_html(
                f"""
                <div class="fin-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#A0AEC0; font-size:13px; text-transform:uppercase; font-weight:600; letter-spacing:0.5px;">Nifty Bank Index (^NSEBANK)</span>
                            <h2 style="margin: 5px 0 0 0; font-size:32px; font-weight:700; color:#FFFFFF;">{bank_nifty_quote['current_price']:.2f}</h2>
                        </div>
                        <div>
                            {spark_bank}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:20px; border-top:1px solid rgba(255,255,255,0.06); padding-top:12px;">
                        <div>
                            <span style="color:#A0AEC0; font-size:12px;">Daily Change</span><br/>
                            <span class="{'highlight-green' if bank_nifty_quote['percentage_change'] >= 0 else 'highlight-red'}" style="font-size:15px; font-weight:700;">
                                {bank_nifty_quote['percentage_change']:+.2f}%
                            </span>
                        </div>
                        <div>
                            <span style="color:#A0AEC0; font-size:12px;">Prev Close</span><br/>
                            <span style="font-weight:600; font-size:15px; color:#F8FAFC;">{bank_nifty_quote['previous_close']:.2f}</span>
                        </div>
                        <div>
                            <span style="color:#A0AEC0; font-size:12px;">Daily Volume</span><br/>
                            <span style="font-weight:600; font-size:15px; color:#F8FAFC;">{bank_nifty_quote['volume']:,}</span>
                        </div>
                    </div>
                </div>
                """
            )
            draw_ai_insight("Bank Nifty is consolidative. Private banking sector participation is critical for a breakout.")

        st.markdown('<h4>📊 Multi-Timeframe Index Chart Analysis</h4>', unsafe_allow_html=True)
        col_sel_idx, col_sel_time = st.columns([2, 3])
        with col_sel_idx:
            chart_index = st.selectbox("Select Benchmark/Sector Index:", options=list(config.TICKER_MAPPING.keys()), index=0, key="benchmark_chart_index_sel")
        with col_sel_time:
            st.write("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            chart_period = st.radio("Select Period:", options=["1D", "5D", "1M", "3M", "6M", "1Y"], index=2, horizontal=True, key="benchmark_chart_period_sel")
            
        symbol = config.TICKER_MAPPING[chart_index]
        hist_df = get_index_history(symbol, chart_period)
        
        st.line_chart(hist_df)
        draw_ai_insight(f"Historical line chart of {chart_index} over {chart_period}. Trend displays long consolidation with key support bands.")
        
        st.write("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        col_globals_b, col_explorer_b = st.columns([1, 1.2])

        with col_globals_b:
            st.subheader("Global Benchmarks Monitor")
            global_quotes = []
            for gt in global_tickers:
                global_quotes.append(get_global_quote(gt["symbol"], gt["name"]))
                
            for g in global_quotes:
                draw_html(
                    f"""
                    <div style="background-color:#0A1326; border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:10px 15px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-weight:600; font-size:13px; color:#F8FAFC;">{g['name']}</span>
                            <span style="color:#A0AEC0; font-size:10px; margin-left:6px;">{g['symbol']}</span>
                        </div>
                        <div style="text-align:right;">
                            <strong style="font-size:13px; color:#F8FAFC;">{g['price']}</strong>
                            <span style="color:{g['color']}; font-weight:bold; font-size:12px; margin-left:10px;">{g['change_pct']}</span>
                        </div>
                    </div>
                    """
                )

        with col_explorer_b:
            st.subheader("Extended Universe Explorer")
            search_term = st.text_input("Search Indices by name or symbol:", placeholder="e.g. Pharma, FMCG, ^CNX", key="extended_universe_search")
            
            col_sort_1, col_sort_2 = st.columns(2)
            with col_sort_1:
                sort_col = st.selectbox("Sort by Column:", options=["Name", "Symbol", "Price", "Change %", "Prev Close", "Volume"], key="extended_universe_sort_col")
            with col_sort_2:
                sort_order = st.radio("Sort Order:", options=["Ascending", "Descending"], index=1, horizontal=True, key="extended_universe_sort_order")
                
            explorer_rows = []
            for name, sym in config.TICKER_MAPPING.items():
                quote = next((q for q in db_data["market"] if q["symbol"] == sym), None) or \
                        next((q for q in db_data["sector"] if q["symbol"] == sym), None)
                if not quote:
                    quote = {"current_price": 0.0, "percentage_change": 0.0, "previous_close": 0.0, "volume": 0}
                    
                explorer_rows.append({
                    "Name": name,
                    "Symbol": sym,
                    "Price": quote.get("current_price", 0.0),
                    "Change %": quote.get("percentage_change", 0.0),
                    "Prev Close": quote.get("previous_close", 0.0),
                    "Volume": quote.get("volume", 0)
                })
                
            explorer_df = pd.DataFrame(explorer_rows)
            
            if search_term:
                explorer_df = explorer_df[
                    explorer_df["Name"].str.contains(search_term, case=False) |
                    explorer_df["Symbol"].str.contains(search_term, case=False)
                ]
                
            ascending = (sort_order == "Ascending")
            explorer_df = explorer_df.sort_values(by=sort_col, ascending=ascending)
            
            page_size = 5
            total_rows = len(explorer_df)
            total_pages = max(1, (total_rows + page_size - 1) // page_size)
            
            col_pag_1, col_pag_2 = st.columns([1, 4])
            with col_pag_1:
                page_num = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, key="explorer_page_num_sub")
            
            start_idx = (page_num - 1) * page_size
            end_idx = start_idx + page_size
            paginated_df = explorer_df.iloc[start_idx:end_idx].copy()
            
            paginated_df.insert(0, "Rank", range(start_idx + 1, start_idx + len(paginated_df) + 1))
            
            st.dataframe(
                paginated_df.style.format({
                    "Price": "{:.2f}",
                    "Change %": "{:+.2f}%",
                    "Prev Close": "{:.2f}",
                    "Volume": "{:,}"
                }),
                use_container_width=True,
                hide_index=True
            )
            
            csv_data = explorer_df.to_csv(index=False)
            st.download_button(
                label="📥 Export Filtered Indices to CSV",
                data=csv_data,
                file_name="kknova_indices_explorer.csv",
                mime="text/csv",
                key="btn_export_indices_csv_sub"
            )

    # -------------------------------------------------------------------------
    # SUB-TAB 3: SECTOR ROTATIONS & MONEY FLOW
    # -------------------------------------------------------------------------
    with sub_market_sectors:
        st.markdown('<h3 style="margin-top: 10px;">🌌 Sector Intelligence & Flow Analytics</h3>', unsafe_allow_html=True)
        
        query_params = st.query_params
        selected_sector = query_params.get("sector", "Bank Nifty")
        if isinstance(selected_sector, list):
            selected_sector = selected_sector[0] if selected_sector else "Bank Nifty"
            
        col_heatmap_drawer, col_flow_rotations = st.columns([1.2, 1])
        
        with col_heatmap_drawer:
            st.subheader("TradingView Interactive Heatmap")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                heatmap_filter = st.selectbox(
                    "Filter Heatmap:",
                    options=["All Sectors", "Gainers (Positive %)", "Losers (Negative %)", "High Volume (>50k shares)"],
                    index=0,
                    key="hm_filter_choice_sub"
                )
            with col_f2:
                heatmap_sort = st.selectbox(
                    "Sort Heatmap:",
                    options=["Performance (High to Low)", "Performance (Low to High)", "Volume (High to Low)", "Alphabetical"],
                    index=0,
                    key="hm_sort_choice_sub"
                )
                
            filtered_sectors = list(sector_list)
            if heatmap_filter == "Gainers (Positive %)":
                filtered_sectors = [s for s in filtered_sectors if s["percentage_change"] > 0]
            elif heatmap_filter == "Losers (Negative %)":
                filtered_sectors = [s for s in filtered_sectors if s["percentage_change"] < 0]
            elif heatmap_filter == "High Volume (>50k shares)":
                filtered_sectors = [s for s in filtered_sectors if s["volume"] > 50000]
                
            if heatmap_sort == "Performance (High to Low)":
                filtered_sectors.sort(key=lambda x: x["percentage_change"], reverse=True)
            elif heatmap_sort == "Performance (Low to High)":
                filtered_sectors.sort(key=lambda x: x["percentage_change"])
            elif heatmap_sort == "Volume (High to Low)":
                filtered_sectors.sort(key=lambda x: x["volume"], reverse=True)
            elif heatmap_sort == "Alphabetical":
                filtered_sectors.sort(key=lambda x: x["sector_name"])
                
            if not filtered_sectors:
                st.info("No sectors match the active filter criteria.")
                
            heatmap_html = '<div class="heatmap-grid">'
            for sec in filtered_sectors:
                name = sec["sector_name"]
                sym = sec["symbol"]
                price = sec["current_price"]
                change = sec["percentage_change"]
                vol = sec["volume"]
                
                if change >= 1.5:
                    color_class = "tile-strong-green"
                elif change > 0:
                    color_class = "tile-mild-green"
                elif change <= -1.5:
                    color_class = "tile-strong-red"
                else:
                    color_class = "tile-mild-red"
                    
                momentum_lbl = "Strong Bullish" if change >= 1.5 else "Mild Bullish" if change > 0 else "Strong Bearish" if change <= -1.5 else "Mild Bearish"
                
                heatmap_html += f"""
                <a href="?sector={name.replace(' ', '+')}" target="_self" style="text-decoration: none; color: inherit;">
                    <div class="heatmap-tile {color_class}">
                        <div class="tile-title">{name}</div>
                        <div class="tile-price">{change:+.2f}%</div>
                        <div class="tile-tooltip">
                            <strong>{name} ({sym})</strong><br/>
                            Quote: {price:,.2f}<br/>
                            Change: {change:+.2f}%<br/>
                            Volume: {vol:,}<br/>
                            Momentum: {momentum_lbl}
                        </div>
                    </div>
                </a>
                """
            heatmap_html += '</div>'
            draw_html(heatmap_html)
            
            if selected_sector:
                active_sec_data = next((s for s in sector_list if s["sector_name"] == selected_sector), None)
                if not active_sec_data:
                    active_sec_data = sector_list[0]
                    
                sec_name = active_sec_data["sector_name"]
                sec_price = active_sec_data["current_price"]
                sec_change = active_sec_data["percentage_change"]
                sec_vol = active_sec_data["volume"]
                
                outlook_info = get_sector_outlook(sec_name, sec_change)
                constituents = config.SECTOR_CONSTITUENTS.get(sec_name, ["Stock A", "Stock B", "Stock C"])
                
                sec_category = SectorStrengthEngine.SECTOR_CATEGORY_MAP.get(sec_name, "General")
                sec_news_list = [n for n in db_data["news"] if n["category"] == sec_category]
                news_html = ""
                if sec_news_list:
                    for n in sec_news_list[:3]:
                        news_html += f"<li style='color:#E2E8F0; font-size:12px; margin-bottom:6px;'><strong>{n['source']}:</strong> {n['title']}</li>"
                else:
                    news_html = f"<li style='color:#A0AEC0; font-size:12px;'>No recent news headlines stored for {sec_category}. Monitor sidebar sync.</li>"
                    
                draw_html(
                    f"""
                    <div style="background-color:#0A1326; border:1.5px solid #D4AF37; border-radius:12px; padding:20px; margin-top:15px; box-shadow: 0 4px 20px rgba(212,175,55,0.15);">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:10px;">
                            <span style="color:#D4AF37; font-size:14px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">📁 Sector Intelligence Drawer: {sec_name}</span>
                            <span style="background-color:rgba({'0,200,83' if sec_change >= 0 else '255,82,82'},0.1); color:{'#00C853' if sec_change >= 0 else '#FF5252'}; font-size:12px; padding:3px 10px; border-radius:10px; font-weight:700;">
                                {sec_change:+.2f}%
                            </span>
                        </div>
                        
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:15px;">
                            <div>
                                <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase; font-weight:600;">Key Technical Levels</span>
                                <div style="margin-top:4px; font-size:13px; color:#FFFFFF;">
                                    Resistance (R1): <strong style="color:#FF5252;">{outlook_info['resistance']}</strong><br/>
                                    Support (S1): <strong style="color:#00C853;">{outlook_info['support']}</strong>
                                </div>
                            </div>
                            <div>
                                <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase; font-weight:600;">FII Flows Interest</span>
                                <div style="margin-top:4px; font-size:13px; color:#D4AF37; font-weight:600;">
                                    {outlook_info['fii']}
                                </div>
                            </div>
                        </div>
                        
                        <div style="margin-bottom:15px;">
                            <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase; font-weight:600; display:block; margin-bottom:4px;">Constituents Focus</span>
                            <div style="display:flex; flex-wrap:wrap; gap:6px;">
                                {" ".join([f"<span style='background-color:rgba(255,255,255,0.05); color:#F8FAFC; font-size:11px; font-family:monospace; padding:3px 8px; border-radius:4px; border:1px solid rgba(255,255,255,0.04);'>{stock}</span>" for stock in constituents])}
                            </div>
                        </div>
                        
                        <div style="margin-bottom:15px;">
                            <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase; font-weight:600; display:block; margin-bottom:4px;">Sector Specific News</span>
                            <ul style="margin:0; padding-left:16px;">
                                {news_html}
                            </ul>
                        </div>
                        
                        <div style="border-top:1px solid rgba(255,255,255,0.04); padding-top:10px;">
                            <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase; font-weight:600; display:block; margin-bottom:2px;">AI Outlook Summary</span>
                            <p style="font-size:12px; color:#B8C0D0; line-height:1.4; margin:0;">
                                {outlook_info['outlook']}
                            </p>
                        </div>
                    </div>
                    """
                )
                
        with col_flow_rotations:
            st.subheader("Money Flow Map")
            draw_html(
                """
                <div style="margin-bottom:20px;">
                    <svg width="100%" height="210" viewBox="0 0 400 240" xmlns="http://www.w3.org/2000/svg" style="background:#050B18; border-radius:10px; border:1px solid rgba(255,255,255,0.06); display:block; margin:0 auto;">
                        <style>
                            @keyframes flowDash {
                                to {
                                    stroke-dashoffset: -20;
                                }
                            }
                            .flow-line {
                                stroke-dasharray: 6, 6;
                                animation: flowDash 1.2s linear infinite;
                            }
                            .node-text {
                                font-family: 'Inter', sans-serif;
                                font-size: 11px;
                                fill: #F8FAFC;
                                font-weight: 600;
                            }
                            .node-subtext {
                                font-family: 'Inter', sans-serif;
                                font-size: 9px;
                                fill: #94A3B8;
                            }
                        </style>
                        <defs>
                            <marker id="arrowGreen" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                                <path d="M 0 1 L 10 5 L 0 9 z" fill="#00C853" />
                            </marker>
                        </defs>
                        <circle cx="50" cy="50" r="28" fill="#111827" stroke="#FF5252" stroke-width="2" />
                        <text x="50" y="48" text-anchor="middle" class="node-text">Nifty IT</text>
                        <text x="50" y="60" text-anchor="middle" class="node-subtext">Outflow</text>
                        <circle cx="200" cy="50" r="28" fill="#111827" stroke="#00C853" stroke-width="2" />
                        <text x="200" y="48" text-anchor="middle" class="node-text">Bank Nifty</text>
                        <text x="200" y="60" text-anchor="middle" class="node-subtext">Inflow</text>
                        <circle cx="50" cy="180" r="28" fill="#111827" stroke="#FF5252" stroke-width="2" />
                        <text x="50" y="178" text-anchor="middle" class="node-text">Pharma</text>
                        <text x="50" y="190" text-anchor="middle" class="node-subtext">Defensive</text>
                        <circle cx="200" cy="180" r="28" fill="#111827" stroke="#00C853" stroke-width="2" />
                        <text x="200" y="178" text-anchor="middle" class="node-text">PSU Bank</text>
                        <text x="200" y="190" text-anchor="middle" class="node-subtext">Breakout</text>
                        <circle cx="350" cy="115" r="28" fill="#111827" stroke="#FF5252" stroke-width="2" />
                        <text x="350" y="113" text-anchor="middle" class="node-text">FMCG</text>
                        <text x="350" y="125" text-anchor="middle" class="node-subtext">Consolid.</text>
                        <circle cx="200" cy="115" r="28" fill="#111827" stroke="#00C853" stroke-width="2" />
                        <text x="200" y="113" text-anchor="middle" class="node-text">Nifty Auto</text>
                        <text x="200" y="125" text-anchor="middle" class="node-subtext">Inflow</text>
                        <path d="M 78 50 L 172 50" fill="none" stroke="#FF5252" stroke-width="2.5" class="flow-line" marker-end="url(#arrowGreen)" />
                        <path d="M 78 180 L 172 180" fill="none" stroke="#D4AF37" stroke-width="2.5" class="flow-line" marker-end="url(#arrowGreen)" />
                        <path d="M 322 115 L 228 115" fill="none" stroke="#FF5252" stroke-width="2.5" class="flow-line" marker-end="url(#arrowGreen)" />
                    </svg>
                </div>
                """
            )
            
            st.subheader("Sector Rotation Center")
            rotations_html = '<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size:12px; margin-bottom:12px;">'
            for sname in [selected_sector, "Nifty IT", "Nifty Auto", "Nifty PSU Bank"][:4]:
                sdata = next((s for s in sector_list if s["sector_name"] == sname), None)
                if not sdata:
                    sdata = {"percentage_change": 0.0, "volume": 10000}
                change = sdata["percentage_change"]
                rs = change - nifty_change
                vol_trend = "Above Average" if sdata["volume"] > 50000 else "Neutral"
                inst_interest = "Strong Inflow" if change > 1.0 else "Selective" if change > -1.0 else "Heavy Selling"
                
                rotations_html += f"""
                <div style="background:rgba(255,255,255,0.02); padding:10px 14px; border-radius:8px; border:1px solid rgba(255,255,255,0.04);">
                    <strong style="color:#F8FAFC; display:block; font-size:13px; margin-bottom:4px;">{sname}</strong>
                    <span style="color:#A0AEC0;">Relative Strength:</span> <span style="color:{'#00C853' if rs >= 0 else '#FF5252'}; font-weight:600;">{rs:+.2f}%</span><br/>
                    <span style="color:#A0AEC0;">Volume Trend:</span> <strong style="color:#FFFFFF;">{vol_trend}</strong><br/>
                    <span style="color:#A0AEC0;">Inst. Interest:</span> <span style="color:{'#00C853' if change > 0 else '#FF5252'}; font-weight:600;">{inst_interest}</span>
                </div>
                """
            rotations_html += '</div>'
            draw_html(rotations_html)
            
            draw_ai_insight(
                f"Money flow shows active rotation into <strong>Nifty PSU Bank</strong> and <strong>Nifty Auto</strong> counters. "
                f"FII allocations are defensive, seeking shelter in Pharma relative to high-beta indices."
            )

        st.divider()

        col_ranks, col_quotes = st.columns([1, 1.2])

        with col_ranks:
            st.subheader("Sector Rotations Strength Rankings")
            if db_data["rankings"]:
                for r in db_data["rankings"]:
                    medal = "🥇" if r["rank"] == 1 else "🥈" if r["rank"] == 2 else "🥉" if r["rank"] == 3 else "❌"
                    draw_html(
                        f"""
                        <div style="background-color:#0A1326; border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:12px 18px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                            <div style="display:flex; align-items:center;">
                                <span style="font-size:20px; margin-right:12px;">{medal}</span>
                                <div>
                                    <strong style="color:#F8FAFC; font-size:15px;">Rank {r['rank']}: {r['sector_name']}</strong><br/>
                                    <span style="color:#A0AEC0; font-size:12px;">Strength Score</span>
                                </div>
                            </div>
                            <div style="text-align:right;">
                                <span style="background-color:rgba(212,175,55,0.1); color:#D4AF37; font-family:monospace; font-weight:bold; font-size:14px; padding:4px 10px; border-radius:6px;">{r['score']:.2f}</span>
                            </div>
                        </div>
                        """
                    )
            else:
                st.info("No rankings calculated. Trigger calculations in the sidebar.")

        with col_quotes:
            st.subheader("Sector Quotes Monitor")
            df_sec = pd.DataFrame(db_data["sector"])
            if not df_sec.empty:
                df_display = df_sec[["sector_name", "symbol", "current_price", "percentage_change", "volume"]]
                df_display.columns = ["Sector Name", "Ticker Symbol", "Current Quote", "Daily Change %", "Session Volume"]
                st.dataframe(df_display.style.format({
                    "Current Quote": "{:.2f}",
                    "Daily Change %": "{:+.2f}%",
                    "Session Volume": "{:,}"
                }), use_container_width=True)
            else:
                st.info("No sectoral quotes loaded.")
            draw_ai_insight(
                "Sector Rotations indicate that strength is rotating out of defensive sectors into high-beta momentum sectors, "
                "as shown by the leading sector indicators ranking above. Keep a close watch on volume breakouts in top 3 sectors."
            )

    # -------------------------------------------------------------------------
    # SUB-TAB 4: RISK METRICS & LIQUIDITY FLOWS
    # -------------------------------------------------------------------------
    with sub_market_risk:
        st.markdown('<h3 style="margin-top: 10px;">📊 Market Risk & Breadth Parameters</h3>', unsafe_allow_html=True)
        col_breadth_box, col_fg_box, col_vix_box = st.columns(3)
        
        with col_breadth_box:
            adv_pct = (advances / total_sectors) * 100
            draw_html(
                f"""
                <div class="fin-card" style="min-height:330px;">
                    <span style="color:#A0AEC0; font-size:12px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase;">Market Breadth Center</span>
                    <h4 style="margin:10px 0 5px 0; font-size:22px; font-weight:700; color:#FFFFFF;">{advances} Adv / {declines} Dec</h4>
                    <p style="font-size:12px; color:#B8C0D0; margin:0 0 10px 0;">A/D Ratio (ADR): <strong>{adr:.2f}</strong></p>
                    <div style="background-color:#1E293B; height:8px; border-radius:4px; overflow:hidden; margin-bottom:20px;">
                        <div style="background-color:#00C853; width:{adv_pct}%; height:100%; float:left;"></div>
                        <div style="background-color:#FF5252; width:{100 - adv_pct}%; height:100%; float:left;"></div>
                    </div>
                </div>
                """
            )
            
            with st.expander("🟢 View Advances Detail List"):
                if adv_list:
                    st.markdown("\n".join([f"- {item}" for item in adv_list]))
                else:
                    st.write("No positive indexes today.")
                    
            with st.expander("🔴 View Declines Detail List"):
                if dec_list:
                    st.markdown("\n".join([f"- {item}" for item in dec_list]))
                else:
                    st.write("No negative indexes today.")
            draw_ai_insight(
                f"Market Breadth is operating at <strong>{breadth_score:.1f}%</strong> positivity. "
                f"An A/D ratio of <strong>{adr:.2f}</strong> indicates that {'advancing sectors are in clear control, pointing to broad-based participation.' if adr > 1.2 else 'declining forces are dominant, suggesting a highly defensive or sector-selective posture.'}"
            )
                    
        with col_fg_box:
            fg_needle = generate_fg_needle_svg(fg_score, fg_label, fg_color)
            import random
            random.seed(int(nifty_quote["current_price"]))
            fg_trend_vals = [max(10.0, min(90.0, fg_score + random.uniform(-10.0, 10.0))) for _ in range(5)]
            fg_trend_spark = generate_sparkline_svg(fg_trend_vals, color=fg_color)
            
            draw_html(
                f"""
                <div class="fin-card" style="min-height:330px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div>
                        <span style="color:#A0AEC0; font-size:12px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase;">Fear & Greed Index</span>
                        {fg_needle}
                    </div>
                    <div style="border-top:1px solid rgba(255,255,255,0.06); padding-top:10px; margin-top:10px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#A0AEC0; font-size:11px;">Yesterday</span><br/>
                            <strong style="color:#FFFFFF; font-size:13px;">{(fg_score - nifty_change * 5.0):.0f}</strong>
                        </div>
                        <div>
                            <span style="color:#A0AEC0; font-size:11px;">Weekly Trend</span><br/>
                            {fg_trend_spark}
                        </div>
                    </div>
                </div>
                """
            )
            draw_ai_insight(
                f"Fear & Greed is currently at <strong>{fg_score:.0f} ({fg_label})</strong>. "
                f"This suggests market sentiment is {'overextended' if fg_score > 70 else 'fearful/risk-averse' if fg_score < 30 else 'stabilizing in neutral territory'}, "
                f"warranting {'caution on new entries' if fg_score > 70 else 'looking for selective accumulation opportunities' if fg_score < 30 else 'a standard range-bound trading approach'}."
            )
            
        with col_vix_box:
            vix_trend_vals = [max(10.0, min(25.0, vix_val + random.uniform(-1.0, 1.0))) for _ in range(5)]
            vix_trend_spark = generate_sparkline_svg(vix_trend_vals, color=vix_color)
            draw_html(
                f"""
                <div class="fin-card" style="min-height:330px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div>
                        <span style="color:#A0AEC0; font-size:12px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase;">India VIX Volatility</span>
                        <h2 style="margin: 15px 0 5px 0; font-size:42px; font-weight:700; color:{vix_color};">{vix_val:.2f}</h2>
                        <span style="color:{vix_color}; font-weight:600; font-size:13px;">Regime: {vix_status}</span>
                    </div>
                    <div style="border-top:1px solid rgba(255,255,255,0.06); padding-top:10px; margin-top:10px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#A0AEC0; font-size:11px;">Risk Level</span><br/>
                            <strong style="color:{vix_color}; font-size:14px;">{vix_risk_level}</strong>
                        </div>
                        <div>
                            <span style="color:#A0AEC0; font-size:11px;">VIX Trend</span><br/>
                            {vix_trend_spark}
                        </div>
                    </div>
                </div>
                """
            )
            
            with st.expander("📘 VIX Interpretation Guide"):
                st.markdown(
                    """
                    **India VIX Guide:**
                    - **Below 15 (Low Risk):** Bullish / Rangebound. Low volatility means option premiums are cheap and market confidence is high.
                    - **15 to 20 (Moderate Risk):** Normal volatility. Displays standard corrections or sector rotation behavior.
                    - **Above 22 (High Risk):** Fear regime. Higher option premiums, wild intra-day swings, and potential panic selling.
                    """
                )
            draw_ai_insight(
                f"India VIX is at <strong>{vix_val:.2f}</strong>, indicating a <strong>{vix_status.lower()}</strong> environment. "
                f"This implies option writers have {'stable pricing power' if vix_val < 15 else 'elevated risk premiums'}, and "
                f"traders should expect {'range-bound consolidation' if vix_val < 15 else 'sharp intra-day reversals'}."
            )

        st.divider()

        # Institutional Flow Center
        st.subheader("Institutional Flow Center")
        flows = get_institutional_flows()
        latest_fii_val = flows["latest_fii"]
        latest_dii_val = flows["latest_dii"]
        
        fii_class = "highlight-green" if latest_fii_val >= 0 else "highlight-red"
        dii_class = "highlight-green" if latest_dii_val >= 0 else "highlight-red"
        fii_sign = "+" if latest_fii_val >= 0 else ""
        dii_sign = "+" if latest_dii_val >= 0 else ""

        col_flow_details, col_flow_chart = st.columns([1, 1])

        with col_flow_details:
            draw_html(
                f"""
                <div style="background-color:#0A1326; border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:15px 20px; margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
                        <span style="color:#A0AEC0; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Institutional Category</span>
                        <span style="color:#A0AEC0; font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Net Daily Flow Value</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:6px;">
                        <span style="font-size:13px; font-weight:500; color:#FFFFFF;">FII Net Flow (NSE/BSE)</span>
                        <span class="{fii_class}" style="font-weight:bold; font-size:14px;">{fii_sign}₹{latest_fii_val:,.2f} Cr</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
                        <span style="font-size:13px; font-weight:500; color:#FFFFFF;">DII Net Flow (NSE/BSE)</span>
                        <span class="{dii_class}" style="font-weight:bold; font-size:14px;">{dii_sign}₹{latest_dii_val:,.2f} Cr</span>
                    </div>
                    
                    <div style="display:flex; justify-content:space-between; border-top:1px solid rgba(255,255,255,0.06); padding-top:8px; margin-bottom:4px;">
                        <span style="color:#A0AEC0; font-size:11px;">Weekly Aggregate FII:</span>
                        <strong style="color:{'#00C853' if flows['weekly_fii'] >= 0 else '#FF5252'}; font-size:11px;">
                            {"+" if flows['weekly_fii'] >= 0 else ""}₹{flows['weekly_fii']:,.2f} Cr
                        </strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="color:#A0AEC0; font-size:11px;">Weekly Aggregate DII:</span>
                        <strong style="color:{'#00C853' if flows['weekly_dii'] >= 0 else '#FF5252'}; font-size:11px;">
                            {"+" if flows['weekly_dii'] >= 0 else ""}₹{flows['weekly_dii']:,.2f} Cr
                        </strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="color:#A0AEC0; font-size:11px;">Monthly Aggregate FII:</span>
                        <strong style="color:{'#00C853' if flows['monthly_fii'] >= 0 else '#FF5252'}; font-size:11px;">
                            {"+" if flows['monthly_fii'] >= 0 else ""}₹{flows['monthly_fii']:,.2f} Cr
                        </strong>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#A0AEC0; font-size:11px;">Monthly Aggregate DII:</span>
                        <strong style="color:{'#00C853' if flows['monthly_dii'] >= 0 else '#FF5252'}; font-size:11px;">
                            {"+" if flows['monthly_dii'] >= 0 else ""}₹{flows['monthly_dii']:,.2f} Cr
                        </strong>
                    </div>
                </div>
                """
            )

        with col_flow_chart:
            st.caption("FII/DII Net Flow Trend (Last 30 Trading Days)")
            st.line_chart(flows["df"], height=160)
            
        draw_ai_insight(
            "Liquidity trends demonstrate robust domestic retail participation through DII inflows, "
            "acting as a significant counterweight to foreign FII outflow cycles."
        )

# -----------------------------------------------------------------------------
# TAB 2: NEWS INTELLIGENCE
# -----------------------------------------------------------------------------
with tab_news:
    st.subheader("Aggregated Market & Sectoral News Pipeline")
    if db_data["news"]:
        df_news = pd.DataFrame(db_data["news"])
        
        col_cat, col_find = st.columns([1, 2])
        with col_cat:
            categories_list = ["All Sector Groups"] + list(df_news["category"].unique())
            sel_cat = st.selectbox("Filter Category:", categories_list)
        with col_find:
            search_query = st.text_input("Filter Headlines by keywords:", placeholder="Type news keywords...")
            
        df_filtered = df_news
        if sel_cat != "All Sector Groups":
            df_filtered = df_filtered[df_filtered["category"] == sel_cat]
        if search_query:
            df_filtered = df_filtered[df_filtered["title"].str.contains(search_query, case=False)]
            
        st.write(f"Showing **{len(df_filtered)}** unique financial articles:")
        st.divider()
        
        for idx, row in df_filtered.iterrows():
            draw_html(
                f"""
                <div style="background-color:#0A1326; border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:16px 20px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="background-color:rgba(212,175,55,0.1); color:#D4AF37; font-size:11px; padding:3px 8px; border-radius:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">{row['category']}</span>
                        <span style="color:#A0AEC0; font-size:12px; margin-left:12px;">{row['publish_date']} | {row['source']}</span>
                        <h4 style="margin:10px 0 0 0; color:#FFFFFF; font-size:16px; font-weight:600; letter-spacing:-0.2px;">{row['title']}</h4>
                    </div>
                    <div>
                        <a href="{row['url']}" target="_blank" style="background-color:#111827; color:#FFFFFF; text-decoration:none; padding:8px 14px; border-radius:6px; font-size:13px; font-weight:600; border: 1px solid rgba(255,255,255,0.08); transition:all 0.2s;">Read Source</a>
                    </div>
                </div>
                """
            )
    else:
        st.info("No news catalog found in SQLite database.")

# -----------------------------------------------------------------------------
# TAB 3: AI REPORTS ARCHIVE
# -----------------------------------------------------------------------------
with tab_reports:
    st.subheader("Archived AI Analyst Research Briefs")
    if db_data["reports"]:
        col_type_f, col_search_f = st.columns([1, 2])
        with col_type_f:
            report_type_filter = st.selectbox(
                "Filter by Report Type:",
                options=["All Types", "Morning Briefs", "Closing Reports"],
                index=0,
                key="reports_tab_type_filter"
            )
        with col_search_f:
            report_search_query = st.text_input(
                "Search reports by keyword:",
                placeholder="Type keywords (e.g. Nifty, stocks, bullish)...",
                key="reports_tab_search_query"
            )
            
        filtered_reports = db_data["reports"]
        if report_type_filter == "Morning Briefs":
            filtered_reports = [r for r in filtered_reports if r["report_type"].lower() == "morning"]
        elif report_type_filter == "Closing Reports":
            filtered_reports = [r for r in filtered_reports if r["report_type"].lower() == "closing"]
            
        if report_search_query:
            filtered_reports = [r for r in filtered_reports if report_search_query.lower() in r["content"].lower()]
            
        if filtered_reports:
            report_options = [
                f"{r['report_type'].upper()} - {r['timestamp']}"
                for r in filtered_reports
            ]
            
            col_sel_brief, _ = st.columns([2, 1])
            with col_sel_brief:
                selected_option = st.selectbox("Select Report from Database:", report_options, key="reports_tab_dropdown")
                
            selected_index = report_options.index(selected_option)
            report = filtered_reports[selected_index]
        
            st.divider()
            draw_html(
                f"""
                <div style="background-color:#0A1326; border: 1px solid rgba(255,255,255,0.06); border-radius:12px; padding:20px; margin-bottom:15px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.04); padding-bottom:10px; margin-bottom:10px;">
                        <h3 style="margin:0; font-size:22px;">📄 {report['report_type']} AI Brief</h3>
                        <span style="font-family:monospace; color:#A0AEC0; font-size:12px;">Report ID: {report['id']} | Sync: {report['timestamp']}</span>
                    </div>
                </div>
                """
            )
            
            st.text_area(
                label="Analyst Compiled Brief Content Output",
                value=report["content"],
                height=500,
                disabled=True
            )
        else:
            st.info("No reports found matching your filter criteria.")
    else:
        st.info("No reports compiled in the database yet.")

# -----------------------------------------------------------------------------
# TAB 4: INSTAGRAM CONTENT STUDIO
# -----------------------------------------------------------------------------
with tab_carousel:
    st.subheader("AI Carousel Generation Studio")
    st.write("Construct premium square PNG slides ready for publishing directly from report briefs.")
    st.divider()
    
    if db_data["reports"]:
        brief_options = [
            f"{r['report_type']} - {r['timestamp']}"
            for r in db_data["reports"]
        ]
        
        col_pick, col_btn = st.columns([3, 2])
        with col_pick:
            sel_brief = st.selectbox("Select target report brief:", brief_options, key="carousel_tab_brief_sel")
            selected_idx = brief_options.index(sel_brief)
            report_brief = db_data["reports"][selected_idx]
            
        with col_btn:
            st.write("<div style='height:28px;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="gold-btn">', unsafe_allow_html=True)
            if st.button("🎨 Render Instagram Slides", use_container_width=True):
                with st.spinner("Executing layout rendering engine..."):
                    try:
                        generator = InstagramCarouselGenerator()
                        generator.generate_carousel_package(report_brief["content"])
                        st.success("Successfully generated PNG slides, Canva JSON metadata, and caption TXT!")
                        st.session_state["slides_ready"] = True
                    except Exception as e:
                        st.error(f"Error generating slides: {e}")
            st.markdown('</div>', unsafe_allow_html=True)
            
        st.divider()
        
        carousels_dir = Path("reports/carousel_v2")
        if carousels_dir.exists() and len(list(carousels_dir.glob("slide_*.png"))) == 5:
            st.subheader("Generated Slide Previews & Publisher Download Center")
            
            cols = st.columns(5)
            slide_categories = [
                "Market Mood",
                "Top Strong Sectors",
                "Top Weak Sectors",
                "Stocks To Watch",
                "Tomorrow Outlook"
            ]
            for idx in range(1, 6):
                slide_path = carousels_dir / f"slide_{idx}.png"
                with cols[idx - 1]:
                    import os
                    from PIL import Image
                    try:
                        with Image.open(slide_path) as img:
                            width, height = img.size
                            resolution = f"{width}x{height}"
                    except Exception:
                        resolution = "1080x1350"
                        
                    try:
                        size_bytes = os.path.getsize(slide_path)
                        if size_bytes >= 1024 * 1024:
                            file_size = f"{size_bytes / (1024 * 1024):.2f} MB"
                        else:
                            file_size = f"{size_bytes / 1024:.1f} KB"
                    except Exception:
                        file_size = "Unknown"

                    draw_html(
                        f"""
                        <div class="slide-card" style="margin-bottom: 10px;">
                            <span style="background-color:#D4AF37; color:#030712; font-size:10px; font-weight:bold; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Slide {idx}</span>
                            <p style="margin:5px 0 2px 0; font-size:12px; color:#A0AEC0; font-weight:600;">{slide_categories[idx-1]}</p>
                            <p style="margin:0; font-family:monospace; font-size:11px; color:#718096; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{slide_path.name}</p>
                            <p style="margin:2px 0 8px 0; font-size:11px; color:#CBD5E0;">{resolution} | {file_size}</p>
                        </div>
                        """
                    )
                    st.image(str(slide_path), use_container_width=True)
                    with open(slide_path, "rb") as file:
                        st.download_button(
                            label=f"📥 Download PNG",
                            data=file,
                            file_name=f"slide_{idx}.png",
                            mime="image/png",
                            use_container_width=True,
                            key=f"slide_dl_tab_{idx}"
                        )
            
            st.divider()
            
            # KKNova V4.1 Centralized Download Center
            st.subheader("📥 KKNova.io V4.1 Centralized Download Center")
            st.write("Generate and download institutional EOD market brief resources in multiple target formats.")
            
            try:
                generator = InstagramCarouselGenerator()
                parsed_narrative = generator.parse_report_text(report_brief["content"])
            except Exception as e:
                parsed_narrative = {}
                st.warning(f"Error parsing report text for multi-channel posts: {e}")
                
            # Fetch database holdings and watchlists for the PDF compiler
            with db_manager as db:
                port_holdings_dl = db.get_portfolio_holdings()
                active_wl_names_dl = db.get_watchlist_names()
                
            selected_wl_dl = active_wl_names_dl[0] if active_wl_names_dl else "None"
            if selected_wl_dl != "None":
                with db_manager as db:
                    wl_items_dl = db.get_watchlist_items(selected_wl_dl)
                wl_clean_dl = [item for item in wl_items_dl if item["symbol"] != "NIFTY"]
            else:
                wl_clean_dl = []
                
            col_zip_c, col_pdf_c, col_md_c, col_news_c, col_socials_c = st.columns(5)
            
            # 1. ZIP Package
            with col_zip_c:
                draw_html("""
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 15px; text-align: center; min-height: 180px;">
                  <div style="font-size: 28px; margin-bottom: 8px;">📦</div>
                  <strong style="font-size: 13px; display: block; margin-bottom: 5px; color:#ffffff;">CAROUSEL ZIP</strong>
                  <span style="font-size: 11px; color:#718096; display:block; margin-bottom: 12px;">5 Slide PNGs, Caption & JSON Metadata</span>
                </div>
                """)
                zip_path = carousels_dir / "kknova_carousel.zip"
                if zip_path.exists():
                    with open(zip_path, "rb") as f:
                        zip_bytes = f.read()
                    st.download_button(
                        label="Download ZIP",
                        data=zip_bytes,
                        file_name="kknova_carousel.zip",
                        mime="application/zip",
                        use_container_width=True,
                        key="dl_center_zip"
                    )
                else:
                    st.button("ZIP Not Found", disabled=True, use_container_width=True, key="dl_center_zip_disabled")
                    
            # 2. Institutional PDF
            with col_pdf_c:
                draw_html("""
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 15px; text-align: center; min-height: 180px;">
                  <div style="font-size: 28px; margin-bottom: 8px;">📄</div>
                  <strong style="font-size: 13px; display: block; margin-bottom: 5px; color:#ffffff;">EXECUTIVE PDF</strong>
                  <span style="font-size: 11px; color:#718096; display:block; margin-bottom: 12px;">Playwright-compiled PDF document</span>
                </div>
                """)
                from kknova.image_builder import ImageBuilder
                pdf_builder = ImageBuilder()
                pdf_bytes = pdf_builder.generate_pdf_report(parsed_narrative, port_holdings_dl, wl_clean_dl)
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=f"kknova_market_brief_{datetime.date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_center_pdf"
                )
                
            # 3. Markdown summary
            with col_md_c:
                draw_html("""
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 15px; text-align: center; min-height: 180px;">
                  <div style="font-size: 28px; margin-bottom: 8px;">📝</div>
                  <strong style="font-size: 13px; display: block; margin-bottom: 5px; color:#ffffff;">MARKDOWN</strong>
                  <span style="font-size: 11px; color:#718096; display:block; margin-bottom: 12px;">EOD executive brief in markdown table</span>
                </div>
                """)
                md_text = f"""# KKNova.io Market Intelligence Executive Summary
Generated on: {datetime.date.today()}

## 1. Latest AI Brief Analysis
{report_brief["content"]}

## 2. Portfolio Holdings Valuation
"""
                if port_holdings_dl:
                    df_port_md = pd.DataFrame(port_holdings_dl)
                    md_text += df_port_md.to_markdown(index=False)
                else:
                    md_text += "*No active holdings registered.*"
                st.download_button(
                    label="Download MD",
                    data=md_text.encode("utf-8"),
                    file_name=f"kknova_market_brief_{datetime.date.today()}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key="dl_center_md"
                )
                
            # 4. Newsletter
            with col_news_c:
                draw_html("""
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 15px; text-align: center; min-height: 180px;">
                  <div style="font-size: 28px; margin-bottom: 8px;">✉️</div>
                  <strong style="font-size: 13px; display: block; margin-bottom: 5px; color:#ffffff;">NEWSLETTER</strong>
                  <span style="font-size: 11px; color:#718096; display:block; margin-bottom: 12px;">Formatted copy for email newsletter</span>
                </div>
                """)
                newsletter_text = generate_newsletter(parsed_narrative)
                st.download_button(
                    label="Download Mail",
                    data=newsletter_text.encode("utf-8"),
                    file_name="kknova_newsletter_draft.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_center_news"
                )
                
            # 5. Social Drafts Package
            with col_socials_c:
                draw_html("""
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 15px; text-align: center; min-height: 180px;">
                  <div style="font-size: 28px; margin-bottom: 8px;">📱</div>
                  <strong style="font-size: 13px; display: block; margin-bottom: 5px; color:#ffffff;">SOCIAL DRAFTS</strong>
                  <span style="font-size: 11px; color:#718096; display:block; margin-bottom: 12px;">Unified platform copy drafts packet</span>
                </div>
                """)
                
                # Construct combined socials package
                package_text = f"""==================================================
1.💼 LINKEDIN POST DRAFT
==================================================
{generate_linkedin_post(parsed_narrative)}

==================================================
2.🐦 TWITTER/X THREAD DRAFT
==================================================
"""
                for t_idx, tweet in enumerate(generate_twitter_thread(parsed_narrative), 1):
                    package_text += f"\n--- TWEET {t_idx} ---\n{tweet}\n"
                    
                package_text += f"""
==================================================
3.📢 TELEGRAM BRIEF DRAFT
==================================================
{generate_telegram_brief(parsed_narrative)}

==================================================
4.🎥 YOUTUBE COMMUNITY POST DRAFT
==================================================
{generate_youtube_post(parsed_narrative)}

==================================================
5.🟢 WHATSAPP BROADCAST DRAFT
==================================================
{generate_whatsapp_broadcast(parsed_narrative)}

==================================================
6.📝 BLOG POST DRAFT
==================================================
{generate_blog_draft(parsed_narrative)}
"""
                st.download_button(
                    label="Download Socials",
                    data=package_text.encode("utf-8"),
                    file_name="kknova_socials_drafts_package.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_center_socials"
                )

            st.divider()
            st.subheader("Multi-Channel AI Narratives Preview & Export")
            st.write("Cross-platform formatted EOD narratives mapped to the same underlying AI report.")
            
            # Sub-tabs container for different channels
            sub_tabs = st.tabs([
                "💼 LinkedIn",
                "🐦 Twitter/X Thread",
                "📢 Telegram Brief",
                "🎥 YouTube Post",
                "✉️ Newsletter Draft",
                "🟢 WhatsApp Broadcast",
                "📝 Blog Draft"
            ])
            
            with sub_tabs[0]:
                linkedin_text = generate_linkedin_post(parsed_narrative)
                st.text_area("LinkedIn Post Preview (Read-only)", value=linkedin_text, height=300, key="linkedin_text_area")
                st.download_button(
                    label="📥 Download LinkedIn Post",
                    data=linkedin_text,
                    file_name="linkedin_post.txt",
                    mime="text/plain",
                    key="linkedin_dl"
                )
                
            with sub_tabs[1]:
                twitter_tweets = generate_twitter_thread(parsed_narrative)
                twitter_text = "\n\n---\n\n".join(twitter_tweets)
                st.text_area("Twitter/X Thread Preview (Read-only)", value=twitter_text, height=300, key="twitter_text_area")
                st.download_button(
                    label="📥 Download Twitter Thread",
                    data=twitter_text,
                    file_name="twitter_thread.txt",
                    mime="text/plain",
                    key="twitter_dl"
                )
                
            with sub_tabs[2]:
                telegram_text = generate_telegram_brief(parsed_narrative)
                st.text_area("Telegram Brief Preview (Read-only)", value=telegram_text, height=300, key="telegram_text_area")
                st.download_button(
                    label="📥 Download Telegram Brief",
                    data=telegram_text,
                    file_name="telegram_brief.txt",
                    mime="text/plain",
                    key="telegram_dl"
                )
                
            with sub_tabs[3]:
                youtube_text = generate_youtube_post(parsed_narrative)
                st.text_area("YouTube Community Post Preview (Read-only)", value=youtube_text, height=300, key="youtube_text_area")
                st.download_button(
                    label="📥 Download YouTube Post",
                    data=youtube_text,
                    file_name="youtube_post.txt",
                    mime="text/plain",
                    key="youtube_dl"
                )
                
            with sub_tabs[4]:
                newsletter_text = generate_newsletter(parsed_narrative)
                st.text_area("Newsletter Email Draft Preview (Read-only)", value=newsletter_text, height=300, key="newsletter_text_area")
                st.download_button(
                    label="📥 Download Newsletter Draft",
                    data=newsletter_text,
                    file_name="newsletter_draft.txt",
                    mime="text/plain",
                    key="newsletter_dl"
                )
                
            with sub_tabs[5]:
                whatsapp_text = generate_whatsapp_broadcast(parsed_narrative)
                st.text_area("WhatsApp Broadcast Preview (Read-only)", value=whatsapp_text, height=300, key="whatsapp_text_area")
                st.download_button(
                    label="📥 Download WhatsApp Broadcast",
                    data=whatsapp_text,
                    file_name="whatsapp_broadcast.txt",
                    mime="text/plain",
                    key="whatsapp_dl"
                )
                
            with sub_tabs[6]:
                blog_text = generate_blog_draft(parsed_narrative)
                st.text_area("Blog Draft Preview (Read-only)", value=blog_text, height=300, key="blog_text_area")
                st.download_button(
                    label="📥 Download Blog Draft",
                    data=blog_text,
                    file_name="blog_draft.txt",
                    mime="text/plain",
                    key="blog_dl"
                )
    else:
        st.info("No report brief is archived. Compile an AI report first.")


# -----------------------------------------------------------------------------
# TAB 5: MY PORTFOLIO
# -----------------------------------------------------------------------------
with tab_portfolio:
    st.subheader("💼 Premium Portfolio Tracker")
    st.write("Manage holdings, analyze allocations, examine sector exposure, and track risk metrics.")
    st.divider()

    # 1. Database connection & Operations
    with db_manager as db:
        portfolio_holdings = db.get_portfolio_holdings()

    col_form, col_summary_cards = st.columns([1.2, 2.8])

    with col_form:
        st.markdown("#### ➕ Add or Update Holding")
        with st.form("portfolio_form", clear_on_submit=True):
            stock_symbol = st.text_input("Stock Ticker (e.g. INFY.NS, RELIANCE.NS):", placeholder="TCS.NS")
            shares = st.number_input("Shares Quantity:", min_value=0.01, step=1.0, value=10.0)
            buy_price = st.number_input("Average Purchase Price (₹):", min_value=0.01, step=1.0, value=1000.0)
            sector_choice = st.selectbox("Sector Category:", options=list(config.SECTOR_INDICES))
            
            submit_btn = st.form_submit_button("Save Holding")
            if submit_btn and stock_symbol:
                timestamp_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with db_manager as db:
                    success = db.insert_portfolio_holding(timestamp_now, stock_symbol.upper().strip(), shares, buy_price, sector_choice)
                if success:
                    st.success(f"Successfully saved {stock_symbol.upper()}!")
                    st.rerun()
                else:
                    st.error("Failed to save holding.")

        # Delete holdings
        if portfolio_holdings:
            st.markdown("#### 🗑️ Delete Holding")
            delete_choice = st.selectbox("Select symbol to delete:", options=[item["symbol"] for item in portfolio_holdings], key="port_del_choice")
            if st.button("Delete Selected Symbol", use_container_width=True):
                with db_manager as db:
                    success = db.delete_portfolio_holding(delete_choice)
                if success:
                    st.success(f"Deleted {delete_choice}!")
                    st.rerun()
                else:
                    st.error("Failed to delete holding.")

    with col_summary_cards:
        if portfolio_holdings:
            # Fetch current prices and calculate valuations
            portfolio_rows = []
            total_cost = 0.0
            total_current_value = 0.0
            
            with st.spinner("Fetching current stock prices..."):
                for item in portfolio_holdings:
                    symbol = item["symbol"]
                    shares_qty = item["shares"]
                    avg_buy = item["buy_price"]
                    sector_name = item["sector"]
                    
                    cur_price, prev_close, mapped_sector = get_current_stock_price(symbol)
                    
                    cost = shares_qty * avg_buy
                    cur_value = shares_qty * cur_price
                    p_l = cur_value - cost
                    p_l_pct = (p_l / cost) * 100 if cost else 0.0
                    
                    total_cost += cost
                    total_current_value += cur_value
                    
                    portfolio_rows.append({
                        "Symbol": symbol,
                        "Shares": shares_qty,
                        "Buy Price": avg_buy,
                        "Current Price": cur_price,
                        "Cost Basis": cost,
                        "Current Value": cur_value,
                        "Profit / Loss": p_l,
                        "P/L %": p_l_pct,
                        "Sector": sector_name
                    })

            # Calculate returns
            total_pl = total_current_value - total_cost
            total_pl_pct = (total_pl / total_cost) * 100 if total_cost else 0.0
            
            # Risk Score Calculations
            weighted_risk_sum = 0.0
            for row in portfolio_rows:
                alloc_pct = (row["Current Value"] / total_current_value) * 100 if total_current_value else 0.0
                row["Allocation %"] = alloc_pct
                
                risk_weights = {
                    "Nifty IT": 70, "Bank Nifty": 60, "Finnifty": 60, "Nifty Auto": 65,
                    "Nifty Pharma": 45, "Nifty FMCG": 35, "Nifty Realty": 85, "Nifty Metal": 80,
                    "Nifty Energy": 55, "Nifty PSU Bank": 75, "Nifty Infra": 65
                }
                sect_risk = risk_weights.get(row["Sector"], 50)
                weighted_risk_sum += row["Current Value"] * sect_risk

            base_risk_score = weighted_risk_sum / total_current_value if total_current_value else 0.0
            
            concentration_penalty = 0
            max_alloc = max([row["Allocation %"] for row in portfolio_rows]) if portfolio_rows else 0.0
            if max_alloc > 40.0:
                concentration_penalty += 10
            if len(portfolio_rows) < 3:
                concentration_penalty += 5
                
            risk_score = round(min(100.0, max(10.0, base_risk_score + concentration_penalty)))
            
            if risk_score > 65:
                risk_lbl = "Aggressive / High Risk"
                risk_clr = "#FF5252"
            elif risk_score > 45:
                risk_lbl = "Balanced / Moderate Risk"
                risk_clr = "#F59E0B"
            else:
                risk_lbl = "Conservative / Low Risk"
                risk_clr = "#00C853"
                
            # Summary Metrics Cards
            cols_summary = st.columns(4)
            with cols_summary[0]:
                draw_html(
                    f"""
                    <div class="fin-card" style="padding:15px; text-align:center; min-height:100px;">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Cost Basis</span>
                        <h4 style="margin:5px 0 0 0; color:#FFFFFF;">₹{total_cost:,.2f}</h4>
                    </div>
                    """
                )
            with cols_summary[1]:
                draw_html(
                    f"""
                    <div class="fin-card" style="padding:15px; text-align:center; min-height:100px;">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Current Value</span>
                        <h4 style="margin:5px 0 0 0; color:#FFFFFF;">₹{total_current_value:,.2f}</h4>
                    </div>
                    """
                )
            with cols_summary[2]:
                pl_color = "#00C853" if total_pl >= 0 else "#FF5252"
                pl_sign = "+" if total_pl >= 0 else ""
                draw_html(
                    f"""
                    <div class="fin-card" style="padding:15px; text-align:center; min-height:100px;">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Total Return</span>
                        <h4 style="margin:5px 0 0 0; color:{pl_color};">{pl_sign}₹{total_pl:,.2f} ({total_pl_pct:+.2f}%)</h4>
                    </div>
                    """
                )
            with cols_summary[3]:
                draw_html(
                    f"""
                    <div class="fin-card" style="padding:15px; text-align:center; min-height:100px;">
                        <span style="color:#A0AEC0; font-size:11px; text-transform:uppercase;">Portfolio Risk</span>
                        <h4 style="margin:5px 0 0 0; color:{risk_clr};">{risk_score}/100</h4>
                        <span style="color:{risk_clr}; font-size:10px; font-weight:bold;">{risk_lbl}</span>
                    </div>
                    """
                )

            # Filters
            col_port_f1, col_port_f2 = st.columns(2)
            with col_port_f1:
                sector_filter = st.selectbox(
                    "Filter Portfolio by Sector:",
                    options=["All Sectors"] + list(config.SECTOR_INDICES),
                    index=0,
                    key="portfolio_sector_filter"
                )
            with col_port_f2:
                symbol_filter = st.text_input(
                    "Search Symbol in Portfolio:",
                    placeholder="e.g. RELIANCE.NS",
                    key="portfolio_symbol_filter"
                )
                
            filtered_portfolio_rows = portfolio_rows
            if sector_filter != "All Sectors":
                filtered_portfolio_rows = [row for row in filtered_portfolio_rows if row["Sector"] == sector_filter]
            if symbol_filter:
                filtered_portfolio_rows = [row for row in filtered_portfolio_rows if symbol_filter.upper() in row["Symbol"].upper()]
                
            df_portfolio_filtered = pd.DataFrame(filtered_portfolio_rows)
            
            # Dataframe display
            st.write("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if not df_portfolio_filtered.empty:
                st.dataframe(
                    df_portfolio_filtered.style.format({
                        "Shares": "{:.2f}",
                        "Buy Price": "₹{:.2f}",
                        "Current Price": "₹{:.2f}",
                        "Cost Basis": "₹{:,.2f}",
                        "Current Value": "₹{:,.2f}",
                        "Profit / Loss": "₹{:+.2f}",
                        "P/L %": "{:+.2f}%",
                        "Allocation %": "{:.2f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No portfolio holdings match the filter criteria.")
            
            # visual charts with Plotly
            col_chart_alloc, col_chart_sector = st.columns(2)
            with col_chart_alloc:
                if not df_portfolio_filtered.empty:
                    fig_alloc = px.pie(
                        df_portfolio_filtered, values="Current Value", names="Symbol", hole=0.4,
                        title="Asset Allocation Breakdown",
                        color_discrete_sequence=px.colors.sequential.solar_r if theme == "kknova" else px.colors.sequential.Agsunset
                    )
                    fig_alloc.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#FFFFFF"
                    )
                    st.plotly_chart(fig_alloc, use_container_width=True)
                else:
                    st.info("No allocation breakdown data available.")
                
            with col_chart_sector:
                if not df_portfolio_filtered.empty:
                    df_sector_exp = df_portfolio_filtered.groupby("Sector")["Current Value"].sum().reset_index()
                    fig_sector = px.bar(
                        df_sector_exp, x="Sector", y="Current Value",
                        title="Sector Exposure Valuation",
                        labels={"Current Value": "Value (₹)", "Sector": "Sector Indices"},
                        color_discrete_sequence=[accent_color]
                    )
                fig_sector.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#FFFFFF"
                )
                st.plotly_chart(fig_sector, use_container_width=True)
        else:
            st.info("No holdings registered. Use the panel on the left to add stocks to your portfolio.")


# -----------------------------------------------------------------------------
# TAB 6: WATCHLISTS
# -----------------------------------------------------------------------------
with tab_watchlist:
    st.subheader("👀 Custom Watchlists")
    st.write("Monitor customized baskets of equities and sectors.")
    st.divider()

    with db_manager as db:
        watchlist_names = db.get_watchlist_names()

    col_wl_ctrl, col_wl_display = st.columns([1.2, 2.8])

    with col_wl_ctrl:
        st.markdown("#### 📂 Watchlist Controller")
        
        new_wl_name = st.text_input("Create New Watchlist Name:", placeholder="e.g. Blue Chips")
        if st.button("Create Watchlist", use_container_width=True):
            if new_wl_name:
                timestamp_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with db_manager as db:
                    success = db.insert_watchlist_item(timestamp_now, new_wl_name, "NIFTY")
                if success:
                    st.success(f"Watchlist '{new_wl_name}' created!")
                    st.rerun()
                else:
                    st.error("Failed to create watchlist.")
                    
        st.divider()
        
        if watchlist_names:
            selected_wl = st.selectbox("Select Active Watchlist:", options=watchlist_names)
            
            new_ticker = st.text_input("Add Ticker to Watchlist (e.g. INFY.NS, RELIANCE.NS):", placeholder="RELIANCE.NS")
            if st.button("Add Ticker", use_container_width=True):
                if new_ticker:
                    timestamp_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with db_manager as db:
                        success = db.insert_watchlist_item(timestamp_now, selected_wl, new_ticker.upper().strip())
                    if success:
                        st.success(f"Added {new_ticker.upper()} to {selected_wl}!")
                        st.rerun()
                    else:
                        st.error("Failed to add ticker.")
                        
            with db_manager as db:
                wl_items = db.get_watchlist_items(selected_wl)
            clean_wl_items = [item for item in wl_items if item["symbol"] != "NIFTY"]
            
            if clean_wl_items:
                st.write("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                delete_symbol = st.selectbox("Remove symbol from watchlist:", options=[item["symbol"] for item in clean_wl_items], key="wl_del_sym_choice")
                if st.button("Remove Symbol", use_container_width=True):
                    with db_manager as db:
                        success = db.delete_watchlist_item(selected_wl, delete_symbol)
                    if success:
                        st.success(f"Removed {delete_symbol} from {selected_wl}!")
                        st.rerun()
                    else:
                        st.error("Failed to remove symbol.")
            
            st.divider()
            
            if st.button("Delete Entire Watchlist", use_container_width=True, type="secondary"):
                with db_manager as db:
                    success = db.delete_watchlist(selected_wl)
                if success:
                    st.success(f"Watchlist '{selected_wl}' deleted!")
                    st.rerun()
                else:
                    st.error("Failed to delete watchlist.")
        else:
            st.info("No custom watchlists created yet.")
            selected_wl = None

    with col_wl_display:
        if selected_wl:
            st.markdown(f"#### 📋 Baskets Monitor: {selected_wl}")
            
            with db_manager as db:
                wl_items = db.get_watchlist_items(selected_wl)
            clean_items = [item for item in wl_items if item["symbol"] != "NIFTY"]
            
            if clean_items:
                wl_rows = []
                with st.spinner("Loading watchlist statistics..."):
                    for item in clean_items:
                        symbol = item["symbol"]
                        cur_price, prev_close, mapped_sector = get_current_stock_price(symbol)
                        change = cur_price - prev_close
                        change_pct = (change / prev_close) * 100 if prev_close else 0.0
                        
                        wl_rows.append({
                            "Symbol": symbol,
                            "Price (₹)": cur_price,
                            "Change (₹)": change,
                            "Change %": change_pct,
                            "Sector Group": mapped_sector
                        })
                
                df_wl = pd.DataFrame(wl_rows)
                st.dataframe(
                    df_wl.style.format({
                        "Price (₹)": "{:.2f}",
                        "Change (₹)": "{:+.2f}",
                        "Change %": "{:+.2f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.write("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.markdown("##### 📈 5-Day Trend Comparison")
                col_sel_wl_sym = st.selectbox("Select symbol to view 5-day historical trend chart:", options=[row["Symbol"] for row in wl_rows])
                if col_sel_wl_sym:
                    hist_df = get_ticker_5d_history(col_sel_wl_sym)
                    st.line_chart(hist_df, height=200)
            else:
                st.info("Watchlist is currently empty. Add symbols in the left controller.")
        else:
            st.info("Select or create a watchlist to view quotes.")


# -----------------------------------------------------------------------------
# TAB 7: HISTORICAL COMPARISON
# -----------------------------------------------------------------------------
with tab_historical:
    st.subheader("📅 Multi-Timeframe Performance Engine")
    st.write("Compare broad index and sector performance across daily, weekly, and monthly horizons.")
    st.divider()

    with st.spinner("Computing multi-timeframe returns..."):
        df_comparison = get_historical_comparison_data()

    if not df_comparison.empty:
        st.write("#### 📊 Sector and Benchmark Momentum Table")
        
        def color_returns(val):
            color = "#00C853" if val >= 0 else "#FF5252"
            return f'color: {color}; font-weight: bold;'
            
        st.dataframe(
            df_comparison.style.format({
                "Price": "{:,.2f}",
                "Today %": "{:+.2f}%",
                "Yesterday %": "{:+.2f}%",
                "Last Week %": "{:+.2f}%",
                "Last Month %": "{:+.2f}%"
            }).map(color_returns, subset=["Today %", "Yesterday %", "Last Week %", "Last Month %"]),
            use_container_width=True,
            hide_index=True
        )
        
        st.write("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 🌌 Multi-Horizon Performance Comparison Chart")
        
        df_melted = pd.melt(
            df_comparison, id_vars=["Name"], value_vars=["Today %", "Yesterday %", "Last Week %", "Last Month %"],
            var_name="Horizon", value_name="Return %"
        )
        
        fig_hist = px.bar(
            df_melted, x="Name", y="Return %", color="Horizon", barmode="group",
            title="Comparative Return Over Horizon",
            labels={"Name": "Index / Sector", "Return %": "Returns (%)"},
            color_discrete_sequence=px.colors.qualitative.Antique
        )
        fig_hist.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#FFFFFF"
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.warning("Unable to fetch historical comparison data.")


# -----------------------------------------------------------------------------
# TAB 8: EXPORT CENTER
# -----------------------------------------------------------------------------
with tab_export:
    st.subheader("📥 Export Center")
    st.write("Generate and download records, analytics, and briefs in various formats.")
    st.divider()

    with db_manager as db:
        port_holdings_for_export = db.get_portfolio_holdings()
        active_wl_names = db.get_watchlist_names()
    
    selected_wl_for_export = st.selectbox("Select Watchlist to Export:", options=active_wl_names if active_wl_names else ["None"], key="wl_export_sel")
    
    if selected_wl_for_export != "None":
        with db_manager as db:
            wl_items_for_export = db.get_watchlist_items(selected_wl_for_export)
        wl_clean = [item for item in wl_items_for_export if item["symbol"] != "NIFTY"]
    else:
        wl_clean = []

    latest_report_text = "Market closed EOD with strong PSU banking inflows and IT distribution."
    if db_data["reports"]:
        latest_report_text = db_data["reports"][0]["content"]

    col_pdf, col_xlsx = st.columns(2)

    with col_pdf:
        draw_html(
            f"""
            <div class="fin-card" style="text-align:center; min-height:220px; display:flex; flex-direction:column; justify-content:center;">
                <span style="font-size:32px;">📄</span>
                <strong style="font-size:16px; display:block; margin:10px 0;">PDF Report Pack</strong>
                <p style="color:#A0AEC0; font-size:12px;">Styled executive summary containing the latest AI Brief, Portfolio holdings, and watchlist snapshot.</p>
            </div>
            """
        )
        pdf_bytes = generate_pdf_report(latest_report_text, port_holdings_for_export, selected_wl_for_export, wl_clean)
        st.download_button(
            label="📥 Download PDF Document",
            data=pdf_bytes,
            file_name=f"kknova_market_brief_{datetime.date.today()}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with col_xlsx:
        draw_html(
            f"""
            <div class="fin-card" style="text-align:center; min-height:220px; display:flex; flex-direction:column; justify-content:center;">
                <span style="font-size:32px;">📊</span>
                <strong style="font-size:16px; display:block; margin:10px 0;">Excel Spreadsheet (XLSX)</strong>
                <p style="color:#A0AEC0; font-size:12px;">Multi-sheet Excel workbook mapping Broad Quotes, Sector Strength scores, Portfolio holdings, and Watchlist.</p>
            </div>
            """
        )
        xlsx_bytes = generate_excel_report(db_data, port_holdings_for_export, wl_clean, selected_wl_for_export)
        st.download_button(
            label="📥 Download Excel Workbook",
            data=xlsx_bytes,
            file_name=f"kknova_database_export_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    st.write("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    st.markdown("#### 📂 Text & Table Formats (CSV & Markdown)")
    
    col_csv, col_md = st.columns(2)
    
    with col_csv:
        if port_holdings_for_export:
            df_port_csv = pd.DataFrame(port_holdings_for_export)
            csv_data = df_port_csv.to_csv(index=False).encode("utf-8")
        else:
            csv_data = "No holdings registered".encode("utf-8")
            
        st.download_button(
            label="📥 Download Portfolio CSV",
            data=csv_data,
            file_name="kknova_portfolio_holdings.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    with col_md:
        md_text = f"""# KKNova.io Market Intelligence Executive Summary
Generated on: {datetime.date.today()}

## 1. Latest AI Brief Analysis
{latest_report_text}

## 2. Portfolio Holdings Valuation
"""
        if port_holdings_for_export:
            df_port_md = pd.DataFrame(port_holdings_for_export)
            md_text += df_port_md.to_markdown(index=False)
        else:
            md_text += "*No active holdings registered.*"
            
        st.download_button(
            label="📥 Download Markdown Summary",
            data=md_text.encode("utf-8"),
            file_name=f"kknova_market_summary_{datetime.date.today()}.md",
            mime="text/markdown",
            use_container_width=True
        )

# -----------------------------------------------------------------------------
# TAB 9: FUTURE EXPANSION HUB
# -----------------------------------------------------------------------------
with tab_future:
    st.subheader("🚀 Future Expansion Hub")
    st.write("Planned enterprise-grade additions. Modules will unlock in upcoming platform updates.")
    st.divider()

    # Grid of planned extensions
    col_feat1, col_feat2, col_feat3, col_feat4 = st.columns(4)
    col_feat5, col_feat6, col_feat7, col_feat8 = st.columns(4)

    with col_feat1:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">💼</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Portfolio Intelligence</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">Automated smart rebalancing suggestions based on institutional flows and risk limits.</p>
          </div>
          <span style="background: rgba(59, 130, 246, 0.15); color: #3B82F6; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Planned: Q3 2026</span>
        </div>
        """)

    with col_feat2:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">🔍</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Stock Screener AI</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">Natural language query search scanner to find breakout setups instantly.</p>
          </div>
          <span style="background: rgba(59, 130, 246, 0.15); color: #3B82F6; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Planned: Q3 2026</span>
        </div>
        """)

    with col_feat3:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">📊</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Earnings Intelligence</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">Real-time conference call transcription summary and sentiment shifts scorer.</p>
          </div>
          <span style="background: rgba(59, 130, 246, 0.15); color: #3B82F6; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Planned: Q4 2026</span>
        </div>
        """)

    with col_feat4:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">🌎</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Global Macro Hub</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">US yields, Dollar Index, and global liquidity flows correlation tracker.</p>
          </div>
          <span style="background: rgba(59, 130, 246, 0.15); color: #3B82F6; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Planned: Q4 2026</span>
        </div>
        """)

    with col_feat5:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">✉️</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Personalized Reports</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">Automated custom PDF briefings delivered directly to your registered email.</p>
          </div>
          <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Beta Mockup</span>
        </div>
        """)

    with col_feat6:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">🎙️</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Voice Market Brief</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">Generate EOD audio podcast updates narrated by an AI financial analyst.</p>
          </div>
          <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Beta Mockup</span>
        </div>
        """)

    with col_feat7:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">📲</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Mobile App API</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">API endpoints gateway access package for custom application ingestion.</p>
          </div>
          <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">Beta Mockup</span>
        </div>
        """)

    with col_feat8:
        draw_html("""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; min-height: 220px; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <span style="font-size: 24px;">🔄</span>
            <h4 style="margin: 10px 0 5px 0; font-size: 15px; color:#ffffff;">Real-Time Streams</h4>
            <p style="font-size: 12px; color:#718096; line-height:1.4;">Websockets streams connecting directly to SEBI announcements and indexes.</p>
          </div>
          <span style="background: rgba(239, 68, 68, 0.15); color: #EF4444; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; align-self: flex-start; text-transform: uppercase;">In Design</span>
        </div>
        """)


