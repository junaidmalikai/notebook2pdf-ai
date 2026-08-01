"""Shared Streamlit CSS - preserves the existing AL-Junaid visual language."""

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;0,700;1,400&family=Syne:wght@400;600&family=JetBrains+Mono:wght@300;400&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');

:root{
  --bg:#080e17; --panel:#0e1a28; --border:rgba(180,145,60,.22);
  --gold:#c8a84a; --gold2:#e6c96e; --cream:#ede5cf;
  --dim:rgba(237,229,207,.38); --green:#3aad6e; --red:#c0564a;
  --icon-gold:#C0A060;
  --mono:'JetBrains Mono',monospace;
  --serif:'Fraunces',serif; --sans:'Syne',sans-serif;
}
html,body,[data-testid="stAppViewContainer"]{
  background:var(--bg) !important; font-family:var(--sans); color:var(--cream) !important;
}
[data-testid="stHeader"]{background:transparent !important;}
/* Hide Streamlit chrome, but keep the expand-sidebar control visible + gold */
#MainMenu, footer {visibility:hidden;}
header [data-testid="stDecoration"] {display:none;}
header [data-testid="stToolbar"]{
  visibility:visible !important;
}
/* Hide toolbar children by default… */
header [data-testid="stToolbar"] > *{
  visibility:hidden;
}
/* …except the expand-sidebar button (shown when sidebar is collapsed) */
header [data-testid="stToolbar"] [data-testid="stExpandSidebarButton"],
header [data-testid="stToolbar"] [data-testid="stExpandSidebarButton"] *{
  visibility:visible !important;
  color:#C0A060 !important;
  fill:#C0A060 !important;
  stroke:#C0A060 !important;
}
[data-testid="stMainBlockContainer"]{max-width:860px;margin:0 auto;padding:0 1.6rem 6rem;}

section[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0a121c 0%,#0e1a28 100%) !important;
  border-right:1px solid rgba(180,145,60,.18) !important;
}
/* Apply Syne to sidebar text, but NEVER override Material icon fonts */
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p{
  font-family:var(--sans);
  color:var(--cream) !important;
}
section[data-testid="stSidebar"] label{
  color:var(--cream) !important;
}

/* ---- Material / Streamlit icons (sidebar toggle + password eye) ---- */
[data-testid="stIconMaterial"],
span[data-testid="stIconMaterial"],
.material-icons,
.material-symbols-outlined,
.material-symbols-rounded{
  font-family:'Material Symbols Outlined','Material Symbols Rounded','Material Icons' !important;
  font-weight:400 !important;
  font-style:normal !important;
  font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24 !important;
  letter-spacing:normal !important;
  text-transform:none !important;
  display:inline-block !important;
  line-height:1 !important;
  -webkit-font-smoothing:antialiased;
  color:#C0A060 !important;
}

/*
 * Sidebar open + closed toggle icons MUST stay #C0A060.
 * Collapse control lives in the sidebar; expand control lives in stToolbar
 * when the sidebar is hidden (Streamlit 1.60: stExpandSidebarButton).
 */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"] *,
[data-testid="collapsedControl"],
[data-testid="collapsedControl"] *,
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] *,
[data-testid="stBaseButton-headerNoPadding"],
[data-testid="stBaseButton-headerNoPadding"] *,
[data-testid="baseButton-headerNoPadding"],
[data-testid="baseButton-headerNoPadding"] *,
button[kind="headerNoPadding"],
button[kind="headerNoPadding"] *,
button[kind="header"],
button[kind="header"] *{
  color:#C0A060 !important;
  fill:#C0A060 !important;
  stroke:#C0A060 !important;
}

/* Beat Streamlit emotion fadedText60 on the Material icon inside expand btn */
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] span,
[data-testid="stSidebarCollapseButton"] span{
  color:#C0A060 !important;
  font-family:'Material Symbols Outlined','Material Icons' !important;
  opacity:1 !important;
}

