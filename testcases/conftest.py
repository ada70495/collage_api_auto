"""全局 fixture：请求客户端、接口对象、测试数据复位"""
import os
import sys

import pytest

# 保证从任意目录运行都能 import 项目内的包
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.collage_api import CollageApi
from common.conf_handler import config
from common.logger_handler import logger
from common.request_handler import RequestHandler


@pytest.fixture(scope="session")
def client() -> RequestHandler:
    """全 session 共用一个 Session 和一个 token"""
    c = RequestHandler()
    logger.info(f"测试环境：{config.summary()}")
    yield c
    c.close()


@pytest.fixture(scope="session")
def api(client) -> CollageApi:
    return CollageApi(client)


@pytest.fixture(scope="session", autouse=True)
def prepared_env(client):
    """环境自愈：复位素材 → 登录

    内置素材 img_demo_1 / 2 / 3 / shape / alpha 由 /__admin/reset 重建，
    用例直接用这些固定 image_id，不依赖上传用例的执行顺序。
    """
    logger.info("=== 测试环境准备开始 ===")

    resp = client.post("/__admin/reset")
    assert resp.json()["code"] == 200, "Mock 服务复位失败，请确认 mock_server 已启动且地址正确"

    login_data = client.login()
    assert login_data.get("code") == 200, f"登录失败：{login_data}"

    logger.info(f"素材复位完成 count={resp.json()['data'].get('count')}")
    logger.info("=== 测试环境准备结束 ===")
    yield
