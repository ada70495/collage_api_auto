# collage_api_auto

拼图工作台后台接口的自动化测试工程，覆盖图片上传、抠图、滤镜、调整、模糊、文字、边框、背景、模板、贴纸、拼图合成与导出。
技术栈：Python 3.13 + requests + pytest + PyYAML + Pillow + Allure + loguru，被测服务用 Flask + Pillow 起在本地。

被测服务是仓库里的一个 Flask 应用（`mock_server/app.py`），13 个业务接口。图片处理是真的跑 Pillow，接口返回 PNG 的 base64；
测试侧同样用 Pillow 解码产物，校验尺寸、像素、透明度、通道与格式，而不是只看业务码。
克隆仓库、装好依赖就能跑，当前用例 56 条。

## 环境要求

| 项 | 说明 |
| --- | --- |
| Python | 3.10 及以上（验证用的是 3.13） |
| 被测服务 | 仓库内 `mock_server/app.py`，默认监听 9400 端口 |
| Pillow | 服务端做图像处理，测试侧校验产物，两边都依赖 |
| Allure 命令行 | 可选。装了才能生成 HTML 报告，不装仍可跑用例，原始数据留在 `report/allure_raw` |

## 依赖与用途

| 包 | 用途 | 备注 |
| --- | --- | --- |
| `requests` | HTTP 请求 | 统一走 `common/request_handler.py` 的 Session |
| `PyYAML` | 读取环境配置和用例数据 | 滤镜、边界值、间距等都放在 `data/collage_data.yaml` |
| `pytest` | 用例执行、参数化、fixture | `pytest.ini` 固定扫描路径与执行参数 |
| `allure-pytest` | 报告，附带请求/响应与软断言明细 | 需要 allure 命令行转 HTML |
| `pytest-rerunfailures` | 失败重跑 | 最多 2 次，间隔 1 秒 |
| `loguru` | 日志 | 控制台 + 按天切文件，10MB 轮转，保留 7 天 |
| `Pillow` | 图像处理与产物校验 | 生成测试图、解码响应、读像素与 alpha |
| `flask` | 起被测服务 | 仅 `mock_server` 使用 |

安装：

```powershell
pip install -r requirements.txt
```

## 目录与职责

| 路径 | 职责 |
| --- | --- |
| `api/collage_api.py` | 13 个接口的封装：上传、素材、六种编辑、拼图、导出，只拼参数不做断言 |
| `common/image_lib.py` | 产物工具：生成纯色/图形测试图、解码 base64、读尺寸、透明占比、像素、平均亮度、灰度判定、像素差异 |
| `common/conf_handler.py` | 读 `config/env.yaml`，用 `config/env_local.yaml` 深度覆盖，产出 `config` 单例 |
| `common/request_handler.py` | 请求封装：拼 URL、算签名、带 token、401 重登、记日志，产出 `client` 单例 |
| `common/logger_handler.py` | loguru 初始化，输出到 `report/logs/collage_api_日期.log` |
| `common/assert_handler.py` | 软断言。一条用例里多个检查点全部执行完再统一抛错 |
| `config/env.yaml` | local / ci 两套地址，外加 Mock 账号与签名密钥 |
| `data/collage_data.yaml` | 滤镜清单、调整/模糊/文字/边框/间距的边界值与预期 |
| `testcases/conftest.py` | `client` 与 `api` fixture，`prepared_env` 负责复位素材并登录 |
| `testcases/test_image_upload.py` | 上传：格式白名单、体积与像素上限、内容合法性 |
| `testcases/test_edit.py` | 抠图、滤镜、调整、模糊、文字、边框、背景 |
| `testcases/test_collage.py` | 模板、贴纸、拼图合成、导出 |
| `mock_server/app.py` | 被测服务，13 个业务接口 + `/health` + `/__admin/reset` |
| `run.py` | 起服务、跑用例、生成报告的入口 |
| `Jenkinsfile` / `docker-compose.yml` | 流水线和容器编排 |

`api` 和 `common` 的分界：`api` 只描述「哪个接口、传什么」，`common` 只负责「怎么发出去、怎么记录」。图像层的判断全部集中在 `image_lib.py`。

## 跑起来

