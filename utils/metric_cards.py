"""
Metric Cards Component for Bio Dashboard
Design: Operation-Focused Dashboard Cards (Light Theme)
Features:
- Border color indicates metric type
- Trend comparison: Day, Week, Month
- Status badges (OK/WARNING/CRITICAL)
- Progress bars for targets
- Alert mode for items requiring action
- Quick action links
"""
import streamlit as st
from typing import Optional, Literal, Union
from datetime import date, timedelta


# Color definitions
BORDER_COLORS = {
    "info": "#3B82F6",      # Blue - general info
    "success": "#16a34a",   # Green - good values
    "warning": "#f59e0b",   # Yellow/Orange - warning
    "danger": "#dc2626",    # Red - bad values / needs attention
}

# Background colors for alert states (light theme)
BG_COLORS = {
    "normal": "#ffffff",
    "warning": "#fffbeb",   # Light yellow tint
    "critical": "#fef2f2",  # Light red tint
}

# Status badge colors and labels (light theme)
STATUS_CONFIG = {
    "ok": {"color": "#16a34a", "bg": "#dcfce7", "label": "ปกติ", "icon": "✓"},
    "warning": {"color": "#b45309", "bg": "#fef3c7", "label": "เตือน", "icon": "!"},
    "critical": {"color": "#dc2626", "bg": "#fee2e2", "label": "วิกฤต", "icon": "!!"},
    "none": {"color": "#6b7280", "bg": "#f3f4f6", "label": "-", "icon": ""},
}

# Icons for metric types
METRIC_ICONS = {
    "card": "🎴",
    "serial": "📊",
    "delivery": "🚚",
    "center": "🏢",
    "complete": "✅",
    "incomplete": "📝",
    "error": "❌",
    "warning": "⚠️",
    "permit": "🪪",
    "appointment": "📅",
    "checkin": "✔️",
    "noshow": "🚫",
    "sla": "⏱️",
    "percent": "📈",
    "count": "🔢",
    "forecast": "📆",
    "capacity": "📦",
    "target": "🎯",
    "alert": "🔔",
    "action": "⚡",
}


def get_trend_arrow(value: float) -> tuple[str, str]:
    """Get trend arrow and color based on value."""
    if value > 0:
        return "▲", "#16a34a"  # Green up
    elif value < 0:
        return "▼", "#dc2626"  # Red down
    else:
        return "—", "#6b7280"  # Gray neutral


def get_trend_arrow_inverse(value: float) -> tuple[str, str]:
    """Get trend arrow for metrics where down is good (e.g., errors)."""
    if value > 0:
        return "▲", "#dc2626"  # Red up (bad)
    elif value < 0:
        return "▼", "#16a34a"  # Green down (good)
    else:
        return "—", "#6b7280"  # Gray neutral


def format_number(value: Union[int, float], is_percent: bool = False) -> str:
    """Format number with thousand separators or percentage."""
    if is_percent:
        return f"{value:.1f}%"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def format_trend(value: float, is_percent: bool = False) -> str:
    """Format trend value with + or - sign."""
    sign = "+" if value > 0 else ""
    if is_percent:
        return f"{sign}{value:.1f}%"
    return f"{sign}{value:,.0f}"


