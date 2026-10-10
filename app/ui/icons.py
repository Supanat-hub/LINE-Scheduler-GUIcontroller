"""
Icon generator for System Tray and Status Badges (No emojis used)
"""

from PIL import Image, ImageDraw


def create_status_icon(color: str = "green", size: int = 64) -> Image.Image:
    """
    สร้างภาพไอคอนสถานะวงกลมสีเรียบหรูสำหรับถาดระบบ (System Tray)
    color: 'green' (ปกติ), 'yellow' (เตือน), 'red' (ข้อผิดพลาด)
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    color_map = {
        "green": ("#10B981", "#059669"),
        "yellow": ("#F59E0B", "#D97706"),
        "red": ("#EF4444", "#DC2626"),
        "blue": ("#3B82F6", "#2563EB"),
    }

    fill_color, border_color = color_map.get(color, ("#6B7280", "#4B5563"))

    padding = 6
    # วาดวงกลมพื้นหลัง
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=fill_color,
        outline=border_color,
        width=3
    )

    # วาดจุดไฮไลต์ตรงกลาง
    inner_pad = size // 3
    draw.ellipse(
        [inner_pad, inner_pad, size - inner_pad, size - inner_pad],
        fill="#FFFFFF",
        outline=None
    )

    return image

