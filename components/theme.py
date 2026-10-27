"""FinLife design system: CSS tokens (light / dark / system) and a Plotly layout that follows them."""
from __future__ import annotations

import plotly.graph_objects as go

LIGHT = dict(bg="#F4F8FF", surface="#FFFFFF", surface2="#EAF2FF", primary="#2563EB", on_primary="#FFFFFF",
             navy="#142B4A", accent="#60A5FA", text="#172B4D", muted="#64748B", border="#DCE6F3",
             good="#16A34A", warn="#D97706", bad="#DC2626", shadow="0 1px 2px rgba(20,43,74,.06),0 6px 18px rgba(20,43,74,.05)",
             hero="linear-gradient(135deg,#142B4A 0%,#1E3F78 55%,#2563EB 100%)")
DARK = dict(bg="#0B1220", surface="#111C2F", surface2="#17263D", primary="#60A5FA", on_primary="#0B1220",
            navy="#0E1A2E", accent="#60A5FA", text="#F1F5F9", muted="#A7B5CA", border="#263750",
            good="#4ADE80", warn="#FBBF24", bad="#F87171", shadow="0 1px 2px rgba(0,0,0,.4),0 8px 22px rgba(0,0,0,.25)",
            hero="linear-gradient(135deg,#0E1A2E 0%,#17315A 60%,#1E4FA8 100%)")


def _vars(t: dict, scheme: str) -> str:
    items = "".join(f"--{k.replace('_', '-')}:{v};" for k, v in t.items())
    return f"color-scheme:{scheme};{items}"


def theme_css(mode: str, auth_screen: bool = False) -> str:
    if mode == "dark":
        tokens = f":root{{{_vars(DARK, 'dark')}}}"
    elif mode == "light":
        tokens = f":root{{{_vars(LIGHT, 'light')}}}"
    else:  # system: follow the OS/browser preference
        tokens = f":root{{{_vars(LIGHT, 'light')}}}@media (prefers-color-scheme: dark){{:root{{{_vars(DARK, 'dark')}}}}}"
    extra = ".stApp{background:radial-gradient(1200px 500px at 50% -10%,var(--surface2),var(--bg) 70%)!important}" if auth_screen else ""
    return f"<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');{tokens}{BASE_CSS}{extra}</style>"