def render_metric_card(
    label: str,
    value: Union[int, float],
    icon: str = "count",
    card_type: Literal["info", "success", "warning", "danger"] = "info",
    trend_day: Optional[float] = None,
    trend_week: Optional[float] = None,
    trend_month: Optional[float] = None,
    is_percent: bool = False,
    inverse_trend: bool = False,
    help_text: Optional[str] = None,
    # New operation-focused parameters
    status: Optional[Literal["ok", "warning", "critical"]] = None,
    target: Optional[Union[int, float]] = None,
    target_label: Optional[str] = None,
    action_label: Optional[str] = None,
    action_page: Optional[str] = None,
    alert: bool = False,
    subtitle: Optional[str] = None,
):
    """
    Render a metric card with border accent style.

    New Operation-focused features:
    - status: Shows a badge (ok/warning/critical)
    - target: Shows a progress bar towards target
    - target_label: Custom label for target (e.g., "เป้าหมาย", "Capacity")
    - action_label: Button text for quick action
    - action_page: Page to navigate on action click
    - alert: Highlight card for items requiring attention
    - subtitle: Additional context line below value
    """
    border_color = BORDER_COLORS.get(card_type, BORDER_COLORS["info"])
    icon_char = METRIC_ICONS.get(icon, "📊")

    # Determine background based on alert state
    if alert and card_type == "danger":
        bg_color = BG_COLORS["critical"]
    elif alert and card_type == "warning":
        bg_color = BG_COLORS["warning"]
    else:
        bg_color = BG_COLORS["normal"]

    # Build trend HTML
    trend_html = ""
    trend_parts = []

    get_arrow = get_trend_arrow_inverse if inverse_trend else get_trend_arrow

    if trend_day is not None:
        arrow, color = get_arrow(trend_day)
        trend_parts.append(f'<span style="color:{color}">{arrow} {format_trend(trend_day, is_percent)} วัน</span>')

    if trend_week is not None:
        arrow, color = get_arrow(trend_week)
        trend_parts.append(f'<span style="color:{color}">{arrow} {format_trend(trend_week, is_percent)} สัปดาห์</span>')

    if trend_month is not None:
        arrow, color = get_arrow(trend_month)
        trend_parts.append(f'<span style="color:{color}">{arrow} {format_trend(trend_month, is_percent)} เดือน</span>')

    if trend_parts:
        trend_html = f'<div style="font-size:0.7rem;color:#6b7280;margin-top:6px">{" | ".join(trend_parts)}</div>'

    # Build status badge HTML
    status_html = ""
    if status:
        cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["none"])
        status_html = f'<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:10px;font-size:0.65rem;font-weight:600;background:{cfg["bg"]};color:{cfg["color"]}">{cfg["icon"]} {cfg["label"]}</span>'

    # Build subtitle HTML
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<div style="font-size:0.75rem;color:#6b7280;margin-top:2px">{subtitle}</div>'

    # Build progress bar HTML (for target comparison)
    progress_html = ""
    if target is not None and target > 0:
        pct = min((value / target) * 100, 100)
        pct_display = (value / target) * 100
        bar_color = "#16a34a" if pct_display <= 80 else ("#f59e0b" if pct_display <= 100 else "#dc2626")
        tlabel = target_label or "เป้าหมาย"
        progress_html = f'<div style="margin-top:8px"><div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#6b7280;margin-bottom:3px"><span>{tlabel}</span><span>{pct_display:.0f}% ({format_number(target)})</span></div><div style="background:#e5e7eb;border-radius:4px;height:6px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{bar_color};border-radius:4px;transition:width 0.3s"></div></div></div>'

    # Help tooltip
    help_attr = f'title="{help_text}"' if help_text else ''

    # Alert animation style
    alert_style = "animation:pulse 2s infinite;" if alert else ""

    # Build header with icon and status badge
    header_html = f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px"><span style="font-size:1.5rem">{icon_char}</span>{status_html}</div>'

    # Single line HTML to avoid Streamlit parsing issues
    card_html = f'<div {help_attr} style="background:{bg_color};border-radius:8px;padding:16px 20px;border-left:4px solid {border_color};border-top:1px solid #e5e7eb;border-right:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.1);{alert_style}transition:transform 0.2s,box-shadow 0.2s;">{header_html}<div style="font-size:1.75rem;font-weight:700;color:#1f2937;line-height:1.2">{format_number(value, is_percent)}</div><div style="font-size:0.85rem;color:#6b7280;margin-top:2px">{label}</div>{subtitle_html}{trend_html}{progress_html}</div>'

    st.markdown(card_html, unsafe_allow_html=True)

    # Render action button separately (Streamlit buttons can't be in HTML)
    if action_label and action_page:
        st.page_link(action_page, label=f"➡️ {action_label}", use_container_width=True)


