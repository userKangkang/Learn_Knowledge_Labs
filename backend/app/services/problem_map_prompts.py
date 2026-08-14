"""Prompt templates for the paper-problem map suggestion flow."""

PROBLEM_MAP_SUGGEST_PROMPT = """你负责从论文问题卡中提炼“共性大问题”，供用户审核后手动落地到论文-问题导图。只依据给出的问题卡与已有共享问题，不联网、不添加论文外资料、不生成学习路线、不替用户决定优先级。
目标：
1. 找出多张问题卡共同指向的共享问题；同一篇论文的多张卡可能指向不同的问题，不同论文的卡可能指向同一问题。
2. 共享问题应抽象到“论文之外仍成立”的层级，但不要空泛到无法指导学习（例如“模型训练效率”可以，“深度学习”不行）。
3. 若某问题与已有共享问题含义吻合，优先复用已有问题 id，不要重复新建；若现有问题太粗或太细，可建议新建并挂在合适的问题之下。
4. 大问题可以分化为子问题：用 parent_key 或 edges 表达层级（大问题 → 子场景/子问题）。
返回严格 JSON，顶层对象包含：
- "problems"：建议新建的共享问题数组；每项 {key, title, description, parent_key}。key 是本地唯一标识（如 "p1"），不要用已有问题 id 作为 key；parent_key 可引用另一个新问题 key 或已有问题 id。
- "edges"：建议的层级边数组；每项 {source_ref, target_ref, relation_label}。ref 可以是已有问题 id 或新问题 key；relation_label 默认 "SPECIALIZES_INTO"，也可写场景描述。
- "card_links"：问题卡关联建议；每项 {problem_card_id, problem_ref, link_type}。problem_ref 是已有问题 id 或新问题 key；link_type 只能 "CORE" 或 "TOUCHED"。
- "note"：一句面向用户的话，说明这次提议的要点。
只返回 JSON，不要输出其它内容。"""
