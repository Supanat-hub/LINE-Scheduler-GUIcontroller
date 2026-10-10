"""
Template processor for dynamic variables in LINE messages
"""

from datetime import datetime
from typing import Dict, Any

THAI_DAYS = [
    "วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี",
    "วันศุกร์", "วันเสาร์", "วันอาทิตย์"
]

THAI_DAYS_SHORT = [
    "จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"
]

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]


def render_message_template(template: str, dt: datetime = None, custom_vars: Dict[str, Any] = None) -> str:
    """
    แปลงตัวแปรในข้อความ (Template Variables) ให้อยู่ในรูปข้อความจริงตามวันเวลาปัจจุบัน
    
    ตัวแปรที่รองรับ:
      - {วันที่}: วันที่ปัจจุบันแบบไทย เช่น '10 ตุลาคม 2569'
      - {วันที่สั้น}: เช่น '10/10/2569'
      - {วัน}: เช่น 'วันเสาร์'
      - {เวลา}: เช่น '17:30'
      - {เดือน}: เช่น 'ตุลาคม'
      - {ปี}: เช่น '2569' (พ.ศ.)
      - {date}: เช่น '2026-10-10'
      - {time}: เช่น '17:30:00'
      - {datetime}: เช่น '2026-10-10 17:30:00'
    """
    if dt is None:
        dt = datetime.now()

    day_idx = dt.weekday()  # 0 = Monday, 6 = Sunday
    month_idx = dt.month - 1
    thai_year = dt.year + 543

    variables = {
        "{วันที่}": f"{dt.day} {THAI_MONTHS[month_idx]} {thai_year}",
        "{วันที่สั้น}": f"{dt.day:02d}/{dt.month:02d}/{thai_year}",
        "{วัน}": THAI_DAYS[day_idx],
        "{วันสั้น}": THAI_DAYS_SHORT[day_idx],
        "{เวลา}": dt.strftime("%H:%M"),
        "{เวลานาทีวินาที}": dt.strftime("%H:%M:%S"),
        "{เดือน}": THAI_MONTHS[month_idx],
        "{ปี}": str(thai_year),
        "{date}": dt.strftime("%Y-%m-%d"),
        "{time}": dt.strftime("%H:%M:%S"),
        "{year}": str(dt.year),
        "{datetime}": dt.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if custom_vars:
        for k, v in custom_vars.items():
            var_key = k if k.startswith("{") and k.endswith("}") else f"{{{k}}}"
            variables[var_key] = str(v)

    rendered = template
    for placeholder, val in variables.items():
        rendered = rendered.replace(placeholder, val)

    return rendered