BASE_CSS = """
html,body,.stApp{font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif}
.stApp :is(p,li,label,button,input,textarea,select,h1,h2,h3,h4,h5,h6,td,th,summary,a,[data-testid="stMarkdownContainer"],.fl-card,.fl-hero,.fl-table){
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif}
.stApp{background:var(--bg);color:var(--text)}
[data-testid="stHeader"]{background:transparent}
#MainMenu,footer,[data-testid="stDecoration"],[data-testid="stToolbar"] [data-testid="stMainMenu"]{visibility:hidden}
.block-container{max-width:1240px;padding:2rem 1.5rem 4rem}
@media (max-width:640px){.block-container{padding:1rem .75rem 3rem}}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6,.stApp p,.stApp li,.stApp label,.stApp summary,
.stApp [data-testid="stWidgetLabel"] p,.stApp [data-testid="stCaptionContainer"]{color:var(--text)}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p{color:var(--muted)}
.stApp h1{font-weight:700;letter-spacing:-.02em;font-size:1.75rem}
.stApp h2,.stApp h3{font-weight:650;letter-spacing:-.01em}
a{color:var(--primary)}

/* sidebar */
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--border)}
[data-testid="stSidebarContent"]{padding-top:1rem}
[data-testid="stSidebar"] [data-testid^="stBaseButton-"]{width:100%;border:0;background:transparent;color:var(--text);
  font-weight:500;padding:.5rem .75rem;border-radius:10px;box-shadow:none;transition:background .15s,color .15s}
[data-testid="stSidebar"] [data-testid^="stBaseButton-"]>div{width:100%;justify-content:flex-start;text-align:left}
[data-testid="stSidebar"] [data-testid^="stBaseButton-"]:hover{background:var(--surface2);color:var(--primary)}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]{background:var(--surface2);box-shadow:inset 3px 0 0 var(--primary)}
.stApp [data-testid="stSidebar"] [data-testid="stBaseButton-primary"],.stApp [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] *{color:var(--primary);font-weight:650}
[data-testid="stSidebar"] [data-testid^="stBaseButton-"] *{color:inherit}

/* buttons */
[data-testid^="stBaseButton-"]{border-radius:10px;font-weight:600;transition:all .15s}
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"],[data-testid="stDownloadButton"] button,[data-testid="stBaseButton-headerNoPadding"]{
  background:var(--surface);color:var(--text);border:1px solid var(--border)}
.stApp [data-testid="stBaseButton-secondary"] *,.stApp [data-testid="stBaseButton-secondaryFormSubmit"] *,.stApp [data-testid="stDownloadButton"] button *{color:var(--text)}
[data-testid="stBaseButton-secondary"]:hover,[data-testid="stBaseButton-secondaryFormSubmit"]:hover,[data-testid="stDownloadButton"] button:hover{border-color:var(--primary)}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]{background:var(--primary);border:1px solid var(--primary);color:var(--on-primary)}
.stApp [data-testid="stBaseButton-primary"] *,.stApp [data-testid="stBaseButton-primaryFormSubmit"] *{color:var(--on-primary)}
[data-testid="stBaseButton-primary"]:hover,[data-testid="stBaseButton-primaryFormSubmit"]:hover{filter:brightness(1.08)}
[data-testid="stBaseButton-tertiary"]{border:0;background:transparent;padding:0 .25rem;font-weight:550}
.stApp [data-testid="stBaseButton-tertiary"],.stApp [data-testid="stBaseButton-tertiary"] *{color:var(--primary)}
[data-testid="stLinkButton"] a{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:10px;font-weight:600}
.stApp [data-testid="stLinkButton"] a *{color:var(--text)}
[data-testid^="stBaseButton-"]:focus-visible,[data-testid="stLinkButton"] a:focus-visible{outline:2px solid var(--primary);outline-offset:2px}

/* inputs (React Aria based in Streamlit >= 1.6x: hook on data-testid, not on library classes) */
[data-testid="stTextInputRootElement"],[data-testid="stNumberInputContainer"],[data-testid="stDateInputField"],
[data-testid="stTextAreaRootElement"],[data-testid="stSelectbox"] [role="group"],[data-testid="stMultiSelect"] [role="group"]{
  background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important}
[data-testid="stTextInputRootElement"] *,[data-testid="stNumberInputContainer"] input,[data-testid="stDateInputField"] *,
[data-testid="stTextAreaRootElement"] textarea,[data-testid="stSelectbox"] input,[data-testid="stMultiSelect"] input{
  color:var(--text)!important;-webkit-text-fill-color:var(--text);background:transparent!important}
input::placeholder,textarea::placeholder{color:var(--muted)!important;-webkit-text-fill-color:var(--muted);opacity:.8}
[data-testid="stSelectbox"] svg,[data-testid="stDateInputField"] svg,[data-testid="stNumberInput"] svg{color:var(--muted);fill:var(--muted)}
[data-testid="stNumberInputStepUp"],[data-testid="stNumberInputStepDown"]{background:var(--surface2)!important}
[data-testid="stTextInputRootElement"]:focus-within,[data-testid="stNumberInputContainer"]:focus-within,[data-testid="stSelectbox"] [role="group"]:focus-within{
  border-color:var(--primary)!important;box-shadow:0 0 0 2px color-mix(in srgb,var(--primary) 25%,transparent)}
[data-testid="stSelectboxVirtualDropdown"],[role="listbox"],[data-testid="stDateInputCalendar"],[role="dialog"]{background:var(--surface)!important;color:var(--text)!important}
[role="option"],[role="option"] *,[role="dialog"] *{color:var(--text)}
[role="option"]:hover,[role="option"][aria-selected="true"]{background:var(--surface2)!important}
[data-testid="stRadioOption"]>div>div:first-child{background:var(--surface)!important;border-color:var(--border)!important}
[data-testid="stRadioOption"][data-selected="true"]>div>div:first-child{background:var(--primary)!important;border-color:var(--primary)!important}
[data-testid="stCheckbox"] label>span:first-of-type,[data-testid="stToggle"] label>span:first-of-type{border-color:var(--border)}

/* tabs, forms, expanders, alerts */
[data-testid="stTab"],[data-testid="stTab"] *{color:var(--muted);font-weight:600}
[data-testid="stTab"][aria-selected="true"],[data-testid="stTab"][aria-selected="true"] *{color:var(--primary)}
[role="tablist"]{border-bottom:1px solid var(--border)}
[data-testid="stForm"]{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:1.1rem 1.2rem;box-shadow:var(--shadow)}
[data-testid="stExpander"] details{background:var(--surface);border:1px solid var(--border);border-radius:14px}
[data-testid="stExpander"] summary{font-weight:600}
[data-testid="stAlert"]{background:var(--surface2);border-radius:12px;border:1px solid var(--border)}
[data-testid="stAlert"] *{color:var(--text)!important}
div[role="dialog"]{background:var(--surface)!important;color:var(--text)}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:.9rem 1rem}
[data-testid="stMetricValue"],[data-testid="stMetricLabel"] *{color:var(--text)!important}
hr{border-color:var(--border)}
[data-testid="stPlotlyChart"]{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:.4rem;box-shadow:var(--shadow)}

/* plotly text/grid follow the theme even in 'system' mode */
.js-plotly-plot .plotly text{fill:var(--text)!important}
.js-plotly-plot .plotly .gridlayer path,.js-plotly-plot .plotly .zerolinelayer path{stroke:var(--border)!important}
.js-plotly-plot .plotly .xtick text,.js-plotly-plot .plotly .ytick text,.js-plotly-plot .plotly .legendtext{fill:var(--muted)!important}

/* FinLife components */
.fl-num{font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.fl-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:1.05rem 1.15rem;box-shadow:var(--shadow);color:var(--text)}
.fl-kpi-label{color:var(--muted);font-size:.82rem;font-weight:550}
.fl-kpi-value{font-size:1.65rem;font-weight:700;margin:.25rem 0 .2rem;line-height:1.15}
.fl-kpi-note{color:var(--muted);font-size:.78rem}
.fl-delta{display:inline-block;font-size:.76rem;font-weight:650;padding:.1rem .45rem;border-radius:999px;margin-right:.35rem}
.fl-up{color:var(--good);background:color-mix(in srgb,var(--good) 14%,transparent)}
.fl-down{color:var(--bad);background:color-mix(in srgb,var(--bad) 14%,transparent)}
.fl-flat{color:var(--muted);background:var(--surface2)}
.fl-good{color:var(--good)}.fl-warn{color:var(--warn)}.fl-bad{color:var(--bad)}.fl-muted{color:var(--muted)}
.fl-hero{background:var(--hero);color:#fff;border-radius:20px;padding:1.6rem 1.8rem;box-shadow:var(--shadow)}
.fl-hero *{color:#fff}
.fl-hero-label{opacity:.8;font-size:.9rem;font-weight:550}
.fl-hero-value{font-size:2.5rem;font-weight:700;letter-spacing:-.025em;margin:.2rem 0 .5rem;line-height:1.1}
.fl-hero-row{display:flex;gap:2rem;flex-wrap:wrap;margin-top:.9rem}
.fl-hero-row div div:first-child{opacity:.75;font-size:.78rem}
.fl-hero-row div div:last-child{font-weight:650;font-size:1.05rem}
.fl-bar{height:9px;border-radius:99px;background:var(--surface2);overflow:hidden;margin:.45rem 0 .25rem}
.fl-bar>div{height:100%;border-radius:99px;transition:width .4s}
.fl-row{display:flex;justify-content:space-between;align-items:baseline;gap:.75rem}
.fl-title{font-weight:650;font-size:1.02rem;margin:0 0 .15rem}
.fl-pill{display:inline-block;font-size:.72rem;font-weight:650;padding:.12rem .55rem;border-radius:999px;background:var(--surface2);color:var(--primary)}
.fl-empty{text-align:center;padding:2.6rem 1.2rem}
.fl-empty .fl-title{font-size:1.2rem}
.fl-brand{display:flex;align-items:center;gap:.6rem;font-weight:700;font-size:1.25rem;color:var(--text)}
.fl-logo{width:34px;height:34px;border-radius:10px;background:var(--hero);display:inline-flex;align-items:center;justify-content:center}
.fl-table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:14px;background:var(--surface)}
.fl-table{width:100%;border-collapse:collapse;font-size:.88rem;color:var(--text)}
.fl-table th{text-align:left;font-weight:600;color:var(--muted);padding:.6rem .8rem;border-bottom:1px solid var(--border);white-space:nowrap;background:var(--surface2)}
.fl-table td{padding:.55rem .8rem;border-bottom:1px solid var(--border);white-space:nowrap}
.fl-table tr:last-child td{border-bottom:0}
.fl-table td.r,.fl-table th.r{text-align:right}
.fl-insight{border-left:3px solid var(--primary);padding:.15rem 0 .15rem .8rem;margin:.6rem 0}
.fl-insight.good{border-color:var(--good)}.fl-insight.warn{border-color:var(--warn)}
@media (max-width:640px){.fl-hero-value{font-size:2rem}.fl-kpi-value{font-size:1.4rem}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def plotly_layout(fig: go.Figure, height: int = 340, legend: bool = True) -> go.Figure:
    """Transparent, theme-neutral layout. Text and grid colours come from CSS variables (see BASE_CSS)."""
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12), showlegend=legend,
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#142B4A", font=dict(color="#FFFFFF", family="Inter, sans-serif"), bordercolor="#60A5FA"),
        colorway=["#2563EB", "#60A5FA", "#16A34A", "#D97706", "#8B5CF6", "#DC2626", "#14B8A6"])
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,.25)", zeroline=False)
    return fig
