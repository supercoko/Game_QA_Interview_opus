import sys

# 相对导入只会在包内执行；python -m bug_insight 实际从当前包加载 __main__.py。
from .cli import main

# argparse.main() 返回进程退出码：0 表示成功，非 0 表示参数错误或执行失败。
# sys.exit() 会把该退出码交给操作系统，便于脚本和 CI 判断命令是否成功。
sys.exit(main())
