"""拼图工作台 - 本地被测服务

覆盖图片上传、抠图、滤镜、调整、模糊、文字、边框、背景、模板、贴纸、拼图合成、导出。

启动：python mock_server/app.py
环境变量：PORT（默认 9400）、SIGN_CHECK（true 时校验 X-Sign）、SIGN_KEY
"""
import base64
import hashlib
import io
import os

from flask import Flask, jsonify, request
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

app = Flask(__name__)

SIGN_KEY = os.getenv("SIGN_KEY", "mock-sign-key-2026")
SIGN_CHECK = os.getenv("SIGN_CHECK", "false").lower() == "true"

MAX_EDGE = 4096          # 单边像素上限
MAX_BYTES = 4 * 1024 * 1024  # 上传体积上限 4MB
FORMATS = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}

TEMPLATES = [
    {"template_id": "row_2", "name": "横向两格", "slots": 2},
    {"template_id": "row_3", "name": "横向三格", "slots": 3},
    {"template_id": "grid_2x2", "name": "四宫格", "slots": 4},
]

STICKERS = [
    {"sticker_id": "star", "name": "星星"},
    {"sticker_id": "heart", "name": "爱心"},
    {"sticker_id": "badge", "name": "徽章"},
    {"sticker_id": "ribbon", "name": "飘带"},
]

# image_id -> {"image": PIL.Image, "name": str, "format": str}
STATE = {"images": {}, "seq": 0}


# ---------------------------------------------------------------- 工具
def make_sign(method, path, payload):
    parts = [method.upper(), path]
    if isinstance(payload, dict):
        for key in sorted(payload):
            parts.append(f"{key}={payload[key]}")
    return hashlib.md5(("&".join(parts) + "&key=" + SIGN_KEY).encode()).hexdigest()


def ok(data=None, msg="成功"):
    return jsonify({"code": 200, "msg": msg, "data": data or {}})


def fail(msg, code=400):
    return jsonify({"code": code, "msg": msg, "data": {}})


def new_id(prefix="img"):
    STATE["seq"] += 1
    return f"{prefix}_{STATE['seq']:04d}"


def get_image(image_id):
    if not image_id:
        return None
    item = STATE["images"].get(image_id)
    return item["image"] if item else None


def hex_to_rgb(color, default=None):
    if not color:
        return default
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return None
    try:
        return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return None


def encode_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def save_image(img, name, fmt="PNG"):
    image_id = new_id()
    STATE["images"][image_id] = {"image": img, "name": name, "format": fmt}
    return image_id


def result(img, image_id=None, **extra):
    """统一返回：新图 id、尺寸、PNG base64"""
    image_id = image_id or save_image(img, "edited")
    data = {
        "image_id": image_id,
        "width": img.width,
        "height": img.height,
        "format": "PNG",
        "base64": encode_png(img),
    }
    data.update(extra)
    return ok(data)


def get_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # 低版本 Pillow 不支持 size 参数
        return ImageFont.load_default()


def build_demo_images():
    imgs = {}

    imgs["img_demo_1"] = {"image": Image.new("RGB", (400, 300), (214, 69, 69)), "name": "纯红底色", "format": "PNG"}

    gradient = ImageOps.colorize(
        Image.linear_gradient("L").resize((400, 300)),
        black=(40, 80, 200),
        white=(255, 255, 255),
    ).convert("RGB")
    imgs["img_demo_2"] = {"image": gradient, "name": "蓝白渐变", "format": "PNG"}

    imgs["img_demo_3"] = {"image": Image.new("RGB", (300, 400), (70, 160, 90)), "name": "纯绿竖图", "format": "PNG"}

    shape = Image.new("RGB", (400, 300), (255, 255, 255))
    draw = ImageDraw.Draw(shape)
    draw.ellipse((120, 70, 280, 230), fill=(214, 69, 69))
    imgs["img_demo_shape"] = {"image": shape, "name": "白底红圆", "format": "PNG"}

    alpha = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(alpha).rectangle((50, 50, 150, 150), fill=(60, 120, 220, 255))
    imgs["img_demo_alpha"] = {"image": alpha, "name": "透明底方块", "format": "PNG"}

    return imgs


