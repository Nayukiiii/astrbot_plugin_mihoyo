# astrbot_plugin_mihoyo

> 原神 & 崩坏：星穹铁道 查询插件，基于 AstrBot 框架。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-purple)](https://github.com/Soulter/AstrBot)

---

## 功能

| 指令 | 说明 |
|------|------|
| `/崩 便笺` | 开拓力 / 每日实训 / 模拟宇宙 / 委托派遣 |
| `/崩 签到` | HoYoLAB 每日签到 |
| `/崩 忘却 [上期]` | 忘却之庭 |
| `/崩 虚构 [上期]` | 虚构叙事 |
| `/崩 差分 [上期]` | 差分宇宙 |
| `/崩 抽卡 角色\|光锥\|常驻\|新手` | 跃迁统计 |
| `/原 便笺` | 原粹树脂 / 委托 / 洞天宝钱 / 质变仪 |
| `/原 签到` | HoYoLAB 每日签到 |
| `/原 深渊 [上期]` | 深境螺旋 |
| `/原 抽卡 角色\|武器\|常驻\|新手` | 祈愿统计 |
| `/米 登录` | 绑定米游社账号（手机验证码） |
| `/米 解绑` | 解除绑定 |
| `/米 账号` | 查看已绑定信息 |

---

## 安装

```bash
# 在 AstrBot 插件目录下
git clone https://github.com/your-username/astrbot_plugin_mihoyo.git
cd astrbot_plugin_mihoyo
pip install -r requirements.txt
```

渲染卡片所需的图像资源（来自 [StarRailUID](https://github.com/baiqwerdvd/StarRailUID)）会在首次使用时自动从 GitHub 下载，无需手动操作。如果网络受限，可参考下方「手动下载资源」说明。

---

## 配置

在 AstrBot 插件配置中填写以下项：

```yaml
proxy:
  login_proxy_url: ""          # 登录时使用的 SOCKS5 代理（可选）
  geetest_proxy_url: ""        # 极验过码使用的代理（可选，推荐住宅 IP）

captcha:
  provider: "manual"           # 验证码方式：manual / ttocr / capsolver
  ttocr_appkey: ""             # ttocr API Key（provider=ttocr 时必填）
  capsolver_apikey: ""         # Capsolver API Key（provider=capsolver 时必填）
  geetest_server_url: "https://geetest.utautai.org"  # 手动验证服务器地址

login:
  max_wait: 300                # 登录等待超时（秒）

gacha:
  sync_limit: 0                # 单次同步最多拉取的页数（0=不限制）
```

---

## 技术说明

### 便笺接口策略

崩铁便笺优先走 **Widget 接口**，不触发极验（10041），只有 Widget 失败时才 fallback 到 `/api/note` + 极验过码流程。

原神便笺暂时使用 genshin.py 路径，待后续迁移到原神 Widget 接口。

---

## 逆向研究记录

> 本节记录从米游社 APK（v2.71.1）逆向得到的技术细节，供社区参考。
> 工具：jadx（反编译）、Ghidra（native 分析）。

---

### DS Salt 完整对照表

米游社使用动态签名（Dynamic Sign，DS）对每个请求进行签名校验。不同接口域名使用不同的 salt。

#### 普通战绩接口 Salt

```
xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs
```

- **对应域名**：`api-takumi-record.mihoyo.com`（`API_RECORD`）
- **逆向来源**：`libxxxx.so` 中 `ANDROID_SALT` 数组，使用掩码 `0xbde26df4 / 0x4200194` 解密
- **调用函数**：`Java_com_mihoyo_hyperion_net_aaaaa_b5555`（`bbbbb.a22` 为无参版本）
- **算法**：`MD5("salt=<salt>&t=<timestamp>&r=<random>&b=<body>&q=<query>")`，r 为随机整数 100001-200000

#### Widget 接口 Salt（本次新增）

```
t0qEgfub6cvueAPgR5m9aQWWVciEer7v
```

- **对应接口**：
  - `/game_record/app/hkrpg/aapi/widget`（崩铁便笺 Widget）
  - `/game_record/app/genshin/aapi/widget/v2`（原神便笺 Widget）
  - `/apihub/app/api/signIn`（签到）
- **逆向来源**：`libxxxxxx.so` 中 `ANDROID_SALT` 数组，使用掩码 `0x5efebb5e / 0x400a0102` 解密
- **调用函数**：`Java_com_mihoyo_hyperion_net_aaaaa_a2222`
- **路由规则**：由 `jn.l.intercept`（OkHttp 拦截器）判断，白名单路径使用此 salt，其余使用普通 salt

#### 账号 SDK Salt

```
JwYDpKvLj6MrMqqYU6jTKF17KNO2PXoS
```

- **对应域名**：`bbs-api.miyoushe.com`（社区接口）
- **逆向来源**：`com.mihoyo.platform.account.sdk.network.RequestUtils.SALT_PROD`（Java 层明文）
- **算法**：DS1，r 为 6 位字母数字字符串

#### 其他已知 Salt

| Salt | 说明 |
|------|------|
| `4kswrgm` | DS2 无参版本（`bbbbb.a22`，`libdddd.so`） |
| `q7fej8vtzitt26yl24kswrgm` | DS1 旧版（`bbbbb.a11`，`libdddd.so`） |
| `swxdtzit6yltz1i5sfaayltzitds2t26yl` | JSBridge `getDS` 返回值（`bbbbb.a`） |
| `qeutrewq` | DS1 极短 salt（`bbbbb.a1`，用途待确认） |

---

### ANDROID_SALT 解密算法

两个 so 文件中的 salt 均以加密整数数组形式存储，解密逻辑如下：

```python
import math, ctypes

def decrypt_salt(android_salt: list[int], mask1: int, mask2: int) -> str:
    result = []
    for i in range(32):
        val = ctypes.c_int32(android_salt[i]).value
        bit1 = (mask1 >> (i & 0x3f)) & 1
        bit2 = (mask2 >> (i & 0x3f)) & 1
        if bit1 == 0:
            c = (val // 3) + 0x30
        elif bit2 == 0:
            c = (~val) & 0xFF
        else:
            c = int(math.log(float(-val)) / 1.0986122886681098 + -6.0 + 48.0)
        result.append(c & 0xFF)
    return ''.join(chr(c) for c in result)

# libxxxx.so（普通战绩 salt）
ANDROID_SALT_XXXX = [
    0xD8, 0x72, 0xFFB70487, 0xD2, 0xFFFF1957, 0xFFFFFFAE, 0xFFFFFF8A, 0xFFFD4C05,
    # ... 完整数组见源码
]
# decrypt_salt(ANDROID_SALT_XXXX, 0xbde26df4, 0x4200194)
# => "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"

# libxxxxxx.so（widget salt）
ANDROID_SALT_XXXXXX = [
    0xCC, 0xFFFFFD27, 0xFFFFFF8E, 0xFFFFFFBA, 0xFFFFFF98, 0xA2, 0xFFFFFF8A, 0x96,
    # ... 完整数组见源码
]
# decrypt_salt(ANDROID_SALT_XXXXXX, 0x5efebb5e, 0x400a0102)
# => "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"
```

---

### Widget 接口发现过程

1. 搜索 `hkrpg/aapi/widget` → 找到 `ug.f` 接口定义，确认路径
2. 搜索 `DailyNote` → 全部命中 `miniwidget` 包，确认 APP 便笺走 widget 而非 `/api/note`
3. 分析 `StarRailWidgetProvider` → `StarRailWidgetWorker` → `class f.invokeSuspend` → 调用 `ug.f.a()`
4. 逆向 `jn.l.intercept`（OkHttp 拦截器）→ 发现 widget 路径白名单及 salt 路由规则：

```java
// jn.l 构造函数（部分）
this.f474574b = z0.u(
    "/apihub/app/api/signIn",
    "/game_record/app/genshin/aapi/widget/v2",
    "/game_record/app/hkrpg/aapi/widget"
);

// intercept 方法逻辑
if (路径在白名单中) {
    strDS = aaaaa.a2222(body, query);  // Widget salt
} else {
    strDS = bbbbb.a2222(salt);         // 普通战绩 salt
}
```

---

### `dddd` 混淆框架

米游社使用自研的 `libdddd.so` 混淆 DS 生成逻辑：

- 所有 JNI 函数名均为无意义字符（`bbbbb.a`、`bbbbb.a1`、`bbbbb.a2222` 等）
- salt 以字节数组形式拼接在栈上，不作为字符串存储，jadx/strings 无法直接搜索
- `libxxxxxx.so` / `libxxxx.so` 中的 salt 以加密整数数组存储，运行时解密（见上方算法）
- salt 不通过 `JNI_OnLoad` 注册，而是通过静态命名（`Java_com_mihoyo_hyperion_net_*`）直接暴露

---

### StarRailWidgetData 字段表

逆向自 `com.mihoyo.hyperion.biz.miniwidget.starrail.StarRailWidgetData`：

| JSON Key | 类型 | 说明 |
|----------|------|------|
| `current_stamina` | int | 当前开拓力 |
| `max_stamina` | int | 最大开拓力 |
| `stamina_recover_time` | **int**（秒） | 恢复时间（注意：note 接口此字段为 string） |
| `current_reserve_stamina` | int | 备用开拓力 |
| `is_reserve_stamina_full` | bool | 备用是否满 |
| `current_train_score` | int | 每日实训当前 |
| `max_train_score` | int | 每日实训上限 |
| `current_rogue_score` | int | 模拟宇宙积分 |
| `max_rogue_score` | int | 模拟宇宙上限 |
| `accepted_expedition_num` | int | 已派遣数量 |
| `total_expedition_num` | int | 派遣槽总数 |
| `expeditions` | list | 见下表 |
| `rogue_tourn_weekly_cur` | int | 差分宇宙本周积分 |
| `rogue_tourn_weekly_max` | int | 差分宇宙本周上限 |
| `rogue_tourn_weekly_unlocked` | bool | 是否已解锁差分宇宙 |

`expeditions` 数组元素（`StarRailExpedition`）：

| JSON Key | 类型 | 说明 |
|----------|------|------|
| `name` | string | 派遣名称 |
| `remaining_time` | **int**（秒） | 剩余时间（注意：note 接口此字段为 string） |
| `status` | string | `"Ongoing"` 或 `"Finished"` |
| `avatars` | list[string] | 角色头像 URL 列表 |

---

## 资源声明

卡片渲染资源（`render/*/texture2D/`）来自 [baiqwerdvd/StarRailUID](https://github.com/baiqwerdvd/StarRailUID)，遵循 **GPL-3.0 License**。

本项目同样以 **GPL-3.0** 协议开源。

---

## 手动下载资源

如果自动下载失败，可手动从以下链接下载资源文件：

- 便笺资源：`StarRailUID/starrailuid_note/texture2D/`
- 深渊资源：`StarRailUID/starrailuid_abyss_boss/texture2D/`

下载后放入对应的 `render/notes/texture2D/` 和 `render/abyss/texture2D/` 目录。

---

## 免责声明

本项目仅供学习研究使用，请勿用于商业用途。使用本插件导致的账号风险由使用者自行承担。
