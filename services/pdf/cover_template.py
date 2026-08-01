# -*- coding: utf-8 -*-
"""Fixed premium cover-page CSS matching the navy/gold corporate template."""

NAVY = "#102D5C"
GOLD = "#D4AF37"
LIGHT_GOLD = "#E9C46A"
CREAM = "#F7F3EA"
WHITE = "#FFFEF9"


def build_fixed_cover_css(cover_min_height: str = "250mm") -> str:
    """WeasyPrint-safe CSS for the locked cover (second-image template)."""
    return f"""
/* ===== FIXED PREMIUM COVER ===== */
.cover {{
  page-break-after: always;
  break-after: page;
  min-height: {cover_min_height};
  padding: 0.45cm;
  background: {CREAM};
  position: relative;
  box-sizing: border-box;
  overflow: hidden;
}}

/* Gold outer + navy inner double border */
.cover-frame {{
  position: relative;
  height: calc({cover_min_height} - 0.9cm);
  min-height: calc({cover_min_height} - 0.9cm);
  padding: 1.35cm 1.35cm 1.35cm;
  background: {CREAM};
  border: 3pt solid {GOLD};
  border-radius: 28px;
  box-shadow: inset 0 0 0 1.6pt {NAVY};
  box-sizing: border-box;
  overflow: hidden;
}}

/* Matching TR + BL corner ribbons (explicit mm top - WeasyPrint-safe) */
.cover-corner {{
  position: absolute;
  width: 24mm;
  height: 24mm;
  z-index: 5;
  overflow: hidden;
  pointer-events: none;
}}
.cover-corner svg {{
  display: block;
  width: 24mm;
  height: 24mm;
}}
.cover-corner-tr {{
  top: 0;
  right: 0;
}}
.cover-corner-bl {{
  /* bottom: is unreliable in WeasyPrint; pin with top from frame height */
  top: calc({cover_min_height} - 0.9cm - 24mm);
  left: 0;
}}

.cover-header {{
  text-align: center;
  margin: 0.05cm 0 0.7cm;
  position: relative;
  z-index: 2;
}}
.cover-company {{
  margin: 0;
  font-size: 20pt;
  font-weight: 800;
  letter-spacing: 3.5px;
  text-transform: uppercase;
  color: {NAVY};
  line-height: 1.2;
}}

/* Gold line + 4-point star center */
.cover-ornament {{
  margin: 12px auto 0;
  width: 210px;
  height: 16px;
  position: relative;
  text-align: center;
}}
.cover-ornament::before,
.cover-ornament::after {{
  content: "";
  position: absolute;
  top: 7px;
  width: 88px;
  height: 0;
  border-top: 1.15pt solid {GOLD};
}}
.cover-ornament::before {{ left: 0; }}
.cover-ornament::after {{ right: 0; }}
.cover-ornament .cover-star {{
  display: inline-block;
  width: 11px;
  height: 11px;
  margin-top: 2px;
  vertical-align: top;
}}

.cover-hero {{
  margin: 0.15cm auto 0.85cm;
  width: 90%;
  max-width: 545px;
  height: 195px;
  border-radius: 18px;
  border: 1.7pt solid {GOLD};
  background: #0a1f45;
  box-shadow: 0 10px 24px rgba(16, 45, 92, 0.16);
  overflow: hidden;
  text-align: center;
  position: relative;
  z-index: 2;
  box-sizing: border-box;
  padding: 0;
}}
/* Uploaded / photo heroes: letterbox on white stage so logo squares blend */
.cover-hero-upload {{
  padding: 10px;
  background: #FFFFFF;
}}
.cover .cover-hero-img,
.cover-hero-img {{
  display: block !important;
  width: 100% !important;
  height: 175px !important;
  max-width: 100% !important;
  max-height: 175px !important;
  object-fit: contain !important;
  object-position: center center !important;
  margin: 0 auto !important;
  padding: 0 !important;
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
  clip-path: none !important;
  image-rendering: auto;
}}
.cover-hero-svg {{
  display: block;
  width: 100%;
  height: 195px;
  margin: 0 auto;
}}

.cover-titles {{
  text-align: center;
  margin: 0.1cm 0 0;
  padding: 0 0.7cm;
  position: relative;
  z-index: 2;
}}
.cover-title,
.cover h1.cover-title,
.cover h1 {{
  font-size: 21pt !important;
  line-height: 1.18 !important;
  margin: 0 0 14px !important;
  font-weight: 800 !important;
  color: {NAVY} !important;
  border: none !important;
  padding: 0 !important;
  letter-spacing: -0.15px;
  text-align: center !important;
  background: transparent !important;
}}
.cover-ornament-after-title {{
  margin: 0 auto 14px;
}}
.cover-desc {{
  margin: 0 auto 0.55cm;
  max-width: 440px;
  font-size: 9.6pt;
  line-height: 1.55;
  color: {NAVY};
  font-weight: 500;
  text-align: center;
}}

.cover-rule {{
  width: 86%;
  max-width: 460px;
  margin: 0.15cm auto 0.75cm;
  height: 0;
  border: none;
  border-top: 0.9pt solid {GOLD};
  opacity: 0.85;
}}

.cover-meta-table,
.cover .cover-meta-table {{
  width: 86% !important;
  max-width: 470px !important;
  margin: 0 auto !important;
  border-collapse: collapse !important;
  border: none !important;
  background: transparent !important;
  table-layout: fixed !important;
  position: relative;
  z-index: 2;
}}
.cover-meta-table td,
.cover .cover-meta-table td {{
  width: 50% !important;
  vertical-align: top !important;
  padding: 0 10px 16px 0 !important;
  border: none !important;
  background: transparent !important;
}}
.cover-meta-table tr:nth-child(even) td,
.cover .cover-meta-table tr:nth-child(even) td {{
  background: transparent !important;
}}
.cover-meta-table td:last-child,
.cover .cover-meta-table td:last-child {{
  padding-right: 0 !important;
  padding-left: 10px !important;
}}
.cover-meta-icon {{
  display: inline-block;
  width: 28px;
  height: 28px;
  margin-right: 8px;
  border-radius: 7px;
  background: {GOLD} !important;
  text-align: center;
  line-height: 28px;
  vertical-align: top;
  border: none !important;
}}
.cover-meta-icon svg {{
  display: inline-block;
  vertical-align: middle;
  width: 14px;
  height: 14px;
}}
.cover-meta-text {{
  display: inline-block;
  vertical-align: top;
  max-width: calc(100% - 42px);
}}
.cover-meta-label {{
  font-size: 7.5pt;
  font-weight: 800;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: {NAVY};
  margin: 0 0 2px;
}}
.cover-meta-value {{
  font-size: 9.4pt;
  font-weight: 500;
  color: {NAVY};
  line-height: 1.3;
  word-break: break-word;
  opacity: 0.92;
}}

.cover-bottom {{
  text-align: center;
  margin-top: 1.6cm;
  padding-top: 0.2cm;
  position: relative;
  z-index: 2;
}}
.cover-copyright {{
  font-size: 8pt;
  color: {NAVY};
  letter-spacing: 0.15px;
  opacity: 0.85;
}}
"""