```powershell
# 方式一：一条命令（自动起服务、跑完自动关）
python run.py

# 方式二：分开执行，方便看日志
python mock_server/app.py      # 终端 1，保持前台运行
pytest                          # 终端 2

# 只跑某一类
pytest testcases/test_edit.py -k 抠图
```

正常输出结尾：

```
============================= 56 passed in 1.52s =============================
```

服务单独起时先确认它活着：

```powershell
curl http://127.0.0.1:9400/health
# {"service":"mock-collage-api","sign_check":false,"status":"ok"}
```

## 一次请求的调用链

以「抠图」为例：

```
testcases/test_edit.py::test_cutout_removes_background
  → api/collage_api.py::CollageApi.cutout(image_id, bg_color, tolerance)
  → common/request_handler.py::send()                 算 X-Sign、带 token、发请求、记日志
  → mock_server/app.py::cutout()                      取图、算与背景色的差值、生成 alpha 蒙版
  → 返回 {"code":200,"data":{"image_id":...,"base64":"...","width":400,"height":300}}
  → common/image_lib.py::alpha_ratio() / pixel_at()    解码产物，查透明占比与指定像素
  → common/assert_handler.py::finish()                 汇总所有检查点
```

## 接口清单

| 模块 | 方法 | 路径 | 主要校验 |
| --- | --- | --- | --- |
| 登录 | POST | `/user/login` | 用户名空 → 400；密码错 → 401 |
| 上传 | POST | `/image/upload` | 格式白名单 png/jpg/jpeg/webp；空内容、非法 base64、超 4MB、单边超 4096 像素 → 400 |
| 素材 | GET | `/asset/templates` | 返回 3 个模板及各自槽位数 |
| 素材 | GET | `/asset/stickers` | 返回 4 个贴纸 |
| 抠图 | POST | `/edit/cutout` | `bg_color` 需 `#RRGGBB`；`tolerance` 0-100；输出 RGBA，背景像素 alpha=0 |
| 滤镜 | POST | `/edit/filter` | 支持 grayscale/sepia/warm/cool/vivid；其他值 → 400 |
| 调整 | POST | `/edit/adjust` | brightness/contrast/saturation 各 0-200，100 为原图；三项全空 → 400 |
| 模糊 | POST | `/edit/blur` | `radius` 0-50，0 表示原样返回 |
| 文字 | POST | `/edit/text` | 文字 1-20 字符；位置 top-left/center/bottom-right；字号 12-72 |
| 边框 | POST | `/edit/border` | `width` 1-50，输出尺寸 = 原尺寸 + 2×width |
| 背景 | POST | `/edit/background` | `color` 需 `#RRGGBB`，透明图合成到色底，尺寸不变 |
| 拼图 | POST | `/collage/compose` | 模板 row_2/row_3/grid_2x2；图片数量须等于槽位；`gap` 0-20 |
| 导出 | POST | `/export` | `format` png/jpg；`quality` 1-100；PNG 保留 alpha，JPG 转 RGB 并铺白 |

业务码约定：HTTP 状态码统一 200，响应体 `code` 区分结果
（200 成功 / 400 参数或状态非法 / 401 未登录或签名错误 / 404 图片或模板不存在）。

## 内置素材

`/__admin/reset` 会重建 5 张固定素材，用例直接用这些 id，不依赖上传用例的执行顺序：

| image_id | 尺寸 | 内容 | 用途 |
| --- | --- | --- | --- |
| `img_demo_1` | 400×300 | 纯红 RGB | 滤镜、调整、模糊、文字、边框 |
| `img_demo_2` | 400×300 | 蓝白渐变 RGB | 拼图 |
| `img_demo_3` | 300×400 | 纯绿竖图 RGB | 四宫格（验 cell 取最大边） |
| `img_demo_shape` | 400×300 | 白底 + 正中红圆 | 抠图（背景去除、主体保留） |
| `img_demo_alpha` | 200×200 | 透明底蓝色方块 | 抠图产物、背景合成、导出 JPG 转 RGB |

## 用例清单

