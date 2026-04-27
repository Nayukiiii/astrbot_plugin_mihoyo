# astrbot_plugin_mihoyo

> 原神 & 崩坏：星穹铁道 查询插件，基于 AstrBot 框架。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-purple)](https://github.com/Soulter/AstrBot)

---

## 功能

### 崩坏：星穹铁道

| 指令 | 内容 | 说明 |
|------|------|------|
| `/崩 便笺` | 开拓力 / 后备开拓力 / 每日实训 / 模拟宇宙 | 优先使用 Widget 接口，失败时回退到实时便笺接口 |
| `/崩 签到` | 每日签到 | 支持米游社签到 |
| `/崩 忘却 [上期]` | 忘却之庭 | 支持本期 / 上期战绩卡 |
| `/崩 虚构 [上期]` | 虚构叙事 | 支持本期 / 上期战绩卡 |
| `/崩 末日 [上期]` | 末日幻影 | 支持本期 / 上期战绩卡，`/崩 差分` 作为兼容别名保留 |
| `/崩 抽卡 角色\|光锥\|常驻\|新手` | 跃迁统计 | 通过游戏内抽卡记录链接导入 authkey 后查询 |
| `/崩 抽卡 链接 <URL>` | 记录抽卡 authkey | 保存后可直接查询对应卡池 |

### 原神

| 指令 | 内容 | 说明 |
|------|------|------|
| `/原 便笺` | 原粹树脂 / 每日委托 / 洞天宝钱 / 质变仪 / 探索派遣 | 使用 genshin.py 路径 |
| `/原 签到` | 每日签到 | 支持米游社签到 |
| `/原 深渊 [上期]` | 深境螺旋 | 支持本期 / 上期战绩卡 |
| `/原 抽卡 角色\|武器\|常驻\|新手` | 祈愿统计 | 通过游戏内抽卡记录链接导入 authkey 后查询 |
| `/原 抽卡 链接 <URL>` | 记录抽卡 authkey | 保存后可直接查询对应卡池 |

### 账号

| 指令 | 说明 |
|------|------|
| `/米 登录` | 绑定米游社账号（手机验证码） |
| `/米 验证` | 完成验证码登录流程 |
| `/米 解绑` | 解除绑定 |
| `/米 账号` | 查看已绑定信息 |

### 开发中

以下模块已具备 StarRailUID 风格渲染层，后续会继续接入 API 与指令：

- `/崩 异相`：异相仲裁
- `/崩 货币战争`
- `/崩 模拟宇宙`
- `/崩 蝗灾`：寰宇蝗灾
- `/崩 月报` / `/崩 阅历`
- `/崩 角色`

---

## 安装

```bash
# 在 AstrBot 插件目录下
git clone https://github.com/your-username/astrbot_plugin_mihoyo.git
cd astrbot_plugin_mihoyo
pip install -r requirements.txt
```

渲染卡片所需的图像资源来自 [StarRailUID](https://github.com/baiqwerdvd/StarRailUID)，仓库内已保留常用资源。若部署环境缺少部分资源，可参考下方「手动下载资源」说明补齐。

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

卡片渲染资源（`render/starrailuid_vendor/*/texture2D/`）来自 [baiqwerdvd/StarRailUID](https://github.com/baiqwerdvd/StarRailUID)，遵循 **GPL-3.0 License**。

本项目同样以 **GPL-3.0** 协议开源。

---

## 手动下载资源

如果自动下载失败，可手动从以下链接下载资源文件：

- 崩铁便笺：`StarRailUID/starrailuid_stamina/texture2D/`
- 崩铁忘却之庭：`StarRailUID/starrailuid_abyss/texture2D/`
- 崩铁虚构叙事：`StarRailUID/starrailuid_abyss_story/texture2D/`
- 崩铁末日幻影：`StarRailUID/starrailuid_abyss_boss/texture2D/`
- 崩铁异相仲裁：`StarRailUID/starrailuid_abyss_peak/texture2D/`
- 崩铁模拟宇宙：`StarRailUID/starrailuid_rogue/texture2D/`
- 崩铁货币战争：`StarRailUID/starrailuid_grid_fight/texture2D/`
- 崩铁月报：`StarRailUID/starrailuid_note/texture2D/`

下载后放入对应的 `render/starrailuid_vendor/<模块名>/texture2D/` 目录。

---

## 免责声明

本项目仅供学习研究使用，请勿用于商业用途。使用本插件导致的账号风险由使用者自行承担。
