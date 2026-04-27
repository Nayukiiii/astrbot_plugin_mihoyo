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

> 底层逆向细节（DS Salt、解密算法、混淆框架等）见 [REVERSE_RESEARCH.md](REVERSE_RESEARCH.md)。

### 便笺接口策略

崩铁便笺优先走 **Widget 接口**，不触发极验（10041），只有 Widget 失败时才 fallback 到 `/api/note` + 极验过码流程。

原神便笺暂时使用 genshin.py 路径，待后续迁移到原神 Widget 接口。

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
