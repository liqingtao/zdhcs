"""让 pytest 能在项目根目录导入 core/demos 等包。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

