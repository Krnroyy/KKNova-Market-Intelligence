import logging
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from typing import Dict, Any, List, Tuple
from playwright.sync_api import sync_playwright
import datetime

# Initialize module logger
logger = logging.getLogger("kknova.image_builder")

class ImageBuilder:
    """
    Renders premium portrait (1080x1350) financial media slides for Instagram
    using a dedicated HTML/CSS canvas rendering engine powered by Playwright.
    Also handles compilation of institutional-grade market briefs into PDFs.
    """
    def __init__(self, width: int = 1080, height: int = 1350) -> None:
        self.width = width
        self.height = height

    def _get_html_wrapper(self, title: str, slide_num: int, bg_overlay: str, content_html: str, total_slides: int = 5) -> str:
        """Wraps slide content with the base HTML/CSS template structure using premium styling."""
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    width: {self.width}px;
    height: {self.height}px;
    font-family: 'SF Pro', -apple-system, BlinkMacSystemFont, 'Inter', 'IBM Plex Sans', 'Segoe UI', Roboto, sans-serif;
    background-color: #071224;
    color: #ffffff;
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 55px;
  }}
  
  .top-bar {{
    position: absolute;
    top: 0;
    left: 0;
    width: {self.width}px;
    height: 10px;
    background: #D4AF37;
    z-index: 10;
  }}

  .bg-overlay {{
    position: absolute;
    top: 0;
    left: 0;
    width: {self.width}px;
    height: {self.height}px;
    z-index: 1;
    pointer-events: none;
  }}

  header {{
    z-index: 5;
    position: relative;
    margin-bottom: 15px;
  }}
  .brand {{
    font-size: 22px;
    font-weight: 800;
    color: #D4AF37;
    letter-spacing: 2px;
    margin-bottom: 6px;
    text-transform: uppercase;
  }}
  .slide-title {{
    font-size: 46px;
    font-weight: 900;
    color: #ffffff;
    text-transform: uppercase;
    letter-spacing: -1px;
    line-height: 1.1;
  }}

  footer {{
    z-index: 5;
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 18px;
    margin-top: 15px;
  }}
  .footer-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .handle {{
    font-size: 20px;
    font-weight: 700;
    color: #B8C0D0;
  }}
  .page-indicator {{
    font-size: 20px;
    font-weight: 600;
    color: #B8C0D0;
  }}
  .disclaimer-bar {{
    font-size: 13px;
    color: #718096;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    text-align: center;
  }}

  .content-area {{
    flex-grow: 1;
    z-index: 5;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: center;
    margin: 25px 0;
  }}

  .glass-card {{
    background: rgba(14, 26, 53, 0.75);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1.5px solid rgba(255, 255, 255, 0.08);
    border-radius: 24px;
    padding: 35px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
    height: 100%;
  }}
</style>
</head>
<body>
  <div class="top-bar"></div>
  {bg_overlay}
  
  <header>
    <div class="brand">KKNOVA CONTENT INTELLIGENCE ENGINE V4.1</div>
    <div class="slide-title">{title}</div>
  </header>
  
  <div class="content-area">
    {content_html}
  </div>
  
  <footer>
    <div class="footer-row">
      <div class="handle">@kknova.io | KKNova Insight</div>
      <div class="page-indicator">{slide_num} / {total_slides}</div>
    </div>
    <div class="disclaimer-bar">Educational Content Only • Not Investment Advice • SEBI Registered Investment Advisers disclaimer applies</div>
  </footer>
