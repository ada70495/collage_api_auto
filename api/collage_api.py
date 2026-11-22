"""拼图工作台接口：上传、抠图、滤镜、调整、模糊、文字、边框、背景、拼图、导出

只拼参数，不做断言；产物校验交给 common/image_lib.py。
"""
from requests import Response


class CollageApi:
    def __init__(self, client):
        self.client = client

    # ---------- 基础 ----------
    def upload(self, name: str, content: str, fmt: str = "png") -> Response:
        return self.client.post(
            "/image/upload", json={"name": name, "content": content, "format": fmt}
        )

    def templates(self) -> Response:
        return self.client.get("/asset/templates")

    def stickers(self) -> Response:
        return self.client.get("/asset/stickers")

    # ---------- 编辑 ----------
    def cutout(self, image_id: str, bg_color: str = "#FFFFFF", tolerance: int = 20) -> Response:
        return self.client.post(
            "/edit/cutout",
            json={"image_id": image_id, "bg_color": bg_color, "tolerance": tolerance},
        )

    def apply_filter(self, image_id: str, name: str) -> Response:
        return self.client.post("/edit/filter", json={"image_id": image_id, "filter": name})

    def adjust(self, image_id: str, **fields) -> Response:
        payload = {"image_id": image_id}
        payload.update(fields)
        return self.client.post("/edit/adjust", json=payload)

    def blur(self, image_id: str, radius: int) -> Response:
        return self.client.post("/edit/blur", json={"image_id": image_id, "radius": radius})

    def add_text(self, image_id: str, text: str, position: str = "center", font_size: int = 24,
                 color: str = "#000000") -> Response:
        return self.client.post(
            "/edit/text",
            json={
                "image_id": image_id,
                "text": text,
                "position": position,
                "font_size": font_size,
                "color": color,
            },
        )

    def border(self, image_id: str, width: int = 10, color: str = "#000000") -> Response:
        return self.client.post(
            "/edit/border", json={"image_id": image_id, "width": width, "color": color}
        )

    def background(self, image_id: str, color: str = "#FFFFFF") -> Response:
        return self.client.post("/edit/background", json={"image_id": image_id, "color": color})

    # ---------- 拼图与导出 ----------
    def compose(self, template_id: str, image_ids: list, gap: int = 0, bg_color: str = "#FFFFFF") -> Response:
        return self.client.post(
            "/collage/compose",
            json={"template_id": template_id, "image_ids": image_ids, "gap": gap, "bg_color": bg_color},
        )

    def export(self, image_id: str, fmt: str = "png", quality: int = 90) -> Response:
        return self.client.post("/export", json={"image_id": image_id, "format": fmt, "quality": quality})