# ---------------------------------------------------------------- 鉴权
@app.before_request
def check_sign():
    if not SIGN_CHECK or request.method == "GET" or request.path in ("/user/login", "/__admin/reset"):
        return None
    payload = request.get_json(silent=True) or {}
    if request.headers.get("X-Sign") != make_sign(request.method, request.path, payload):
        return fail("签名校验失败", 401)
    return None


@app.route("/health")
def health():
    return jsonify({"service": "mock-collage-api", "sign_check": SIGN_CHECK, "status": "ok"})


@app.route("/__admin/reset", methods=["POST"])
def reset():
    STATE["images"] = build_demo_images()
    STATE["seq"] = 0
    return ok({"count": len(STATE["images"])})


@app.route("/user/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    if not body.get("username"):
        return fail("用户名不能为空")
    if body.get("password") != "123456":
        return fail("用户名或密码错误", 401)
    return ok({"token": "collage-token-2026", "username": body["username"]})


# ---------------------------------------------------------------- 上传
@app.route("/image/upload", methods=["POST"])
def upload():
    body = request.get_json(silent=True) or {}
    raw = body.get("content")
    fmt = str(body.get("format", "png")).lower()

    if fmt not in FORMATS:
        return fail(f"不支持的格式：{fmt}，可选 {'/'.join(FORMATS)}")
    if not raw or not isinstance(raw, str):
        return fail("文件内容不能为空")
    if len(raw) > MAX_BYTES:
        return fail("文件超过 4MB 上限")

    try:
        binary = base64.b64decode(raw, validate=True)
    except Exception:
        return fail("文件内容不是合法的 base64")

    try:
        img = Image.open(io.BytesIO(binary))
        img.load()
    except Exception:
        return fail("图片无法解析")

    if max(img.width, img.height) > MAX_EDGE:
        return fail(f"图片单边不能超过 {MAX_EDGE} 像素")

    image_id = save_image(img, body.get("name") or "upload", FORMATS[fmt])
    return ok(
        {
            "image_id": image_id,
            "width": img.width,
            "height": img.height,
            "format": FORMATS[fmt],
            "name": STATE["images"][image_id]["name"],
        }
    )


# ---------------------------------------------------------------- 素材
@app.route("/asset/templates")
def templates():
    return ok({"total": len(TEMPLATES), "list": TEMPLATES})


@app.route("/asset/stickers")
def stickers():
    return ok({"total": len(STICKERS), "list": STICKERS})


# ---------------------------------------------------------------- 抠图
@app.route("/edit/cutout", methods=["POST"])
def cutout():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    bg = hex_to_rgb(body.get("bg_color", "#FFFFFF"))
    if bg is None:
        return fail("背景色需为 #RRGGBB 格式")

    tolerance = body.get("tolerance", 20)
    if not isinstance(tolerance, int) or tolerance < 0 or tolerance > 100:
        return fail("容差取值 0-100")

    rgba = img.convert("RGBA")
    diff = ImageChops.difference(rgba.convert("RGB"), Image.new("RGB", rgba.size, bg))
    mask = diff.convert("L").point(lambda v: 0 if v <= int(tolerance * 2.55) else 255)
    rgba.putalpha(mask)
    return result(rgba)


# ---------------------------------------------------------------- 滤镜
@app.route("/edit/filter", methods=["POST"])
def apply_filter():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    name = body.get("filter")
    rgb = img.convert("RGB")

    if name == "grayscale":
        out = rgb.convert("L").convert("RGB")
    elif name == "sepia":
        out = rgb.convert("RGB", (0.393, 0.769, 0.189, 0, 0.349, 0.686, 0.168, 0, 0.272, 0.534, 0.131, 0))
    elif name == "warm":
        r, g, b = rgb.split()
        out = Image.merge("RGB", (r.point(lambda v: min(255, int(v * 1.2))), g, b.point(lambda v: int(v * 0.85))))
    elif name == "cool":
        r, g, b = rgb.split()
        out = Image.merge("RGB", (r.point(lambda v: int(v * 0.85)), g, b.point(lambda v: min(255, int(v * 1.2)))))
    elif name == "vivid":
        out = ImageEnhance.Color(rgb).enhance(1.8)
    else:
        return fail("滤镜不支持，可选 grayscale/sepia/warm/cool/vivid")

    return result(out, filter=name)


# ---------------------------------------------------------------- 调整
@app.route("/edit/adjust", methods=["POST"])
def adjust():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    fields = ["brightness", "contrast", "saturation"]
    given = {k: body[k] for k in fields if k in body}
    if not given:
        return fail("亮度、对比度、饱和度至少传一项")

    for key, value in given.items():
        if not isinstance(value, int) or value < 0 or value > 200:
            return fail(f"{key} 取值 0-200，100 为原图")

    out = img.convert("RGB")
    if "brightness" in given:
        out = ImageEnhance.Brightness(out).enhance(given["brightness"] / 100)
    if "contrast" in given:
        out = ImageEnhance.Contrast(out).enhance(given["contrast"] / 100)
    if "saturation" in given:
        out = ImageEnhance.Color(out).enhance(given["saturation"] / 100)

    return result(out, adjust=given)


# ---------------------------------------------------------------- 模糊
@app.route("/edit/blur", methods=["POST"])
def blur():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    radius = body.get("radius", 0)
    if not isinstance(radius, int) or isinstance(radius, bool) or radius < 0 or radius > 50:
        return fail("模糊半径取值 0-50")

    out = img.convert("RGB") if radius == 0 else img.convert("RGB").filter(ImageFilter.GaussianBlur(radius))
    return result(out, radius=radius)


# ---------------------------------------------------------------- 文字
@app.route("/edit/text", methods=["POST"])
def add_text():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        return fail("文字内容不能为空")
    if len(text) > 20:
        return fail("文字最多 20 个字符")

    position = body.get("position", "center")
    if position not in ("top-left", "center", "bottom-right"):
        return fail("位置可选 top-left/center/bottom-right")

    font_size = body.get("font_size", 24)
    if not isinstance(font_size, int) or font_size < 12 or font_size > 72:
        return fail("字号取值 12-72")

    color = hex_to_rgb(body.get("color", "#000000"))
    if color is None:
        return fail("文字颜色需为 #RRGGBB 格式")

    canvas = img.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    font = get_font(font_size)
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]

    if position == "top-left":
        xy = (8, 8)
    elif position == "bottom-right":
        xy = (canvas.width - tw - 8, canvas.height - th - 8)
    else:
        xy = ((canvas.width - tw) // 2, (canvas.height - th) // 2)

    draw.text(xy, text, fill=color, font=font)
    return result(canvas, text=text, position=position)


# ---------------------------------------------------------------- 边框
@app.route("/edit/border", methods=["POST"])
def border():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    width = body.get("width", 10)
    if not isinstance(width, int) or isinstance(width, bool) or width < 1 or width > 50:
        return fail("边框宽度取值 1-50")

    color = hex_to_rgb(body.get("color", "#000000"))
    if color is None:
        return fail("边框颜色需为 #RRGGBB 格式")

    out = ImageOps.expand(img.convert("RGB"), border=width, fill=color)
    return result(out, border_width=width)


# ---------------------------------------------------------------- 背景
@app.route("/edit/background", methods=["POST"])
def background():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    color = hex_to_rgb(body.get("color", "#FFFFFF"))
    if color is None:
        return fail("背景色需为 #RRGGBB 格式")

    canvas = Image.new("RGB", img.size, color)
    if img.mode == "RGBA":
        canvas.paste(img, (0, 0), img)
    else:
        canvas.paste(img.convert("RGB"), (0, 0))
    return result(canvas, background=body.get("color", "#FFFFFF"))


# ---------------------------------------------------------------- 拼图
def cover_resize(img, size):
    """等比缩放到完全覆盖目标尺寸，再居中裁剪"""
    scale = max(size[0] / img.width, size[1] / img.height)
    resized = img.resize((max(1, int(img.width * scale) + 1), max(1, int(img.height * scale) + 1)))
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


@app.route("/collage/compose", methods=["POST"])
def compose():
    body = request.get_json(silent=True) or {}
    template = next((t for t in TEMPLATES if t["template_id"] == body.get("template_id")), None)
    if template is None:
        return fail("模板不存在", 404)

    ids = body.get("image_ids") or []
    if not isinstance(ids, list) or len(ids) != template["slots"]:
        return fail(f"模板 {template['template_id']} 需要 {template['slots']} 张图片")

    images = []
    for image_id in ids:
        img = get_image(image_id)
        if img is None:
            return fail(f"图片不存在：{image_id}", 404)
        images.append(img.convert("RGB"))

    gap = body.get("gap", 0)
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 0 or gap > 20:
        return fail("间距取值 0-20")

    bg = hex_to_rgb(body.get("bg_color", "#FFFFFF"))
    if bg is None:
        return fail("背景色需为 #RRGGBB 格式")

    if template["template_id"].startswith("row"):
        height = max(i.height for i in images)
        scaled = [i.resize((max(1, round(i.width * height / i.height)), height)) for i in images]
        width = sum(s.width for s in scaled) + gap * (len(scaled) - 1)
        canvas = Image.new("RGB", (width, height), bg)
        x = 0
        for s in scaled:
            canvas.paste(s, (x, 0))
            x += s.width + gap
        return result(canvas, slots=len(images), cell=None)

    # grid_2x2：统一方格，cover 裁剪
    cell = max(max(i.width, i.height) for i in images)
    canvas = Image.new("RGB", (cell * 2 + gap, cell * 2 + gap), bg)
    for index, img in enumerate(images):
        row, col = divmod(index, 2)
        canvas.paste(cover_resize(img, (cell, cell)), (col * (cell + gap), row * (cell + gap)))
    return result(canvas, slots=len(images), cell=cell)


# ---------------------------------------------------------------- 导出
@app.route("/export", methods=["POST"])
def export():
    body = request.get_json(silent=True) or {}
    img = get_image(body.get("image_id"))
    if img is None:
        return fail("图片不存在", 404)

    fmt = str(body.get("format", "png")).lower()
    if fmt not in ("png", "jpg"):
        return fail("导出格式可选 png/jpg")

    quality = body.get("quality", 90)
    if not isinstance(quality, int) or quality < 1 or quality > 100:
        return fail("质量取值 1-100")

    buf = io.BytesIO()
    if fmt == "png":
        out = img.convert("RGBA") if img.mode in ("RGBA", "LA") else img.convert("RGB")
        out.save(buf, format="PNG")
        out_format, mode = "PNG", out.mode
    else:
        # JPEG 不支持透明通道，透明区域合成到白底
        out = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            out.paste(img, (0, 0), img)
        else:
            out.paste(img.convert("RGB"), (0, 0))
        out.save(buf, format="JPEG", quality=quality)
        out_format, mode = "JPEG", out.mode

    return ok(
        {
            "width": img.width,
            "height": img.height,
            "format": out_format,
            "mode": mode,
            "base64": base64.b64encode(buf.getvalue()).decode(),
        }
    )


if __name__ == "__main__":
    STATE["images"] = build_demo_images()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "9400")))