def render_metric_row(metrics: list[dict], columns: int = 4):
    """
    Render a row of metric cards.
    """
    cols = st.columns(columns)
    for i, metric in enumerate(metrics):
        with cols[i % columns]:
            render_metric_card(**metric)


def calculate_trend(
    current: Union[int, float],
    previous: Union[int, float],
    as_percent: bool = False
) -> Optional[float]:
    """
    Calculate trend as absolute change (default) or percentage.
    Returns None only if both current and previous are 0.
    """
    if current == 0 and previous == 0:
        return None

    if as_percent and previous != 0:
        return ((current - previous) / previous) * 100
    else:
        return current - previous


# CSS for metric cards (inject once)
METRIC_CARDS_CSS = """
<style>
.metric-card-row {
    display: flex;
    gap: 16px;
    margin-bottom: 16px;
}

.metric-card-row > div {
    flex: 1;
}

@media (max-width: 768px) {
    .metric-card-row {
        flex-direction: column;
    }
}

/* Pulse animation for alert cards */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.85; }
}

/* Operation Summary Panel */
.op-summary-panel {
    background: linear-gradient(135deg, #f8fafc, #f1f5f9);
    border-radius: 8px;
    padding: 24px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    margin-bottom: 24px;
}

.op-summary-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e5e7eb;
}

.op-summary-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #1f2937;
    display: flex;
    align-items: center;
    gap: 10px;
}

.op-summary-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}

.op-summary-badge.ok {
    background: #dcfce7;
    color: #16a34a;
}

.op-summary-badge.warning {
    background: #fef3c7;
    color: #b45309;
}

.op-summary-badge.critical {
    background: #fee2e2;
    color: #dc2626;
}

/* Quick Stat */
.quick-stat {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #ffffff;
    border-radius: 8px;
    border-left: 3px solid #3B82F6;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.quick-stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1f2937;
}

.quick-stat-label {
    font-size: 0.8rem;
    color: #6b7280;
}
</style>
"""


def inject_metric_cards_css():
    """Inject CSS for metric cards (call once at page load)."""
    st.markdown(METRIC_CARDS_CSS, unsafe_allow_html=True)


def render_mini_metric(
    label: str,
    value: Union[int, float],
    trend: Optional[float] = None,
    card_type: Literal["info", "success", "warning", "danger"] = "info",
    is_percent: bool = False,
    inverse_trend: bool = False,
):
    """
    Render a compact metric card (for dense dashboards).
    """
    border_color = BORDER_COLORS.get(card_type, BORDER_COLORS["info"])

    trend_html = ""
    if trend is not None:
        get_arrow = get_trend_arrow_inverse if inverse_trend else get_trend_arrow
        arrow, color = get_arrow(trend)
        trend_html = f'<span style="color:{color};font-size:0.75rem;margin-left:8px">{arrow} {format_trend(trend, is_percent)}</span>'

    card_html = f'<div style="background:#ffffff;border-radius:8px;padding:12px 16px;border-left:3px solid {border_color};border-top:1px solid #e5e7eb;border-right:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;box-shadow:0 1px 2px rgba(0,0,0,0.05)"><div style="font-size:0.75rem;color:#6b7280;margin-bottom:4px">{label}</div><div style="font-size:1.25rem;font-weight:600;color:#1f2937">{format_number(value, is_percent)}{trend_html}</div></div>'

    st.markdown(card_html, unsafe_allow_html=True)