[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg,
[data-testid="collapsedControl"] svg,
button[kind="headerNoPadding"] svg{
  color:#C0A060 !important;
}
[data-testid="stSidebarCollapseButton"] svg *,
[data-testid="stExpandSidebarButton"] svg *,
[data-testid="collapsedControl"] svg *,
button[kind="headerNoPadding"] svg *{
  fill:#C0A060 !important;
  stroke:#C0A060 !important;
  color:#C0A060 !important;
}

/* Password visibility toggle */
[data-testid="stTextInput"] button,
[data-testid="stTextInput"] button span,
[data-testid="stTextInput"] [data-testid="stIconMaterial"]{
  color:#C0A060 !important;
  font-family:'Material Symbols Outlined','Material Icons' !important;
}

.hero{text-align:center;padding:3.2rem 0 1.4rem;}
.hero-eyebrow{font-family:var(--mono);font-size:.65rem;letter-spacing:5px;text-transform:uppercase;color:var(--gold);margin-bottom:1rem;}
.hero-name{font-family:var(--serif);font-size:3.2rem;font-weight:700;color:var(--cream);line-height:.95;text-shadow:0 0 60px rgba(200,168,74,.18);}
.hero-name em{color:var(--gold);font-style:italic;}
.hero-rule{width:1px;height:48px;background:linear-gradient(180deg,transparent,var(--gold),transparent);margin:1.4rem auto;}
.hero-title{font-family:var(--serif);font-size:1.25rem;font-weight:300;color:var(--cream);}
.hero-sub{font-family:var(--mono);font-size:.68rem;color:var(--dim);letter-spacing:1.5px;margin-top:.5rem;}
.hero-desc{font-family:var(--sans);font-size:.95rem;line-height:1.55;color:var(--cream);opacity:.88;max-width:42rem;margin:0 auto;font-weight:400;}
.hero-desc + .hero-desc{margin-top:.85rem;opacity:.72;}

.steps{display:flex;gap:.7rem;margin:1.6rem 0 0;flex-wrap:wrap;}
.step{flex:1;min-width:110px;border:1px solid var(--border);border-radius:10px;padding:.8rem .6rem;text-align:center;background:rgba(200,168,74,.03);}
.step-n{font-family:var(--serif);font-size:1.4rem;color:var(--gold);line-height:1;}
.step-t{font-family:var(--mono);font-size:.6rem;color:var(--dim);letter-spacing:.4px;margin-top:5px;line-height:1.45;}

.pane{background:linear-gradient(160deg,#0e1a28,#111e30);border:1px solid var(--border);border-radius:14px;padding:1.6rem 1.8rem;margin:1.2rem 0;box-shadow:0 12px 48px rgba(0,0,0,.55),inset 0 1px 0 rgba(200,168,74,.07);}
.pane-lbl{font-family:var(--mono);font-size:.62rem;letter-spacing:3.5px;text-transform:uppercase;color:var(--gold);margin-bottom:1rem;}

[data-testid="stFileUploader"]{background:rgba(200,168,74,.03) !important;border:1.5px dashed rgba(200,168,74,.3) !important;border-radius:10px !important;}
[data-testid="stFileUploaderDropzoneInstructions"] p,[data-testid="stFileUploader"] label{color:var(--dim) !important;font-family:var(--mono) !important;font-size:.76rem !important;}

.fbadge{margin-top:.8rem;padding:.5rem 1rem;background:rgba(200,168,74,.06);border:1px solid rgba(200,168,74,.2);border-radius:6px;font-family:var(--mono);font-size:.74rem;color:var(--dim);display:flex;align-items:center;gap:.5rem;}
.fbadge strong{color:var(--cream);}

.stButton>button{width:100% !important;background:linear-gradient(120deg,#a8782c,#c8a84a,#dfc070) !important;color:#080e17 !important;font-family:var(--sans) !important;font-weight:600 !important;font-size:.78rem !important;letter-spacing:2px !important;text-transform:uppercase !important;border:none !important;border-radius:8px !important;padding:.8rem 1.4rem !important;margin-top:.55rem !important;box-shadow:0 4px 24px rgba(200,168,74,.3) !important;}
[data-testid="stDownloadButton"]>button{width:100% !important;background:transparent !important;color:var(--gold) !important;font-family:var(--sans) !important;font-size:.75rem !important;letter-spacing:1.5px !important;text-transform:uppercase !important;border:1px solid rgba(200,168,74,.38) !important;border-radius:8px !important;padding:.75rem 1.2rem !important;margin-top:.45rem !important;}

.terminal{background:#040b12;border:1px solid rgba(200,168,74,.14);border-radius:10px;padding:1.1rem 1.3rem;font-family:var(--mono);font-size:.73rem;color:rgba(237,229,207,.65);min-height:88px;max-height:280px;overflow-y:auto;line-height:2;}
.l-tool{color:#5ec4e8;} .l-obs{color:#5dd68c;} .l-err{color:#e07070;}
.l-info{color:rgba(237,229,207,.4);} .l-ans{color:var(--gold2);font-weight:600;}
.l-ts{color:rgba(200,168,74,.35);font-size:.64rem;margin-right:.5rem;}

.r-box{border-radius:10px;padding:1.2rem 1.4rem;margin:1rem 0;}
.r-ok{background:rgba(58,173,110,.1);border:1px solid rgba(58,173,110,.38);}
.r-err{background:rgba(192,86,74,.1);border:1px solid rgba(192,86,74,.35);}
.r-warn{background:rgba(200,168,74,.08);border:1px solid rgba(200,168,74,.3);}
.r-ttl{font-family:var(--serif);font-size:1.05rem;font-weight:700;margin-bottom:.3rem;}
.r-ok .r-ttl{color:#7ee8a8;} .r-err .r-ttl{color:#e8a0a0;} .r-warn .r-ttl{color:var(--gold2);}
.r-bod{font-family:var(--mono);font-size:.73rem;color:var(--dim);line-height:1.8;}

.ai-status{font-family:var(--mono);font-size:.72rem;padding:.55rem .75rem;border-radius:8px;margin:.4rem 0 .8rem;border:1px solid rgba(180,145,60,.2);}
.ai-ok{background:rgba(58,173,110,.12);color:#7ee8a8;}
.ai-bad{background:rgba(192,86,74,.12);color:#e8a0a0;}
.ai-idle{background:rgba(200,168,74,.06);color:var(--dim);}

.pgfoot{text-align:center;margin-top:3.5rem;padding-top:1.2rem;border-top:1px solid rgba(200,168,74,.09);font-family:var(--mono);font-size:.65rem;color: #f8f9fa;letter-spacing:1.5px;}
@keyframes fu{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:translateY(0);}}
.ani{animation:fu .5s ease both;}
</style>
"""


def inject_css() -> None:
    import streamlit as st

    st.markdown(APP_CSS, unsafe_allow_html=True)
