"""图片上传：格式白名单、体积与像素上限、内容合法性"""
import allure

from common.assert_handler import AssertHandler
from common.image_lib import make_image


@allure.feature("拼图工作台")
class TestImageUpload:

    @allure.story("上传 PNG 图片")
    def test_upload_png(self, api):
        body = api.upload("upload_png", make_image(400, 300), "png").json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["width"], 400, "返回宽度")
        a.eq(body["data"]["height"], 300, "返回高度")
        a.eq(body["data"]["format"], "PNG", "返回格式")
        a.not_none(body["data"]["image_id"], "图片ID")
        a.finish()

    @allure.story("上传 JPG 图片")
    def test_upload_jpg(self, api):
        body = api.upload("upload_jpg", make_image(320, 240, fmt="JPEG"), "jpg").json()

        a = AssertHandler()
        a.eq(body["code"], 200, "业务码")
        a.eq(body["data"]["format"], "JPEG", "JPG 上传后格式为 JPEG")
        a.eq(body["data"]["width"], 320, "返回宽度")
        a.finish()

    @allure.story("不支持的格式被拒")
    def test_upload_unsupported_format(self, api):
        body = api.upload("upload.gif", make_image(), "gif").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "格式不在白名单")
        a.contains(body["msg"], "不支持", "错误提示")
        a.finish()

    @allure.story("内容为空被拒")
    def test_upload_empty_content(self, api):
        body = api.upload("empty.png", "").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "不能为空", "错误提示")
        a.finish()

    @allure.story("非法 base64 被拒")
    def test_upload_invalid_base64(self, api):
        body = api.upload("bad.png", "not-base64!!").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "base64", "错误提示")
        a.finish()

    @allure.story("单边像素超限被拒")
    def test_upload_oversize_pixel(self, api):
        body = api.upload("big.png", make_image(4200, 200), "png").json()

        a = AssertHandler()
        a.eq(body["code"], 400, "业务码")
        a.contains(body["msg"], "4096", "错误提示")
        a.finish()
