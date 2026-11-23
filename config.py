"""公共配置：路径、默认阈值、匹配方法等。

这里集中放一些全局可调的东西，方便后面各个 demo 共用。
"""
import sys
from pathlib import Path


def _app_root() -> Path:
    """程序根目录：源码模式是项目根，PyInstaller 打包后是 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _user_data_dir() -> Path:
    """输出/截图等写入位置，确保可写（打包后 exe 目录，失败则退回 ~/.zdhcs）。"""
    root = _app_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except Exception:
        return Path.home() / ".zdhcs"


ROOT = _app_root()
_DATA = _user_data_dir()

ASSETS_DIR = _DATA / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
SCREENSHOTS_DIR = ASSETS_DIR / "screenshots"
LOG_DIR = ROOT / "log"

for _d in (ASSETS_DIR, TEMPLATES_DIR, SCREENSHOTS_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 模板匹配默认阈值。
# 我们默认用 cv2.TM_CCOEFF_NORMED，相似度取值范围是 [-1, 1]，
# 越接近 1 表示越像。0.8~0.9 通常是比较稳的命中区间。
DEFAULT_THRESHOLD = 0.85

# 默认匹配方法（也支持 TM_SQDIFF_NORMED / TM_CCORR_NORMED 等）。
DEFAULT_METHOD = "TM_CCOEFF_NORMED"

# 生成假游戏画面用的尺寸。
FAKE_SCREEN_SIZE = (800, 500)