| 用例类 | 条数 | 覆盖点 |
| --- | --- | --- |
| `TestImageUpload` | 6 | PNG/JPG 上传、格式不在白名单、空内容、非法 base64、单边像素超限 |
| `TestCutout` | 4 | 去背景（透明占比 + 主体像素不透明）、容差 0 与 100 两端、容差越界、图片不存在 |
| `TestFilter` | 6 | 五种滤镜逐个验证（灰度额外断言 R=G=B）、非法滤镜 |
| `TestAdjust` | 7 | 亮度提升前后平均亮度对比、参数 0/200 边界与越界、非整数、三项全空 |
| `TestBlur` | 4 | 半径 0 两次输出一致、半径 50 上限、51 越界 |
| `TestText` | 7 | 叠加文字（尺寸不变 + 像素出现差异）、字号 12/72 与 11、21 字超长、空文字、非法位置 |
| `TestBorder` | 4 | 宽度 10 时尺寸外扩 20、宽度 1/50 边界、0 非法 |
| `TestBackground` | 2 | 透明图合成纯色（四角为底色、主体保留原色）、非法色值 |
| `TestAsset` | 2 | 模板数量与槽位、贴纸数量 |
| `TestCompose` | 9 | 横向两格、带间距、横向三格、四宫格（cell 取最大边）、数量不匹配、模板不存在、间距 0/20/21 |
| `TestExport` | 5 | 导出 PNG 保留 RGBA、透明图导出 JPG 转 RGB、非法格式、质量越界、质量 1 与 100 的产物体积对比 |

合计 54 条。

## 产物怎么校验

这是这个项目和前几个纯 JSON 项目最大的区别：断言不止于 `code`，而是解码图片后检查真实像素。

| 校验点 | 方法 | 典型用例 |
| --- | --- | --- |
| 尺寸 | `image_size(b64)` 返回 `(w, h)` | 边框外扩、拼图合成、编辑后尺寸不变 |
| 透明占比 | `alpha_ratio(b64)` 返回 alpha=0 的像素比例 | 抠图应大于 0.3 |
| 指定像素 | `pixel_at(b64, x, y)` 返回 RGBA 元组 | 抠图后圆心 alpha=255、四角 alpha=0；背景合成后四角为底色 |
| 灰度判定 | `is_grayscale(b64)` 抽样比对 R=G=B | 灰度滤镜 |
| 平均亮度 | `average_brightness(b64)` 返回 0-255 | 亮度调高后应变亮 |
| 像素差异 | `differs_from(a, b)` 比对两张图的字节 | 文字叠加后画面必须变化；模糊半径 0 必须一致 |

改断言前先跑一次当前结果，避免把校验方法的问题误判成业务缺陷。

## 配置

`config/env.yaml`：

```yaml
current_env: "local"

local:
  base_url: "http://127.0.0.1:9400"
  timeout: 15
  sign_key: "mock-sign-key-2026"

ci:
  base_url: "http://host.docker.internal:9400"
  timeout: 20
  sign_key: "mock-sign-key-2026"

account:
  username: "testuser"
  password: "123456"
```

| 字段 | 含义 | 说明 |
| --- | --- | --- |
| `current_env` | 默认生效的环境名 | 可被 `ENV` 环境变量覆盖 |
| `base_url` | 接口根地址 | 可被 `BASE_URL` 覆盖，CI 里用这个注入 |
| `timeout` | 请求超时（秒） | 图片接口返回体积较大，比纯 JSON 项目放宽 |
| `sign_key` | 签名密钥 | 必须与服务端 `SIGN_KEY` 一致 |
| `account` | 登录账号 | Mock 服务的固定账号，不是真实凭据 |

生效顺序：`BASE_URL` / `ENV` 环境变量 → `config/env_local.yaml` → `config/env.yaml`。

## 新增一条用例

### 只加场景，不改逻辑

在 `data/collage_data.yaml` 对应分组下加一项，代码不动：

```yaml
# data/collage_data.yaml
blur_cases:
  - case_name: "模糊半径 12"
    radius: 12
    expect: 200
```

```powershell
pytest testcases/test_edit.py -k "模糊半径 12"
```

`expect.msg` 可选，写了就检查提示是否包含该关键字，不写只比业务码。

### 加一个新接口

四步：

