// Compatibility wording for existing reports: labels change, evidence and
// scientific statements stay intact. Future generations use the new prompt.
const workTypes: Record<string, string> = {
  拓荒: '提出新问题', 修路: '新方法解决已有问题', 加盖: '改进已有方法',
  测绘: '数据集与评测', 勘探: '实证分析', 奠基: '理论分析', 导览: '综述',
};

export function researchWording(text: string, sectionKey: string): string {
  if (sectionKey !== 'address' && sectionKey !== 'quick_card') return text;
  let result = text.replace(/工程类型/g, '研究贡献类型').replace(/地址面包屑/g, '研究定位');
  for (const [old, label] of Object.entries(workTypes)) {
    result = result.replace(new RegExp(`(?:[🏕🛣🏗📐🔍🧱🧭]\\uFE0F?\\s*)?${old}(?=（|\\(|\\s|$)`, 'gu'), label);
  }
  const levels = [['🌍 地球', '研究领域'], ['🗺️ 国家', '子领域'], ['📍 州', '具体研究主题'], ['🏙️ 城市', '关键问题或技术路线'], ['🏠 门牌', '本文方案与贡献']];
  for (const [old, label] of levels) result = result.replaceAll(`### ${old} ·`, `### ${label} ·`);
  result = result.replace(/^### 邻居\s*$/gm, '### 相关工作与区别').replace(/^### 空地\s*$/gm, '### 研究问题与缺口');
  if (sectionKey === 'quick_card') result = result.replace(/[🌍🗺📍🏙🏠]\uFE0F?\s*/gu, '');
  return result.replace('本五级地址为教学定位', '本定位路径用于讲解研究位置');
}
