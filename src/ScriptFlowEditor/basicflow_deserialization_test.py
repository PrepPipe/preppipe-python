from pathlib import Path
from ScriptFlowEditor import GameScriptFlow

# 项目根目录（本文件在 src/ScriptFlowEditor/basicflow_deserialization_test.py）
base = Path(__file__).resolve().parent.parent.parent
path = base / "src" / "ScriptFlowEditor" / "generated" / "Demo Flow.json"
flow = GameScriptFlow.load_from_json(path)

print("已加载流程")
print(f"名称: {flow.name}")
print(f"id: {flow.id}")
print(f"标题: {flow.title}")
print(f"注释: {flow.comment}")
print(f"各段落: {flow.segments}")
print(f"各路径: {flow.paths}")
print(f"flag变量: {flow.flags}")