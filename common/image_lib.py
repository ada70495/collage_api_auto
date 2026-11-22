"""图片工具：生成测试图、解码响应图片、读取尺寸与像素

所有用例里对"产物"的检查都走这里，避免每个用例各写一套 PIL 操作。
"""
import base64
import io

from PIL import Image


def make_image(width=400, height=300, color=(214, 69, 69), mode="RGB", fmt="PNG") -> str:
    """生成纯色图片，返回 base64 字符串"""
    img = Image.new(mode, (width, height), color)
    return to_base64(img, fmt)


def make_shape_image(width=400, height=300, bg=(255, 255, 255), fill=(214, 69, 69), radius=80) -> str:
    """白色底 + 居中实心圆，用于抠图场景"""
    from PIL import ImageDraw

    img = Image.new("RGB", (width, height), bg)
    cx, cy = width // 2, height // 2
    ImageDraw.Draw(img).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
    return to_base64(img, "PNG")


def to_base64(img, fmt="PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def open_image(b64: str) -> Image.Image:
    """把响应里的 base64 还原成 PIL 图片"""
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def image_size(b64: str):
    img = open_image(b64)
    return img.size


def alpha_ratio(b64: str) -> float:
    """透明像素占比（alpha == 0 的比例）"""
    img = open_image(b64).convert("RGBA")
    alpha = img.getchannel("A")
    histogram = alpha.histogram()
    transparent = histogram[0]
    total = img.width * img.height
    return round(transparent / total, 4) if total else 0.0


def pixel_at(b64: str, x: int, y: int):
    img = open_image(b64).convert("RGBA")
    return img.getpixel((x, y))


def average_brightness(b64: str) -> float:
    """整图平均亮度（0-255）"""
    img = open_image(b64).convert("L")
    histogram = img.histogram()
    total = img.width * img.height
    return round(sum(i * count for i, count in enumerate(histogram)) / total, 2)


def is_grayscale(b64: str, samples: int = 20) -> bool:
    """抽样检查：灰度图每个像素的 R=G=B"""
    img = open_image(b64).convert("RGB")
    step_x = max(1, img.width // samples)
    step_y = max(1, img.height // samples)
    for x in range(0, img.width, step_x):
        for y in range(0, img.height, step_y):
            r, g, b = img.getpixel((x, y))
            if not (r == g == b):
                return False
    return True


def differs_from(source_b64: str, target_b64: str) -> bool:
    """两张图是否存在像素差异"""
    return open_image(source_b64).convert("RGB").tobytes() != open_image(target_b64).convert("RGB").tobytes()
