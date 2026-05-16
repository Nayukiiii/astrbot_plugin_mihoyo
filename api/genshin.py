"""
api/genshin.py
原神战绩接口。

目前原神战绩接口触发 1034 极验，challenge 注入无效（待解决）。
暂时保持 genshin.py 调用，待后续逆向原神 1034 处理逻辑后迁移。
"""

# 暂时直接 re-export genshin.py 相关异常，供上层统一处理
import genshin

GenshinException = genshin.GenshinException
GeetestError = genshin.GeetestError
InvalidCookies = genshin.InvalidCookies
DataNotPublic = genshin.DataNotPublic
AlreadyClaimed = genshin.AlreadyClaimed