</body>
</html>
"""

    def _render_html_to_image(self, html_content: str) -> Image.Image:
        """Launches a headless browser to render the HTML slide and capture it as a PIL Image."""
        import sys
        import asyncio
        if sys.platform == 'win32':
            try:
                # Playwright requires ProactorEventLoop on Windows to support subprocesses
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception as e:
                logger.warning(f"Could not set WindowsProactorEventLoopPolicy: {e}")

        logger.info("Using Template: template_v4.1.html")
        logger.info("Using Theme: finance_premium_v4.1")
        logger.info("Using Renderer: playwright_html_renderer")
        logger.info(f"Export Size: {self.width}x{self.height}")

        channels = ["chrome", "msedge"]
        screenshot_bytes = None
        
        for channel in channels:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, channel=channel)
                    page = browser.new_page(viewport={"width": self.width, "height": self.height})
                    page.set_content(html_content)
                    page.wait_for_timeout(250)  # Wait briefly for CSS/Fonts to fully load
                    screenshot_bytes = page.screenshot()
                    browser.close()
                    break
            except Exception as e:
                logger.warning(f"Playwright rendering failed with channel {channel}: {e}")
                continue
                
        if screenshot_bytes:
            return Image.open(BytesIO(screenshot_bytes))
        else:
            logger.error("Playwright HTML rendering failed for all channels. Falling back to default canvas image.")
            img = Image.new("RGB", (self.width, self.height), color="#071224")
            draw = ImageDraw.Draw(img)
            draw.text((100, 500), "Error Rendering Slide Image", fill="#FF5252")
            return img

    def draw_base_layout(self, title: str, slide_num: int, total_slides: int = 5) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
        """Creates the template base layout and returns a PIL Image. Used for testing."""
        html = self._get_html_wrapper(title, slide_num, "", "<div class='glass-card'></div>", total_slides)
        img = self._render_html_to_image(html)
        return img, ImageDraw.Draw(img)

    def _get_background_overlay(self, mood: str) -> str:
        """Returns low-opacity sector themed vector SVG overlay based on the market mood."""
        mood_lower = mood.lower()
        opacity = "0.08"
        
        if "bull" in mood_lower:
            return f"""
            <div class="bg-overlay" style="background: linear-gradient(135deg, #020f26 0%, #071224 100%);">
              <svg width="{self.width}" height="{self.height}" viewBox="0 0 1080 1350" fill="none" xmlns="http://www.w3.org/2000/svg" style="opacity: {opacity}; position: absolute; top:0; left:0; width:100%; height:100%;">
                <!-- Dynamic bullish arrows and trends -->
                <path d="M100 1200 L300 950 L500 1000 L700 750 L900 800 L1080 500" stroke="#00C853" stroke-width="8" stroke-linecap="round"/>
                <path d="M150 1100 L350 850 L550 900 L750 650 L950 700" stroke="#00C853" stroke-width="3" stroke-dasharray="10,15"/>
                <circle cx="300" cy="950" r="12" fill="#00C853"/>
                <circle cx="700" cy="750" r="12" fill="#00C853"/>
                <circle cx="1080" cy="500" r="20" fill="#00C853"/>
              </svg>
            </div>
            """
        elif "bear" in mood_lower:
            return f"""
            <div class="bg-overlay" style="background: linear-gradient(135deg, #180308 0%, #071224 100%);">
              <svg width="{self.width}" height="{self.height}" viewBox="0 0 1080 1350" fill="none" xmlns="http://www.w3.org/2000/svg" style="opacity: {opacity}; position: absolute; top:0; left:0; width:100%; height:100%;">
                <!-- Volatility waves and bearish trend -->
                <path d="M100 500 L300 750 L500 700 L700 950 L900 900 L1080 1200" stroke="#FF5252" stroke-width="8" stroke-linecap="round"/>
                <path d="M150 600 L350 850 L550 800 L750 1050 L950 1000" stroke="#FF5252" stroke-width="3" stroke-dasharray="10,15"/>
                <circle cx="300" cy="750" r="12" fill="#FF5252"/>
                <circle cx="700" cy="950" r="12" fill="#FF5252"/>
                <circle cx="1080" cy="1200" r="20" fill="#FF5252"/>
              </svg>
            </div>
            """
        else:
            return f"""
            <div class="bg-overlay" style="background: linear-gradient(135deg, #030818 0%, #071224 100%);">
              <svg width="{self.width}" height="{self.height}" viewBox="0 0 1080 1350" fill="none" xmlns="http://www.w3.org/2000/svg" style="opacity: {opacity}; position: absolute; top:0; left:0; width:100%; height:100%;">
                <line x1="0" y1="270" x2="1080" y2="270" stroke="#ffffff" stroke-width="1"/>
                <line x1="0" y1="540" x2="1080" y2="540" stroke="#ffffff" stroke-width="1"/>
                <line x1="0" y1="810" x2="1080" y2="810" stroke="#ffffff" stroke-width="1"/>
                <line x1="0" y1="1080" x2="1080" y2="1080" stroke="#ffffff" stroke-width="1"/>
                <line x1="216" y1="0" x2="216" y2="1350" stroke="#ffffff" stroke-width="1"/>
                <line x1="432" y1="0" x2="432" y2="1350" stroke="#ffffff" stroke-width="1"/>
                <line x1="648" y1="0" x2="648" y2="1350" stroke="#ffffff" stroke-width="1"/>
                <line x1="864" y1="0" x2="864" y2="1350" stroke="#ffffff" stroke-width="1"/>
              </svg>
            </div>
            """

    def build_slide_1_mood(self, parsed: Dict[str, Any]) -> Image.Image:
        """Renders Slide 1: High-impact EOD Scorecard, Market Grade, and Sentiment."""
        scorecard = parsed.get("scorecard", {})
        mood = scorecard.get("market_mood", "Neutral")
        health_score = scorecard.get("health_score", 50)
        fii_vs_dii = scorecard.get("fii_vs_dii", "")
        smart_money = scorecard.get("smart_money", "")
        risk_level = scorecard.get("risk_level", "")
        opp_level = scorecard.get("opportunity_level", "")
        bias = scorecard.get("tomorrow_bias", "")
        summary = scorecard.get("one_line_summary", "")
        
        is_bull = "bull" in mood.lower()
        is_bear = "bear" in mood.lower()
        
        mood_color = "#00C853" if is_bull else "#FF5252" if is_bear else "#D4AF37"
        mood_icon = "🐂" if is_bull else "🐻" if is_bear else "⚖️"
        
        # Determine Market Grade
        if health_score >= 80:
            market_grade = "A+"
        elif health_score >= 65:
            market_grade = "A"
        elif health_score >= 50:
            market_grade = "B"
        elif health_score >= 35:
            market_grade = "C"
        else:
            market_grade = "D"
            
        bg_overlay = self._get_background_overlay(mood)
        
        content_html = f"""
        <div class="glass-card" style="padding: 35px; display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
          <div>
            <!-- Header Section -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
              <div>
                <div style="font-size: 20px; font-weight: 800; color: #B8C0D0; letter-spacing: 2px; text-transform: uppercase;">EOD Market Mood</div>
                <div style="font-size: 64px; font-weight: 900; color: {mood_color}; text-transform: uppercase; margin-top: 5px;">{mood_icon} {mood}</div>
              </div>
              <div style="text-align: center; background: rgba(255, 255, 255, 0.05); border: 2px solid {mood_color}; padding: 15px 25px; border-radius: 20px;">
                <div style="font-size: 14px; font-weight: 800; color: #B8C0D0; letter-spacing: 1px;">MARKET GRADE</div>
                <div style="font-size: 48px; font-weight: 950; color: {mood_color};">{market_grade}</div>
              </div>
            </div>
            
            <!-- Health Score Section -->
            <div style="margin-bottom: 30px; background: rgba(0, 0, 0, 0.2); padding: 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.04);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 22px; font-weight: 800; color: #ffffff;">MARKET HEALTH SCORE</span>
                <span style="font-size: 26px; font-weight: 900; color: {mood_color};">{health_score} / 100</span>
              </div>
              <div style="position: relative; width: 100%; height: 16px; background: rgba(255, 255, 255, 0.08); border-radius: 8px; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; width: {health_score}%; height: 100%; background: {mood_color}; box-shadow: 0 0 10px {mood_color};"></div>
              </div>
            </div>
            
            <!-- Key parameters grid -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px;">
              <div style="background: rgba(255, 255, 255, 0.02); padding: 15px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.04);">
                <div style="font-size: 13px; font-weight: 700; color: #718096; text-transform: uppercase;">FII vs DII Activity</div>
                <div style="font-size: 16px; font-weight: 700; color: #ffffff; margin-top: 4px;">{fii_vs_dii}</div>
              </div>
              <div style="background: rgba(255, 255, 255, 0.02); padding: 15px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.04);">
                <div style="font-size: 13px; font-weight: 700; color: #718096; text-transform: uppercase;">Smart Money Focus</div>
                <div style="font-size: 16px; font-weight: 700; color: #ffffff; margin-top: 4px;">{smart_money}</div>
              </div>
              <div style="background: rgba(255, 255, 255, 0.02); padding: 15px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.04);">
                <div style="font-size: 13px; font-weight: 700; color: #718096; text-transform: uppercase;">Risk Level</div>
                <div style="font-size: 16px; font-weight: 700; color: #ffffff; margin-top: 4px;">{risk_level}</div>
              </div>
              <div style="background: rgba(255, 255, 255, 0.02); padding: 15px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.04);">
                <div style="font-size: 13px; font-weight: 700; color: #718096; text-transform: uppercase;">Tomorrow Bias</div>
                <div style="font-size: 16px; font-weight: 700; color: #ffffff; margin-top: 4px;">{bias}</div>
              </div>
            </div>
          </div>
          
          <!-- Bottom Summary block -->
          <div style="background: rgba(212, 175, 55, 0.03); border-left: 4px solid #D4AF37; padding: 20px; border-radius: 4px 12px 12px 4px;">
            <div style="font-size: 15px; font-weight: 800; color: #D4AF37; text-transform: uppercase; margin-bottom: 5px; letter-spacing: 1px;">60-Second EOD Summary</div>
            <div style="font-size: 24px; line-height: 1.45; font-weight: 400; color: #f7fafc;">
              {summary}
            </div>
          </div>
        </div>
        """
        html = self._get_html_wrapper("Market In 10 Seconds", 1, bg_overlay, content_html)
        return self._render_html_to_image(html)

    def build_slide_2_strong(self, parsed: Dict[str, Any]) -> Image.Image:
        """Renders Slide 2: Where Smart Money Is Moving (Inflows vs Outflows)."""
        tracker = parsed.get("smart_money_tracker", {})
        moving_to = tracker.get("moving_to", "")
        exiting_from = tracker.get("exiting_from", "")
        reasoning = tracker.get("reasoning", "")
        
        fii_dii = parsed.get("fii_dii_intelligence", {})
        fii_flow = fii_dii.get("fii_net_flow_cr", 0)
        dii_flow = fii_dii.get("dii_net_flow_cr", 0)
        winner = fii_dii.get("winner", "")
        confidence = fii_dii.get("institutional_strength_score", 50)
        
        mood = parsed.get("scorecard", {}).get("market_mood", "Neutral")
        bg_overlay = self._get_background_overlay(mood)
        
        content_html = f"""
        <div class="glass-card" style="padding: 35px; display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
          <div>
            <!-- Smart Money Confidence Score Indicator -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; background: rgba(0, 0, 0, 0.2); padding: 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.04);">
              <div>
                <div style="font-size: 14px; font-weight: 800; color: #B8C0D0; letter-spacing: 1px; text-transform: uppercase;">Smart Money Tracker</div>
                <div style="font-size: 28px; font-weight: 900; color: #ffffff; margin-top: 5px;">FLOW CONFIDENCE</div>
              </div>
              <div style="text-align: right;">
                <div style="font-size: 40px; font-weight: 950; color: #00C853;">{confidence}%</div>
                <div style="font-size: 12px; color: #718096; font-weight: 700;">ACCUMULATION STRENGTH</div>
              </div>
            </div>
            
            <!-- Inflows Block -->
            <div style="background: rgba(0, 200, 83, 0.03); border: 1px solid rgba(0, 200, 83, 0.1); padding: 20px; border-radius: 16px; margin-bottom: 20px; display: flex; gap: 15px; align-items: flex-start;">
              <div style="font-size: 32px; line-height: 1;">🟢</div>
              <div>
                <div style="font-size: 14px; font-weight: 800; color: #00C853; text-transform: uppercase; letter-spacing: 1px;">Institutional Inflows (Accumulation)</div>
                <div style="font-size: 22px; font-weight: 700; color: #ffffff; margin-top: 5px;">{moving_to}</div>
              </div>
            </div>
            
            <!-- Outflows Block -->
            <div style="background: rgba(255, 82, 82, 0.03); border: 1px solid rgba(255, 82, 82, 0.1); padding: 20px; border-radius: 16px; margin-bottom: 25px; display: flex; gap: 15px; align-items: flex-start;">
              <div style="font-size: 32px; line-height: 1;">🔴</div>
              <div>
                <div style="font-size: 14px; font-weight: 800; color: #FF5252; text-transform: uppercase; letter-spacing: 1px;">Institutional Outflows (Distribution)</div>
                <div style="font-size: 22px; font-weight: 700; color: #ffffff; margin-top: 5px;">{exiting_from}</div>
              </div>
            </div>
          </div>
          
          <!-- Flow Stats & Reasoning -->
          <div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px; text-align: center; background: rgba(255, 255, 255, 0.02); padding: 15px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.04);">
              <div>
                <div style="font-size: 12px; font-weight: 700; color: #718096;">FII NET FLOW</div>
                <div style="font-size: 18px; font-weight: 800; color: { '#FF5252' if fii_flow < 0 else '#00C853' }; margin-top: 3px;">{fii_flow:,.2f} Cr</div>
              </div>
              <div>
                <div style="font-size: 12px; font-weight: 700; color: #718096;">DII NET FLOW</div>
                <div style="font-size: 18px; font-weight: 800; color: { '#FF5252' if dii_flow < 0 else '#00C853' }; margin-top: 3px;">+{dii_flow:,.2f} Cr</div>
              </div>
              <div>
                <div style="font-size: 12px; font-weight: 700; color: #718096;">FLOW WINNER</div>
                <div style="font-size: 18px; font-weight: 800; color: #D4AF37; margin-top: 3px;">{winner}</div>
              </div>
            </div>
            
            <div style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 15px; font-size: 20px; line-height: 1.45; font-weight: 400; color: #B8C0D0; font-style: italic;">
              " {reasoning} "
            </div>
          </div>
        </div>
        """
        html = self._get_html_wrapper("Where Smart Money Is Moving", 2, bg_overlay, content_html)
        return self._render_html_to_image(html)

    def build_slide_3_weak(self, parsed: Dict[str, Any]) -> Image.Image:
        """Renders Slide 3: Risks & Opportunities."""
        risks_opps = parsed.get("risks_opportunities", {})
        risks = risks_opps.get("risks", [])
        opportunities = risks_opps.get("opportunities", [])
        
        mood = parsed.get("scorecard", {}).get("market_mood", "Neutral")
        bg_overlay = self._get_background_overlay(mood)
        
        risks_html = ""
        for r in risks[:2]:
            risks_html += f"""
            <div style="margin-bottom: 15px;">
              <div style="font-size: 18px; font-weight: 800; color: #FF5252; text-transform: uppercase;">⚠️ {r.get('title', '')}</div>
              <div style="font-size: 16px; color: #e2e8f0; margin-top: 3px; line-height: 1.4;">{r.get('description', '')}</div>
            </div>
            """
            
        opps_html = ""
        for o in opportunities[:2]:
            opps_html += f"""
            <div style="margin-bottom: 15px;">
              <div style="font-size: 18px; font-weight: 800; color: #00C853; text-transform: uppercase;">💎 {o.get('title', '')}</div>
              <div style="font-size: 16px; color: #e2e8f0; margin-top: 3px; line-height: 1.4;">{o.get('description', '')}</div>
            </div>
            """
            
        content_html = f"""
        <div class="glass-card" style="padding: 35px; display: grid; grid-template-rows: auto 1fr; gap: 30px; height: 100%;">
          <div>
            <div style="font-size: 20px; font-weight: 800; color: #B8C0D0; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px;">Key Market Drivers</div>
            <div style="font-size: 38px; font-weight: 900; color: #ffffff;">RISKS & OPPORTUNITIES</div>
          </div>
          
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
            <!-- Risks Column -->
            <div style="border-left: 3px solid #FF5252; padding-left: 20px; display: flex; flex-direction: column; justify-content: flex-start;">
              <div style="font-size: 20px; font-weight: 900; color: #FF5252; letter-spacing: 1px; margin-bottom: 20px; text-transform: uppercase;">Threats & Risks</div>
              {risks_html}
            </div>
            
            <!-- Opportunities Column -->
            <div style="border-left: 3px solid #00C853; padding-left: 20px; display: flex; flex-direction: column; justify-content: flex-start;">
              <div style="font-size: 20px; font-weight: 900; color: #00C853; letter-spacing: 1px; margin-bottom: 20px; text-transform: uppercase;">Growth Areas</div>
              {opps_html}
            </div>
          </div>
        </div>
        """
        html = self._get_html_wrapper("Risks & Opportunities", 3, bg_overlay, content_html)
        return self._render_html_to_image(html)

    def build_slide_4_stocks(self, parsed: Dict[str, Any]) -> Image.Image:
        """Renders Slide 4: Tomorrow Levels & Options Data."""
        outlook = parsed.get("tomorrow_outlook", {})
        support = outlook.get("key_support", 24000)
        resistance = outlook.get("key_resistance", 24200)
        
        options = parsed.get("options_intelligence", {})
        pcr = options.get("pcr", 0.9)
        max_pain = options.get("max_pain", 24000)
        call_oi = options.get("highest_call_oi", 24200)
        put_oi = options.get("highest_put_oi", 23800)
        explanation = options.get("explanation", "")
        
        stocks = parsed.get("stocks_to_watch", [])
        
        mood = parsed.get("scorecard", {}).get("market_mood", "Neutral")
        bg_overlay = self._get_background_overlay(mood)
        
        # Technical classification for PCR
        if pcr < 0.6: pcr_class = "Oversold (Bullish trigger)"
        elif pcr > 1.4: pcr_class = "Overbought (Bearish trigger)"
        else: pcr_class = "Neutral / Balanced"
        
        watchlist_html = ""
        for s in stocks[:2]:
            trend_color = "#00C853" if "bull" in s.get("trend", "").lower() else "#FF5252" if "bear" in s.get("trend", "").lower() else "#D4AF37"
            watchlist_html += f"""
            <div style="background: rgba(255, 255, 255, 0.01); border: 1.5px solid rgba(255, 255, 255, 0.04); border-radius: 12px; padding: 15px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 5px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 20px; font-weight: 850; color: #D4AF37;">🔥 {s.get('symbol', '')}</span>
                <span style="font-size: 12px; font-weight: 800; background: rgba(0, 0, 0, 0.2); color: {trend_color}; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; border: 1px solid {trend_color}22;">{s.get('trend', 'Neutral')}</span>
              </div>
              <div style="font-size: 14px; color: #A0AEC0; font-weight: 600;">
                Support: <strong style="color: #ffffff;">₹{s.get('support', 0)}</strong> &nbsp;|&nbsp; Resistance: <strong style="color: #ffffff;">₹{s.get('resistance', 0)}</strong>
              </div>
              <div style="font-size: 14px; color: #e2e8f0; line-height: 1.4;">{s.get('reason_to_watch', '')}</div>
            </div>
            """
            
        content_html = f"""
        <div class="glass-card" style="padding: 35px; display: grid; grid-template-rows: auto 1fr; gap: 20px; height: 100%;">
          <div>
            <div style="font-size: 20px; font-weight: 800; color: #B8C0D0; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px;">Nifty & Watchlist Analysis</div>
            <div style="font-size: 38px; font-weight: 900; color: #ffffff;">TOMORROW LEVELS & OPTIONS</div>
          </div>
          
          <div style="display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 25px;">
            <!-- Left Side: Nifty & Options -->
            <div style="display: flex; flex-direction: column; justify-content: space-between;">
              <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); padding: 18px; border-radius: 16px; margin-bottom: 15px;">
                <div style="font-size: 14px; font-weight: 800; color: #B8C0D0; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px;">Nifty 50 Trading Range</div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <span style="font-size: 11px; color: #FF5252; font-weight: 700; display: block; text-transform: uppercase;">Key Support</span>
                    <span style="font-size: 26px; font-weight: 900; color: #ffffff;">{support}</span>
                  </div>
                  <div style="width: 1px; height: 35px; background: rgba(255,255,255,0.08);"></div>
                  <div style="text-align: right;">
                    <span style="font-size: 11px; color: #00C853; font-weight: 700; display: block; text-transform: uppercase;">Key Resistance</span>
                    <span style="font-size: 26px; font-weight: 900; color: #ffffff;">{resistance}</span>
                  </div>
                </div>
              </div>
              
              <div style="background: rgba(0, 0, 0, 0.2); padding: 18px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.04); flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between;">
                <div style="font-size: 13px; font-weight: 800; color: #D4AF37; text-transform: uppercase; margin-bottom: 8px;">Options Open Interest Data</div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px;">
                  <div><span style="color:#718096; font-weight:600;">PCR:</span> <strong style="color:#ffffff;">{pcr}</strong></div>
                  <div><span style="color:#718096; font-weight:600;">Max Pain:</span> <strong style="color:#ffffff;">{max_pain}</strong></div>
                  <div><span style="color:#718096; font-weight:600;">Call OI:</span> <strong style="color:#ffffff;">{call_oi}</strong></div>
                  <div><span style="color:#718096; font-weight:600;">Put OI:</span> <strong style="color:#ffffff;">{put_oi}</strong></div>
                </div>
                <div style="font-size: 11px; color:#B8C0D0; margin-top: 5px; font-style:italic;">PCR Status: {pcr_class}</div>
                <div style="margin-top: 10px; font-size: 14px; line-height: 1.4; color: #e2e8f0; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;">
                  {explanation}
                </div>
              </div>
            </div>
            
            <!-- Right Side: Watchlist -->
            <div style="display: flex; flex-direction: column;">
              <div style="font-size: 14px; font-weight: 800; color: #B8C0D0; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px;">Spotlight Stocks To Watch</div>
              {watchlist_html}
            </div>
          </div>
        </div>
        """
        html = self._get_html_wrapper("Tomorrow Levels & Watchlist", 4, bg_overlay, content_html)
        return self._render_html_to_image(html)

    def build_slide_5_outlook(self, parsed: Dict[str, Any]) -> Image.Image:
        """Renders Slide 5: AI Outlook, 'Why Should I Care' Blocks, and Educational Insight."""
        outlook = parsed.get("tomorrow_outlook", {})
        expected_mood = outlook.get("expected_mood", "Neutral")
        playbook = outlook.get("tomorrow_playbook", "")
        
        prob = parsed.get("ai_probability_engine", {})
        bull_p = prob.get("bullish_probability", 35)
        bear_p = prob.get("bearish_probability", 35)
        neut_p = prob.get("neutral_probability", 30)
        
        why_care = parsed.get("why_should_i_care", {})
        long_term = why_care.get("long_term_investors", "")
        swing = why_care.get("swing_traders", "")
        sip = why_care.get("sip_investors", "")
        beginners = why_care.get("beginners", "")
        
        edu = parsed.get("educational_insight", {}).get("concept", "")
        
        mood = parsed.get("scorecard", {}).get("market_mood", "Neutral")
        bg_overlay = self._get_background_overlay(mood)
        
        content_html = f"""
        <div class="glass-card" style="padding: 35px; display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
          <div>
            <!-- Probabilities header -->
            <div style="background: rgba(0, 0, 0, 0.2); padding: 15px 20px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.04); margin-bottom: 20px;">
              <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 800; margin-bottom: 8px;">
                <span style="color: #00C853;">🐂 BULLISH: {bull_p}%</span>
                <span style="color: #D4AF37;">⚖️ NEUTRAL: {neut_p}%</span>
                <span style="color: #FF5252;">🐻 BEARISH: {bear_p}%</span>
              </div>
              <div style="position: relative; width: 100%; height: 10px; background: rgba(255,255,255,0.08); border-radius: 5px; overflow: hidden; display: flex;">
                <div style="width: {bull_p}%; height: 100%; background: #00C853;"></div>
                <div style="width: {neut_p}%; height: 100%; background: #D4AF37;"></div>
                <div style="width: {bear_p}%; height: 100%; background: #FF5252;"></div>
              </div>
            </div>
            
            <!-- Expected Playbook -->
            <div style="margin-bottom: 20px;">
              <div style="font-size: 13px; font-weight: 800; color: #D4AF37; text-transform: uppercase; letter-spacing: 1px;">Outlook & Playbook ({expected_mood})</div>
              <div style="font-size: 16px; line-height: 1.45; font-weight: 450; color: #ffffff; margin-top: 4px;">
                {playbook}
              </div>
            </div>
            
            <!-- Why Should I Care Grid -->
            <div style="font-size: 13px; font-weight: 800; color: #B8C0D0; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">Why Should I Care?</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
              <div style="background: rgba(255,255,255,0.01); border: 1.5px solid rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <strong style="color: #60A5FA; display:block; font-size: 12px; text-transform:uppercase;">Long-Term</strong>
                <span style="color:#e2e8f0; font-size:12px; display:inline-block; margin-top:3px; line-height: 1.35;">{long_term}</span>
              </div>
              <div style="background: rgba(255,255,255,0.01); border: 1.5px solid rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <strong style="color: #F472B6; display:block; font-size: 12px; text-transform:uppercase;">Swing Traders</strong>
                <span style="color:#e2e8f0; font-size:12px; display:inline-block; margin-top:3px; line-height: 1.35;">{swing}</span>
              </div>
              <div style="background: rgba(255,255,255,0.01); border: 1.5px solid rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <strong style="color: #34D399; display:block; font-size: 12px; text-transform:uppercase;">SIP Investors</strong>
                <span style="color:#e2e8f0; font-size:12px; display:inline-block; margin-top:3px; line-height: 1.35;">{sip}</span>
              </div>
              <div style="background: rgba(255,255,255,0.01); border: 1.5px solid rgba(255,255,255,0.03); padding: 12px; border-radius: 8px;">
                <strong style="color: #FBBF24; display:block; font-size: 12px; text-transform:uppercase;">Beginners</strong>
                <span style="color:#e2e8f0; font-size:12px; display:inline-block; margin-top:3px; line-height: 1.35;">{beginners}</span>
              </div>
            </div>
          </div>
          
          <!-- Bottom Educational Block & CTA -->
          <div>
            <div style="background: rgba(59, 130, 246, 0.04); border-left: 4px solid #3B82F6; padding: 15px; border-radius: 4px 12px 12px 4px; margin-bottom: 15px;">
              <strong style="color: #3B82F6; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; display:block; margin-bottom: 3px;">📖 Daily Education Block</strong>
              <span style="font-size: 15px; line-height: 1.4; color: #cbd5e1;">{edu}</span>
            </div>
            
            <div style="text-align: center; font-size: 18px; font-weight: 800; color: #D4AF37; letter-spacing: 0.5px; background: rgba(212,175,55,0.04); border: 1px solid rgba(212,175,55,0.1); padding: 10px; border-radius: 8px;">
              🚀 Save for tomorrow's trading session. Follow @kknova.io
            </div>
          </div>
        </div>
        """
        html = self._get_html_wrapper("Tomorrow Outlook & Takeaway", 5, bg_overlay, content_html)
        return self._render_html_to_image(html)

    def generate_pdf_report(self, parsed: Dict[str, Any], portfolio_data: List[Dict[str, Any]] = None, watchlist_data: List[Dict[str, Any]] = None) -> bytes:
        """Compiles a professional, multi-page print-ready HTML report to PDF using Playwright."""
        # Extract metadata
        generated_time = parsed.get("data_freshness", {}).get("generated_time", datetime.datetime.now().strftime("%d %b %Y %H:%M IST"))
        freshness_rating = parsed.get("data_freshness", {}).get("freshness_rating", "HIGH")
        sources = ", ".join(parsed.get("source_attribution", {}).get("sources", ["Yahoo Finance", "NSE India", "BSE India"]))
        
        # Scorecard
        scorecard = parsed.get("scorecard", {})
        mood = scorecard.get("market_mood", "Neutral")
        health_score = scorecard.get("health_score", 50)
        one_line_summary = scorecard.get("one_line_summary", "")
        
        # Sectors
        strong_sectors = parsed.get("sector_rotation_intelligence", {}).get("top_performing_sectors", "")
        weak_sectors = parsed.get("sector_rotation_intelligence", {}).get("top_weak_sectors", "")
        rotation_reason = parsed.get("sector_rotation_intelligence", {}).get("rotation_reason", "")
        
        # Outlook & Playbook
        outlook = parsed.get("tomorrow_outlook", {})
        playbook = outlook.get("tomorrow_playbook", "")
        support = outlook.get("key_support", 24000)
        resistance = outlook.get("key_resistance", 24200)
        
        # Options
        options = parsed.get("options_intelligence", {})
        pcr = options.get("pcr", 0.9)
        max_pain = options.get("max_pain", 24000)
        
        # Why should I care
        why_care = parsed.get("why_should_i_care", {})
        
        # Educational insight
        edu = parsed.get("educational_insight", {}).get("concept", "")
        
        # Build portfolio table rows
        port_rows = ""
        if portfolio_data:
            for item in portfolio_data:
                port_rows += f"""
                <tr>
                  <td>{item.get("symbol", "N/A")}</td>
                  <td>{item.get("shares", 0)}</td>
                  <td>₹{item.get("buy_price", 0):.2f}</td>
                  <td>{item.get("sector", "N/A")}</td>
                </tr>
                """
        else:
            port_rows = "<tr><td colspan='4' class='empty-row'>No active portfolio holdings registered.</td></tr>"
            
        # Build watchlist table rows
        wl_rows = ""
        if watchlist_data:
            for item in watchlist_data:
                wl_rows += f"""
                <tr>
                  <td>{item.get("symbol", "N/A")}</td>
                  <td>{item.get("timestamp", "N/A")}</td>
                </tr>
                """
        else:
            wl_rows = "<tr><td colspan='2' class='empty-row'>No active watchlist counters.</td></tr>"

        html_report = f"""<!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
          @page {{
            size: letter;
            margin: 20mm;
          }}
          body {{
            font-family: 'Inter', sans-serif;
            color: #1a202c;
            background-color: #ffffff;
            line-height: 1.5;
            font-size: 10pt;
          }}
          .header {{
            border-bottom: 2px solid #1a365d;
            padding-bottom: 10px;
            margin-bottom: 20px;
          }}
          .header h1 {{
            font-size: 20pt;
            font-weight: 800;
            color: #1a365d;
            margin: 0;
            text-transform: uppercase;
          }}
          .header .subtitle {{
            font-size: 10pt;
            color: #718096;
            margin-top: 5px;
          }}
          .section-title {{
            font-size: 12pt;
            font-weight: 700;
            color: #1a365d;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 4px;
            margin-top: 20px;
            margin-bottom: 10px;
            text-transform: uppercase;
          }}
          .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
          }}
          .stats-card {{
            background: #f7fafc;
            border: 1px solid #edf2f7;
            border-radius: 6px;
            padding: 12px;
          }}
          .stats-card strong {{
            color: #4a5568;
            font-size: 9pt;
            text-transform: uppercase;
          }}
          .stats-value {{
            font-size: 14pt;
            font-weight: 700;
            margin-top: 4px;
          }}
          table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 9pt;
          }}
          th {{
            background-color: #2d3748;
            color: #ffffff;
            font-weight: 600;
            text-align: left;
            padding: 8px;
            border: 1px solid #2d3748;
          }}
          td {{
            padding: 8px;
            border: 1px solid #edf2f7;
          }}
          tr:nth-child(even) td {{
            background-color: #f7fafc;
          }}
          .empty-row {{
            text-align: center;
            color: #a0aec0;
            font-style: italic;
          }}
          .footer {{
            margin-top: 30px;
            border-top: 1px solid #e2e8f0;
            padding-top: 10px;
            font-size: 8pt;
            color: #a0aec0;
            text-align: center;
          }}
        </style>
        </head>
        <body>
          <div class="header">
            <h1>KKNova.io Market Brief</h1>
            <div class="subtitle">Generated: {generated_time} | Data Freshness: {freshness_rating} | Sources: {sources}</div>
          </div>
          
          <div class="section-title">EOD Market Sentiment</div>
          <div class="grid">
            <div class="stats-card">
              <strong>Market Mood</strong>
              <div class="stats-value" style="color: { '#00C853' if 'bull' in mood.lower() else '#FF5252' if 'bear' in mood.lower() else '#D4AF37' };">
                {mood.upper()}
              </div>
            </div>
            <div class="stats-card">
              <strong>Health Score</strong>
              <div class="stats-value">{health_score} / 100</div>
            </div>
          </div>
          
          <div style="margin-top: 15px; background: #f7fafc; padding: 15px; border-radius: 6px; border-left: 4px solid #D4AF37;">
            <strong>Executive EOD Summary:</strong>
            <p style="margin: 5px 0 0 0; font-size: 11pt; line-height: 1.4;">{one_line_summary}</p>
          </div>
          
          <div class="section-title">Sector Rotation & Smart Money Flow</div>
          <p><strong>Accumulation:</strong> {strong_sectors}</p>
          <p><strong>Distribution:</strong> {weak_sectors}</p>
          <p><strong>Flow Reasoning:</strong> {rotation_reason}</p>
          
          <div class="section-title">Trading Playbook & Outlook</div>
          <p><strong>Playbook:</strong> {playbook}</p>
          <p><strong>Levels:</strong> Support: <strong>{support}</strong> | Resistance: <strong>{resistance}</strong> | PCR: <strong>{pcr}</strong> | Max Pain: <strong>{max_pain}</strong></p>
          
          <div class="section-title">Why Should I Care?</div>
          <div style="font-size: 9pt; display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div><strong>Long Term:</strong> {why_care.get('long_term_investors', '')}</div>
            <div><strong>Swing Traders:</strong> {why_care.get('swing_traders', '')}</div>
            <div><strong>SIP Investors:</strong> {why_care.get('sip_investors', '')}</div>
            <div><strong>Beginners:</strong> {why_care.get('beginners', '')}</div>
          </div>
          
          <div class="section-title">Daily Educational Insight</div>
          <p style="font-style: italic; color: #4a5568;">{edu}</p>
          
          <div class="section-title">Holdings & Watchlist Snapshot</div>
          <div class="grid">
            <div>
              <h3 style="font-size: 10pt; margin: 5px 0;">Portfolio Valuation</h3>
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Shares</th>
                    <th>Buy Price</th>
                    <th>Sector</th>
                  </tr>
                </thead>
                <tbody>
                  {port_rows}
                </tbody>
              </table>
            </div>
            <div>
              <h3 style="font-size: 10pt; margin: 5px 0;">Active Watchlist</h3>
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Added Time</th>
                  </tr>
                </thead>
                <tbody>
                  {wl_rows}
                </tbody>
              </table>
            </div>
          </div>
          
          <div class="footer">
            KKNova Insight • Educational Content Only • Not Investment Advice
          </div>
        </body>
        </html>
        """
        
        pdf_bytes = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(html_report)
                page.wait_for_timeout(250)
                pdf_bytes = page.pdf(format="letter", print_background=True)
                browser.close()
        except Exception as e:
            logger.error(f"Playwright PDF generation failed: {e}", exc_info=True)
            pdf_bytes = f"PDF compilation failed due to Playwright error: {e}".encode("utf-8")
            
        return pdf_bytes
