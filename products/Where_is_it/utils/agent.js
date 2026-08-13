// 意图类型
const INTENTS = {
  UPDATE_LOCATION: 'update_location',
  QUERY_LOCATION: 'query_location',
  ADD_ITEM: 'add_item',
  SET_REMINDER: 'set_reminder'
};

// 已知物品名（动态从 storage 加载）
function getKnownItemNames() {
  try {
    const storage = require('./storage');
    return storage.getItems().map(i => i.name);
  } catch (e) {
    return [];
  }
}

// 核心解析函数
function parse(text) {
  const cleaned = text.trim().replace(/[，。！？、]/g, ',').replace(/\s+/g, ' ');

  // 句式1: "[物品]在哪" (必须放在 update 之前，防止 "在哪" 中的 "在" 被 update 模式匹配)
  const queryMatch = cleaned.match(/(.{1,10})在哪/);
  if (queryMatch) {
    return {
      intent: INTENTS.QUERY_LOCATION,
      item: queryMatch[1].trim()
    };
  }

  // 句式2: "[物品]在[位置]" / "[物品]放[位置]" / "把[物品]放[位置]"
  const updatePatterns = [
    /(?:把)?(.{1,10}?)(?:放|在)(.{1,30})/,
  ];

  for (const pat of updatePatterns) {
    const m = cleaned.match(pat);
    if (m) {
      const itemName = m[1].trim();
      const location = m[2].trim();
      const known = getKnownItemNames();
      const matched = known.find(k => itemName.includes(k) || k.includes(itemName));

      return {
        intent: INTENTS.UPDATE_LOCATION,
        item: matched || itemName,
        location: location,
        isNewItem: !matched
      };
    }
  }

  // 句式3: "添加[物品]" / "新增[物品]" / "记住[物品]"
  const addMatch = cleaned.match(/(?:添加|新增|记住|加一个?)(.{1,20})/);
  if (addMatch) {
    return {
      intent: INTENTS.ADD_ITEM,
      item: addMatch[1].trim()
    };
  }

  // 句式4: "提醒我带[物品]" / "出门带[物品]"
  const remindMatch = cleaned.match(/(?:提醒|出门|别忘了?)(?:我|带)?(.{1,20})/);
  if (remindMatch) {
    return {
      intent: INTENTS.SET_REMINDER,
      item: remindMatch[1].trim()
    };
  }

  // Fallback: 当更新位置处理
  return {
    intent: INTENTS.UPDATE_LOCATION,
    item: cleaned.length > 10 ? cleaned.substring(0, 10) : cleaned,
    location: cleaned,
    isNewItem: true
  };
}

// === LLM 接口（预留，不接入） ===
// 未来如需接 LLM：
// async function parseLLM(text) {
//   const res = await wx.request({
//     url: 'https://your-api/parse',
//     method: 'POST',
//     data: { text }
//   });
//   return res.data;
// }

module.exports = { parse, INTENTS };
