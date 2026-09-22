#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  console.error("Usage: node review_geoport_training_batch.mjs INPUT OUTPUT");
  process.exit(2);
}

const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const reviews = {
  "geoport.pdf": {
    rename: {
      0: "台2線70.1K崩塌事件",
      2: "前期降雨",
      3: "厚層砂岩偶夾頁岩",
      4: "薄砂頁互層",
      5: "現場堆積最大岩塊",
      11: "土石掩蓋範圍",
      13: "剪動岩層",
      28: "邊坡地質剖面",
      31: "石底層（St）",
      32: "大寮層（Tl）",
      34: "台2線路面",
      42: "F層厚層砂岩",
      43: "6月3日劣化點",
      47: "崩崖",
      50: "傾覆破壞機制",
      53: "台2線70.1K路段",
      54: "碉堡（Pillbox）",
      55: "混凝土塊",
    },
    rejectNodes: [6, 12, 14, 15, 16, 17, 18, 19, 20, 21, 33, 35, 36, 51, 52, 59],
    relations: {
      0: { label: "促成", weight: 0.7 },
      1: false,
      2: false,
      3: false,
      4: { target: 8, label: "上覆於" },
      5: { target: 9, label: "上覆於" },
      6: { target: 10, label: "上覆於" },
      7: false,
      8: false,
      9: false,
      10: { target: 53 },
      11: false,
      12: { source: 28, target: 26, label: "包含" },
      13: false,
      14: { label: "發育於" },
      15: false,
      16: false,
      17: false,
      18: { source: 54, label: "位於" },
      19: { label: "發生" },
      20: { label: "導致" },
      21: { label: "導致" },
      22: { label: "分布於" },
      23: { label: "觀測於" },
      27: { label: "控制" },
      28: { source: 47, label: "伴隨" },
      30: { source: 50, label: "導致" },
      31: { label: "包含" },
      32: { label: "包含" },
      33: false,
      34: false,
    },
  },
  "geoport2.pdf": {
    rename: {
      0: "台2線70.1K崩塌事件",
      2: "前期降雨",
      3: "厚層砂岩偶夾頁岩",
      4: "薄砂頁互層",
      5: "現場堆積最大岩塊",
      17: "倒懸岩體",
      19: "2023-04-28落石災害",
      20: "2024-06-04崩塌災害",
      23: "崩塌面積",
      24: "損失量體",
      25: "堆積量體",
      26: "災前後DoD分析",
      34: "崩積岩礫",
      39: "脆性破裂面",
      41: "低岩橋比例",
      48: "高度風化",
      58: "砂頁岩互層",
    },
    rejectNodes: [9, 10, 21, 22, 31, 32, 33, 35, 57],
    relations: {
      0: { label: "支撐" },
      1: { label: "發生" },
      2: { source: 2, target: 0, label: "促成", weight: 0.7 },
      3: { label: "出露於" },
      4: { label: "出露於" },
      5: { label: "出露於" },
      8: { label: "觀測於" },
      9: { label: "施作於" },
      10: false,
      11: false,
      12: false,
      13: { source: 0, label: "產生" },
      14: { source: 0, label: "產生" },
      15: { label: "估算" },
      16: false,
      17: false,
      18: false,
      19: { label: "伴隨" },
      20: false,
      21: { label: "發育" },
      22: false,
      23: { label: "觀測於" },
      24: { label: "促成" },
      25: { label: "分布於" },
      26: { label: "呈現" },
      27: { label: "發育" },
      28: { label: "觀測到" },
      33: { label: "分布於" },
      34: false,
      35: false,
      36: { target: 0, label: "促成" },
    },
  },
};

function normalizeText(text) {
  return text
    .replaceAll("案子2號70.1K", "台2線70.1K")
    .replaceAll("案2線70.1K", "台2線70.1K")
    .replaceAll("案 2 線 70.1K", "台2線70.1K")
    .replaceAll("3案2號70.1K", "台2線70.1K")
    .replaceAll("台2線70.1k", "台2線70.1K")
    .replaceAll("台2線 70.1k", "台2線70.1K")
    .replaceAll("厚層砂岩偶致頁岩", "厚層砂岩偶夾頁岩")
    .replaceAll("厚層砂岩偶成頁岩", "厚層砂岩偶夾頁岩")
    .replaceAll("薄層頁石頁層", "薄砂頁互層")
    .replaceAll("薄層頁石頁岩", "薄砂頁互層")
    .replaceAll("砂頁岩交錯層", "砂頁岩互層")
    .replaceAll("砂頁岩交層", "砂頁岩互層")
    .replaceAll("大壩層", "大寮層")
    .replaceAll("太陽層", "大寮層")
    .replaceAll("裂劃", "脆性破裂面")
    .replaceAll("西側邊量", "西側邊界")
    .replaceAll("破岩體", "破碎岩體")
    .replaceAll("前場事件", "崩塌事件")
    .replaceAll("推積體積", "堆積量體")
    .replaceAll("損失體積", "損失量體")
    .replaceAll(" mPa", " MPa");
}

const review = reviews[input.filename];
if (!review) throw new Error(`No review rules for ${input.filename}`);

const nodes = input.nodes.map((node) => {
  const index = Number(node.id.split(":")[1]);
  return {
    ...node,
    label: review.rename[index] ?? node.label,
    text: normalizeText(node.text),
    approved: !review.rejectNodes.includes(index),
  };
});

const nodeId = (index) => `knowledge:${index}`;
const relations = input.relations.map((relation) => {
  const index = Number(relation.id.split(":")[1]);
  const change = review.relations[index];
  if (change === false) return { ...relation, approved: false };
  if (!change) return relation;
  return {
    ...relation,
    source_node_id: change.source === undefined ? relation.source_node_id : nodeId(change.source),
    target_node_id: change.target === undefined ? relation.target_node_id : nodeId(change.target),
    label: change.label ?? relation.label,
    weight: change.weight ?? relation.weight,
    approved: true,
  };
});

const approvedNodeIds = new Set(nodes.filter((node) => node.approved).map((node) => node.id));
for (const relation of relations) {
  if (!approvedNodeIds.has(relation.source_node_id) || !approvedNodeIds.has(relation.target_node_id)) {
    relation.approved = false;
  }
}

const result = { ...input, nodes, relations };
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`);

console.log(JSON.stringify({
  filename: input.filename,
  approved_nodes: nodes.filter((node) => node.approved).length,
  rejected_nodes: nodes.filter((node) => !node.approved).length,
  approved_relations: relations.filter((relation) => relation.approved).length,
  rejected_relations: relations.filter((relation) => !relation.approved).length,
}, null, 2));
