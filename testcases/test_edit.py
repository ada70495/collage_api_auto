"""编辑能力：抠图、滤镜、调整、模糊、文字、边框、背景

除状态码外，所有用例都会解码产物，用 Pillow 校验尺寸、像素与通道。
"""
import os

import allure
import pytest
import yaml

from common.assert_handler import AssertHandler
from common.image_lib import (
    alpha_ratio,
    average_brightness,
    differs_from,
    image_size,
    is_grayscale,
    pixel_at,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

with open(os.path.join(DATA_DIR, "collage_data.yaml"), "r", encoding="utf-8") as _f:
    DATA = yaml.safe_load(_f)

DEMO_1 = "img_demo_1"        # 400x300 纯红
DEMO_SHAPE = "img_demo_shape"  # 400x300 白底红圆
DEMO_ALPHA = "img_demo_alpha"  # 200x200 透明底方块


@allure.feature("拼图工作台")
class TestCutout:

    @allure.story("去除纯色背景")
    def test_cutout_removes_background(self, api):
        body = api.cutout(DEMO_SHAPE, bg_color="#FFFFFF", tolerance=20).json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 400, "输出宽度不变")
        a.eq(body["data"]["height"], 300, "输出高度不变")

        image = body["data"]["base64"]
        a.gt(alpha_ratio(image), 0.3, "透明像素占比")
        a.eq(pixel_at(image, 200, 150)[3], 255, "圆心的主体像素应保持不透明")
        a.eq(pixel_at(image, 0, 0)[3], 0, "四角背景应变为透明")
        a.finish()

    @allure.story("容差两端：0 只删纯背景、100 全图透明")
    def test_cutout_tolerance_edges(self, api):
        """容差 0 仅去掉与背景色完全相同的像素；容差 100 时所有像素都判为背景"""
        exact = api.cutout(
            DEMO_SHAPE, bg_color="#FFFFFF", tolerance=DATA["cutout_tolerance"]["exact"]
        ).json()
        full = api.cutout(
            DEMO_SHAPE, bg_color="#FFFFFF", tolerance=DATA["cutout_tolerance"]["full"]
        ).json()

        a = AssertHandler()
        a.eq(exact["code"], 200, "容差 0 业务码")
        a.eq(pixel_at(exact["data"]["base64"], 0, 0)[3], 0, "纯背景像素应透明")
        a.eq(pixel_at(exact["data"]["base64"], 200, 150)[3], 255, "主体像素保持不透明")
        a.eq(alpha_ratio(exact["data"]["base64"]) < 1.0, True, "仍保留不透明主体")

        a.eq(full["code"], 200, "容差 100 业务码")
        a.eq(alpha_ratio(full["data"]["base64"]), 1.0, "全图判为背景")
        a.eq(pixel_at(full["data"]["base64"], 200, 150)[3], 0, "主体像素也被判为背景")
        a.finish()

    @allure.story("容差超范围被拒")
    def test_cutout_tolerance_out_of_range(self, api):
        body = api.cutout(DEMO_SHAPE, tolerance=101).json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "0-100", "错误提示")
        a.finish()

    @allure.story("图片不存在返回 404")
    def test_cutout_image_not_found(self, api):
        body = api.cutout("img_not_exist").json()

        a = AssertHandler()
        a.eq(body["code"], 404, "业务码")
        a.contains(body["msg"], "不存在", "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestFilter:

    @allure.story("五种滤镜逐个生效")
    @pytest.mark.parametrize("name", DATA["filters"])
    def test_filter_apply(self, api, name):
        body = api.apply_filter(DEMO_1, name).json()

        a = AssertHandler()
        a.eq(body["code"], 200, f"{name} 业务码")
        a.eq(body["data"]["width"], 400, f"{name} 输出宽度不变")
        a.eq(body["data"]["height"], 300, f"{name} 输出高度不变")
        if name == "grayscale":
            a.eq(is_grayscale(body["data"]["base64"]), True, "灰度滤镜输出的 R/G/B 应相等")
        a.finish()

    @allure.story("非法滤镜被拒")
    def test_filter_invalid(self, api):
        body = api.apply_filter(DEMO_1, "sketch").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "不支持", "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestAdjust:

    @allure.story("亮度提升后平均亮度上升")
    def test_adjust_brightness_increase(self, api):
        origin = api.blur(DEMO_1, 0).json()["data"]["base64"]
        bright = api.adjust(DEMO_1, brightness=150).json()["data"]["base64"]

        a = AssertHandler()
        a.eq(average_brightness(bright) > average_brightness(origin), True, "亮度 150 应比原图更亮")
        a.finish()

    @allure.story("调整参数边界")
    @pytest.mark.parametrize("case", DATA["adjust_cases"], ids=lambda c: c["case_name"])
    def test_adjust_boundary(self, api, case):
        body = api.adjust(DEMO_1, **case["params"]).json()

        a = AssertHandler()
        a.eq(body["code"], case["expect"], "业务码")
        if case["expect"] != 200 and case.get("msg"):
            a.contains(body["msg"], case["msg"], "错误提示")
        a.finish()

    @allure.story("三项参数全不传被拒")
    def test_adjust_empty(self, api):
        body = api.adjust(DEMO_1).json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "至少传一项", "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestBlur:

    @allure.story("半径 0 不改变画面")
    def test_blur_radius_zero(self, api):
        origin = api.blur(DEMO_1, 0).json()["data"]["base64"]
        again = api.blur(DEMO_1, 0).json()["data"]["base64"]

        a = AssertHandler()
        a.eq(differs_from(origin, again), False, "半径 0 两次输出像素一致")
        a.finish()

    @allure.story("模糊半径边界")
    @pytest.mark.parametrize("case", DATA["blur_cases"], ids=lambda c: c["case_name"])
    def test_blur_boundary(self, api, case):
        body = api.blur(DEMO_1, case["radius"]).json()

        a = AssertHandler()
        a.eq(body["code"], case["expect"], "业务码")
        if case["expect"] == 200:
            a.eq(body["data"]["width"], 400, "尺寸不变")
        elif case.get("msg"):
            a.contains(body["msg"], case["msg"], "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestText:

    @allure.story("叠加文字")
    def test_text_overlay(self, api):
        origin = api.blur(DEMO_1, 0).json()["data"]["base64"]
        body = api.add_text(DEMO_1, "Hello", position="center", font_size=32).json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 400, "加字后宽度不变")
        a.eq(body["data"]["height"], 300, "加字后高度不变")
        a.eq(differs_from(origin, body["data"]["base64"]), True, "画面应出现文字像素")
        a.finish()

    @allure.story("文字参数边界")
    @pytest.mark.parametrize("case", DATA["text_cases"], ids=lambda c: c["case_name"])
    def test_text_boundary(self, api, case):
        body = api.add_text(DEMO_1, case["text"], font_size=case["font_size"]).json()

        a = AssertHandler()
        a.eq(body["code"], case["expect"], "业务码")
        if case["expect"] != 200 and case.get("msg"):
            a.contains(body["msg"], case["msg"], "错误提示")
        a.finish()

    @allure.story("空文字被拒")
    def test_text_empty(self, api):
        body = api.add_text(DEMO_1, "   ").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "不能为空", "错误提示")
        a.finish()

    @allure.story("非法位置被拒")
    def test_text_invalid_position(self, api):
        body = api.add_text(DEMO_1, "Hi", position="middle").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "top-left", "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestBorder:

    @allure.story("加边框后尺寸外扩")
    def test_border_expand(self, api):
        body = api.border(DEMO_1, width=10, color="#000000").json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 420, "宽度增加 2 倍边框宽度")
        a.eq(body["data"]["height"], 320, "高度增加 2 倍边框宽度")
        a.finish()

    @allure.story("边框宽度边界")
    @pytest.mark.parametrize("case", DATA["border_cases"], ids=lambda c: c["case_name"])
    def test_border_boundary(self, api, case):
        body = api.border(DEMO_1, width=case["width"]).json()

        a = AssertHandler()
        a.eq(body["code"], case["expect"], "业务码")
        if case["expect"] == 200:
            a.eq(body["data"]["width"], 400 + case["width"] * 2, "输出宽度 = 原宽 + 2*width")
        elif case.get("msg"):
            a.contains(body["msg"], case["msg"], "错误提示")
        a.finish()


@allure.feature("拼图工作台")
class TestBackground:

    @allure.story("透明图合成纯色背景")
    def test_background_fill(self, api):
        body = api.background(DEMO_ALPHA, color="#FFFFFF").json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 200, "尺寸不变")
        a.eq(body["data"]["height"], 200, "尺寸不变")
        a.eq(image_size(body["data"]["base64"]), (200, 200), "产物尺寸")
        a.eq(pixel_at(body["data"]["base64"], 0, 0)[:3], (255, 255, 255), "四角应被填成背景色")
        a.eq(pixel_at(body["data"]["base64"], 100, 100)[:3], (60, 120, 220), "主体像素应保留原色")
        a.finish()

    @allure.story("非法颜色被拒")
    def test_background_invalid_color(self, api):
        body = api.background(DEMO_ALPHA, color="#GGGGGG").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "#RRGGBB", "错误提示")
        a.finish()
