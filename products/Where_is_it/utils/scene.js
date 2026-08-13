const storage = require('./storage');

const EARTH_RADIUS = 6371000;

// Haversine 公式计算两点距离（米）
function distanceMeters(lat1, lon1, lat2, lon2) {
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return EARTH_RADIUS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// 根据 GPS 坐标匹配最近场景（围栏半径内）
function matchSceneByLocation(lat, lon) {
  const scenes = storage.getScenes();
  for (const s of scenes) {
    if (!s.geo_fence || !s.geo_fence.lat) continue;
    const d = distanceMeters(lat, lon, s.geo_fence.lat, s.geo_fence.lon);
    const radius = s.geo_fence.radius || 200;
    if (d <= radius) return s;
  }
  return null;
}

// 获取当前场景：优先 GPS 自动匹配，fallback 到手动设置
function getCurrentScene() {
  return new Promise((resolve) => {
    wx.getLocation({
      type: 'gcj02',
      success(res) {
        const matched = matchSceneByLocation(res.latitude, res.longitude);
        resolve(matched || storage.getScenes().find(s => s.id === 'home'));
      },
      fail() {
        resolve(storage.getScenes().find(s => s.id === 'home'));
      }
    });
  });
}

// 为场景设置地理围栏
function setSceneGeofence(sceneId, lat, lon, radius) {
  const scene = storage.getScenes().find(s => s.id === sceneId);
  if (!scene) return null;
  scene.geo_fence = { lat, lon, radius: radius || 200 };
  return storage.upsertScene(scene);
}

// 关联物品到场景（场景切换时触发提醒）
function addTriggerItem(sceneId, itemId) {
  const scene = storage.getScenes().find(s => s.id === sceneId);
  if (!scene) return null;
  if (!scene.trigger_items.includes(itemId)) {
    scene.trigger_items.push(itemId);
  }
  return storage.upsertScene(scene);
}

module.exports = {
  getCurrentScene,
  matchSceneByLocation,
  setSceneGeofence,
  addTriggerItem
};