def render_operation_summary(
    title: str = "สรุปสถานะการดำเนินงาน",
    overall_status: Literal["ok", "warning", "critical"] = "ok",
    status_message: str = "",
    metrics: list[dict] = None,
    alerts: list[dict] = None,
    last_updated: str = None,
):
    """
    Render an Operation Summary Panel at the top of the page.

    Parameters:
    - title: Panel title
    - overall_status: ok/warning/critical
    - status_message: Message next to status badge
    - metrics: List of quick metrics [{label, value, icon?}]
    - alerts: List of alerts [{message, type, action_label?, action_page?}]
    - last_updated: Timestamp string
    """
    cfg = STATUS_CONFIG.get(overall_status, STATUS_CONFIG["ok"])

    # Build metrics HTML (single line for each)
    metrics_html = ""
    if metrics:
        metrics_items = []
        for m in metrics[:6]:  # Max 6 quick metrics
            icon = METRIC_ICONS.get(m.get("icon", "count"), "📊")
            metrics_items.append(f'<div style="text-align:center;padding:8px 16px"><div style="font-size:0.7rem;color:#6b7280">{icon} {m.get("label", "")}</div><div style="font-size:1.25rem;font-weight:700;color:#1f2937">{format_number(m.get("value", 0))}</div></div>')
        metrics_html = f'<div style="display:flex;flex-wrap:wrap;justify-content:space-around;gap:8px;margin-top:16px">{"".join(metrics_items)}</div>'

    # Build alerts HTML (single line for each)
    alerts_html = ""
    if alerts and len(alerts) > 0:
        alert_items = []
        for a in alerts[:3]:  # Max 3 alerts
            atype = a.get("type", "warning")
            acfg = STATUS_CONFIG.get(atype, STATUS_CONFIG["warning"])
            alert_items.append(f'<div style="display:flex;align-items:center;gap:8px;padding:10px 14px;background:{acfg["bg"]};border-radius:8px;border-left:3px solid {acfg["color"]}"><span style="font-size:1.1rem">{acfg["icon"]}</span><span style="flex:1;font-size:0.85rem;color:{acfg["color"]}">{a.get("message", "")}</span></div>')
        alerts_html = f'<div style="display:flex;flex-direction:column;gap:8px;margin-top:16px">{"".join(alert_items)}</div>'

    # Last updated
    updated_html = ""
    if last_updated:
        updated_html = f'<div style="font-size:0.7rem;color:#9ca3af;text-align:right;margin-top:12px">อัปเดตล่าสุด: {last_updated}</div>'

    # Single line panel HTML
    panel_html = f'<div class="op-summary-panel"><div class="op-summary-header"><div class="op-summary-title"><span style="font-size:1.5rem">📋</span> {title}</div><div class="op-summary-badge {overall_status}">{cfg["icon"]} {status_message or cfg["label"]}</div></div>{metrics_html}{alerts_html}{updated_html}</div>'

    st.markdown(panel_html, unsafe_allow_html=True)


def render_action_card(
    title: str,
    description: str,
    icon: str = "action",
    action_label: str = "ดำเนินการ",
    action_page: str = None,
    status: Literal["ok", "warning", "critical", "none"] = "none",
    count: Optional[int] = None,
):
    """
    Render a card for actionable items (e.g., items requiring attention).
    """
    icon_char = METRIC_ICONS.get(icon, "⚡")
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["none"])

    count_html = ""
    if count is not None:
        count_html = f'<span style="background:{cfg["bg"]};color:{cfg["color"]};padding:4px 10px;border-radius:12px;font-size:0.85rem;font-weight:600">{count:,}</span>'

    # Single line HTML
    card_html = f'<div style="background:#ffffff;border-radius:8px;padding:16px 20px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.1);display:flex;align-items:center;gap:16px"><div style="width:48px;height:48px;background:#f3f4f6;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0">{icon_char}</div><div style="flex:1"><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px"><span style="font-size:1rem;font-weight:600;color:#1f2937">{title}</span>{count_html}</div><div style="font-size:0.8rem;color:#6b7280">{description}</div></div></div>'

    st.markdown(card_html, unsafe_allow_html=True)

    if action_label and action_page:
        st.page_link(action_page, label=f"➡️ {action_label}", use_container_width=True)


