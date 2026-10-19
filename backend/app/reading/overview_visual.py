"""Illustration selection is presentation data, never a paper evidence claim."""

PAPER_THEMES = {
    '2610.06852': 'flowchart-scene',
    '2610.06851': 'cue-scene',
    '2610.06846': 'bias-scene',
    '2610.06844': 'diffusion-scene',
    '2610.06843': 'robot-scene',
    '2610.13948': 'wiki-navigation-scene',
    '2610.13935': 'concept-mask-scene',
    '2610.13909': 'regression-table-scene',
    '2610.13895': 'attention-role-scene',
    '2610.13889': 'tool-reliability-scene',
}

CAPTIONS = {
    'flowchart-scene': ('宽屏流程图 → 检查连接 → 竖屏重排。',
                        'Widescreen flowchart → check connections → portrait layout.'),
    'cue-scene': ('数学题 → 在回答前加入一小段开头 → 逐步推理。效果只限论文测试的特定模型。',
                  'Math problem → add a short opening cue → stepwise reasoning. The reported effect is model-specific.'),
    'bias-scene': ('同一对象、不同背景或水印 → 约束模型内部的虚假分离 → 减少对捷径的依赖。',
                   'Same object with different backgrounds or marks → constrain spurious feature separation → reduce shortcut reliance.'),
    'diffusion-scene': ('未成型的图像 → 读取内部上下文词元 → 探测其中已有的画面信息。',
                        'Unfinished image → read contextual tokens → probe the image information already present.'),
    'robot-scene': ('完整演示视频 → 分层目录 → 按需调出关键片段。',
                    'Full demonstration video → hierarchical index → retrieve a needed clip.'),
    'wiki-navigation-scene': ('从维基百科起点出发 → 只沿可见链接前进 → 比较到达目标的路径。',
                              'Start on Wikipedia → follow visible links → compare routes to the goal.'),
    'concept-mask-scene': ('观察黑箱模型的概念线索 → 暂时隐藏一部分 → 看解释如何变化。',
                           'Inspect a black-box model’s concept clues → hide some → see how the explanation changes.'),
    'regression-table-scene': ('表格输入与连续数值目标 → 调整训练目标 → 检查统一提前停止的局限。',
                               'Tabular inputs and numeric targets → change the training objective → examine limits of global early stopping.'),
    'attention-role-scene': ('同一模型组件 → 置于不同任务语境 → 对比其作用是否变化。',
                             'The same model component → different task contexts → compare how its role changes.'),
    'tool-reliability-scene': ('代理面对多个候选工具 → 观察执行过程中的可靠性 → 决定检索哪个工具。',
                               'An agent considers candidate tools → tracks reliability during execution → chooses a tool to retrieve.'),
}


def visual_for_paper(paper):
    theme = PAPER_THEMES.get(paper['paper_id'])
    if theme is None:
        return None
    zh, en = CAPTIONS[theme]
    return {'theme': theme, 'caption_zh': zh, 'caption_en': en,
            'kind': 'concept_illustration'}