1. `mock_server/app.py` 加路由与校验，需要新状态就一并加进 `/__admin/reset`。
2. `api/collage_api.py` 加方法，只拼参数。
3. 需要参数化的场景在 `data/` 下开分组。
4. `testcases/` 里加用例：成功路径校验产物，失败路径校验业务码与提示。

```python
# api/collage_api.py
def rotate(self, image_id: str, angle: int):
    return self.client.post("/edit/rotate", json={"image_id": image_id, "angle": angle})
```

需要新的产物校验维度（比如通道数、色彩饱和度）时，先在 `common/image_lib.py` 加函数，再在用例里调用。

## 关于签名

请求头带 `X-Sign`，客户端与服务端各实现一次，必须一致：

```
sign = MD5( METHOD + path + 按键排序的 "k=v" 拼接 + "&key=" + sign_key )
```

- 客户端：`common/request_handler.py::make_sign()`
- 服务端：`mock_server/app.py::make_sign()`

服务端由 `SIGN_CHECK` 控制是否强制校验，默认 `false`。排查用例失败时不必先怀疑签名；
要验证签名链路时打开：

```powershell
$env:SIGN_CHECK = "true"; python mock_server/app.py
```

## 测试数据与状态

服务端在内存里维护两项状态，`POST /__admin/reset` 恢复初始值：

| 状态 | 含义 | 初始值 |
| --- | --- | --- |
| `images` | 图片仓库，编辑产物也存进来 | 5 张内置素材 |
| `seq` | 图片 ID 自增序号 | 0 |

编辑接口都是「读原图 → 生成新图 → 存回仓库 → 返回新 id」，不修改原图。
所以用例可以反复编辑同一张素材，互不影响；依赖「图片不存在」的用例用固定假 id（如 `img_not_exist`）。

## 报告与日志

```powershell
pytest
allure generate report/allure_raw -o report/allure_html --clean
allure open report/allure_html
```

- 控制台：每条用例的软断言明细（`[PASS]` / `[FAIL] 期望= 实际=`）
- 日志：`report/logs/collage_api_YYYYMMDD.log`，含请求体、响应状态码与响应片段（base64 只截前 400 字符）
- Allure：按 feature/story 分组，失败用例能定位到具体断言

## CI

**Docker Compose**

```powershell
docker compose up -d mock-collage          # 只起被测服务
docker compose run --rm api-test           # 起服务 + 跑用例
docker compose down
```

两个容器在同一 compose 网络里，用例容器 `BASE_URL` 指向 `http://mock-collage:9400`。

**Jenkins**

`Jenkinsfile` 分四段：拉代码 → 轮询 `/health` 等待服务就绪 → 装依赖 → 执行 pytest。
服务没起来直接失败，不会出现「环境没起、用例全红、以为是代码问题」。
报告由 `post` 段发布 JUnit + Allure。

## 排错对照

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'PIL'` | 没装 Pillow，或包目录命名异常 | `pip install --force-reinstall Pillow` |
| `ConnectionError` / reset 失败 | 被测服务没起 | `python mock_server/app.py`，或直接用 `python run.py` |
| 抠图用例透明占比不达标 | 容差过小，与背景色差值没被覆盖 | 调 `tolerance`，或确认素材背景色与 `bg_color` 一致 |
| 拼图宽度断言失败 | 图片高度不同导致缩放比例不同 | 用等高素材；或按缩放后的宽度重算预期 |
| 导出 JPG 的 mode 不是 RGB | 服务端没做透明合成 | 检查 `/export` 的 JPEG 分支 |
| `PyYAML` 报 `yaml.safe_load` 返回 None | data 文件被清空 | 检查 `data/collage_data.yaml` 缩进 |
| allure 命令找不到 | 只装了 `allure-pytest` | 装 allure 命令行；用例本身不受影响 |

## 已知限制

- 图片仓库在内存里，重启即清空；不支持并发写入同一素材。
- 图片处理基于 Pillow 的通用算法，抠图是「按背景色差值生成蒙版」，不是人像分割模型。
- 文字只支持 ASCII，默认字体不含中文字形。
- 拼图不提供拖拽坐标、缩放倍数、旋转角度这类自由布局参数，只按模板槽位等比排布。