def render_kpi_gauge(
    label: str,
    value: float,
    target: float = 100,
    unit: str = "%",
    thresholds: tuple = (80, 95),
):
    """
    Render a simple KPI gauge with color-coded status.

    Parameters:
    - label: KPI name
    - value: Current value
    - target: Target value (default 100 for percentage)
    - unit: Display unit (% or other)
    - thresholds: (warning_threshold, ok_threshold) - below warning is critical
    """
    # Determine color
    if value >= thresholds[1]:
        color = "#16a34a"  # Green
        status = "ok"
    elif value >= thresholds[0]:
        color = "#f59e0b"  # Yellow
        status = "warning"
    else:
        color = "#dc2626"  # Red
        status = "critical"

    pct = min((value / target) * 100, 100) if target > 0 else 0

    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["ok"])

    # Single line HTML
    gauge_html = f'<div style="background:#ffffff;border-radius:8px;padding:16px 20px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.1)"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px"><span style="font-size:0.85rem;color:#6b7280">{label}</span><span style="background:{cfg["bg"]};color:{cfg["color"]};padding:2px 8px;border-radius:8px;font-size:0.7rem;font-weight:600">{cfg["label"]}</span></div><div style="font-size:2rem;font-weight:700;color:#1f2937;margin-bottom:8px">{value:.1f}<span style="font-size:1rem;color:#6b7280">{unit}</span></div><div style="background:#e5e7eb;border-radius:6px;height:8px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{color};border-radius:6px;transition:width 0.5s"></div></div><div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.7rem;color:#6b7280"><span>0</span><span>เป้าหมาย: {target}{unit}</span></div></div>'

    st.markdown(gauge_html, unsafe_allow_html=True)


def render_uniform_card(
    title: str,
    value: Union[int, float],
    subtitle: str = "",
    icon: str = "count",
    card_type: Literal["info", "success", "warning", "danger"] = "info",
    trend_day: Optional[float] = None,
    is_percent: bool = False,
    inverse_trend: bool = False,
    height: int = 140,
):
    """
    Render a uniform-sized metric card with clear labels.

    All cards have the same height for symmetry.

    Parameters:
    - title: Main label (header)
    - value: The metric value
    - subtitle: Additional context/description
    - icon: Icon key from METRIC_ICONS
    - card_type: Color theme
    - trend_day: Day-over-day trend
    - is_percent: Format value as percentage
    - inverse_trend: Reverse trend colors (down is good)
    - height: Fixed height in pixels (default 140)
    """
    border_color = BORDER_COLORS.get(card_type, BORDER_COLORS["info"])
    icon_char = METRIC_ICONS.get(icon, "📊")

    # Trend HTML
    trend_html = ""
    if trend_day is not None:
        get_arrow = get_trend_arrow_inverse if inverse_trend else get_trend_arrow
        arrow, color = get_arrow(trend_day)
        trend_html = f'<span style="color:{color};font-size:0.85rem;margin-left:8px">{arrow}{format_trend(trend_day, is_percent)}</span>'

    # Subtitle HTML
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<div style="font-size:0.75rem;color:#6b7280;margin-top:4px;line-height:1.3">{subtitle}</div>'

    # Single line HTML with fixed height
    card_html = f'<div style="background:#ffffff;border-radius:8px;padding:16px 20px;border-left:4px solid {border_color};border-top:1px solid #e5e7eb;border-right:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.1);height:{height}px;display:flex;flex-direction:column;justify-content:space-between"><div><div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><span style="font-size:1.3rem">{icon_char}</span><span style="font-size:0.9rem;color:#6b7280;font-weight:500">{title}</span></div><div style="font-size:1.85rem;font-weight:700;color:#1f2937">{format_number(value, is_percent)}{trend_html}</div></div>{subtitle_html}</div>'

    st.markdown(card_html, unsafe_allow_html=True)


def render_card_grid(cards: list[dict], columns: int = 4, height: int = 140):
    """
    Render a grid of uniform cards.

    Parameters:
    - cards: List of card configs (each passed to render_uniform_card)
    - columns: Number of columns (default 4)
    - height: Fixed height for all cards
    """
    cols = st.columns(columns)
    for i, card in enumerate(cards):
        card["height"] = height
        with cols[i % columns]:
            render_uniform_card(**card)
