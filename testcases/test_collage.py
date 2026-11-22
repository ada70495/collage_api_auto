"""拼图合成与导出：模板、贴纸、多图拼接、格式转换"""
import os

import allure
import pytest
import yaml

from common.assert_handler import AssertHandler
from common.image_lib import image_size, make_image

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

with open(os.path.join(DATA_DIR, "collage_data.yaml"), "r", encoding="utf-8") as _f:
    DATA = yaml.safe_load(_f)

DEMO_1 = "img_demo_1"          # 400x300
DEMO_2 = "img_demo_2"          # 400x300
DEMO_3 = "img_demo_3"          # 300x400
DEMO_SHAPE = "img_demo_shape"  # 400x300
DEMO_ALPHA = "img_demo_alpha"  # 200x200 透明底


@allure.feature("拼图工作台")
class TestAsset:

    @allure.story("模板列表")
    def test_templates(self, api):
        body = api.templates().json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["total"], 3, "模板数量")
        slots = {t["template_id"]: t["slots"] for t in body["data"]["list"]}
        a.eq(slots.get("row_2"), 2, "横向两格槽位数")
        a.eq(slots.get("row_3"), 3, "横向三格槽位数")
        a.eq(slots.get("grid_2x2"), 4, "四宫格槽位数")
        a.finish()

    @allure.story("贴纸列表")
    def test_stickers(self, api):
        body = api.stickers().json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["total"], 4, "贴纸数量")
        a.gt(len(body["data"]["list"]), 0, "贴纸列表非空")
        a.finish()


@allure.feature("拼图工作台")
class TestCompose:

    @allure.story("横向两格拼接")
    def test_compose_row_2(self, api):
        body = api.compose("row_2", [DEMO_1, DEMO_2], gap=0).json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 800, "两图等宽，总宽为两图之和")
        a.eq(body["data"]["height"], 300, "输出高度取较高的图")
        a.eq(image_size(body["data"]["base64"]), (800, 300), "产物实际尺寸")
        a.finish()

    @allure.story("横向两格带间距")
    def test_compose_row_2_with_gap(self, api):
        body = api.compose("row_2", [DEMO_1, DEMO_2], gap=10).json()

        a = AssertHandler()
        a.eq(body["data"]["width"], 810, "总宽需计入一格间距")
        a.eq(body["data"]["height"], 300, "间距不影响高度")
        a.finish()

    @allure.story("横向三格拼接")
    def test_compose_row_3(self, api):
        third = api.upload("row3-extra", make_image(400, 300), "png").json()["data"]["image_id"]
        body = api.compose("row_3", [DEMO_1, DEMO_2, third], gap=0).json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 1200, "三图等宽，总宽为三图之和")
        a.eq(body["data"]["height"], 300, "输出高度")
        a.finish()

    @allure.story("四宫格拼接")
    def test_compose_grid(self, api):
        body = api.compose("grid_2x2", [DEMO_1, DEMO_2, DEMO_3, DEMO_SHAPE], gap=0).json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["cell"], 400, "方格边长取所有图最大边")
        a.eq(body["data"]["width"], 800, "四宫格宽度 = 2*cell")
        a.eq(body["data"]["height"], 800, "四宫格高度 = 2*cell")
        a.finish()

    @allure.story("图片数量与模板不匹配被拒")
    def test_compose_count_mismatch(self, api):
        body = api.compose("row_2", [DEMO_1, DEMO_2, DEMO_3]).json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "需要 2 张", "错误提示")
        a.finish()

    @allure.story("模板不存在返回 404")
    def test_compose_template_not_found(self, api):
        body = api.compose("grid_3x3", [DEMO_1, DEMO_2]).json()

        a = AssertHandler()
        a.eq(body["code"], 404, "业务码")
        a.contains(body["msg"], "模板不存在", "错误提示")
        a.finish()

    @allure.story("拼图间距边界")
    @pytest.mark.parametrize("case", DATA["gap_cases"], ids=lambda c: c["case_name"])
    def test_compose_gap_boundary(self, api, case):
        body = api.compose("row_2", [DEMO_1, DEMO_2], gap=case["gap"]).json()

        a = AssertHandler()
        a.eq(body["code"], case["expect"], "业务码")
        if case["expect"] == 200:
            a.eq(body["data"]["width"], 800 + case["gap"], "总宽 = 两图之和 + 间距")
        elif case.get("msg"):
            a.contains(body["msg"], case["msg"], "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestExport:

    @allure.story("导出 PNG 保留透明通道")
    def test_export_png(self, api):
        body = api.export(DEMO_ALPHA, "png").json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["format"], "PNG", "导出格式")
        a.eq(body["data"]["mode"], "RGBA", "PNG 保留 alpha 通道")
        a.eq(body["data"]["width"], 200, "导出宽度")
        a.finish()

    @allure.story("透明图导出 JPG 合成白底")
    def test_export_jpg_from_alpha(self, api):
        body = api.export(DEMO_ALPHA, "jpg", quality=90).json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["format"], "JPEG", "导出格式")
        a.eq(body["data"]["mode"], "RGB", "JPEG 不支持 alpha，应转为 RGB")
        a.finish()

    @allure.story("非法导出格式被拒")
    def test_export_invalid_format(self, api):
        body = api.export(DEMO_ALPHA, "webp").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "png/jpg", "错误提示")
        a.finish()

    @allure.story("导出质量越界被拒")
    def test_export_quality_boundary(self, api):
        body = api.export(DEMO_1, "jpg", quality=0).json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "1-100", "错误提示")
        a.finish()
