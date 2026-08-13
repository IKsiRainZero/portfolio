# Electron MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Electron 最小可用版本 — 启动后自动运行 Flask 并在窗口中打开 portfolio-app

**Architecture:** Electron 主进程 spawn Python Flask 子进程，轮询就绪后创建 BrowserWindow 指向 localhost:5000。不修改 portfolio-app 现有代码。

**Tech Stack:** Electron 38+, Node.js 22, Python 3.10+ (已有)

---

## 文件结构

```
portfolio/
├── electron/              # 新建目录
│   ├── package.json       # Electron 依赖 + 启动脚本
│   ├── main.js            # 主进程：启动 Flask + 开窗口
│   └── preload.js         # 预加载（最小桥接）
├── portfolio-app/         # 现有 Flask 应用（不改）
```

---

### Task 1: 创建项目骨架

**Files:**
- Create: `electron/package.json`
- Create: `electron/preload.js`

- [ ] **Step 1: Create package.json**

```bash
cd C:/Users/16008/Desktop/personal/Write/portfolio/electron && npm init -y
```

- [ ] **Step 2: Install Electron**

```bash
cd C:/Users/16008/Desktop/personal/Write/portfolio/electron && npm install electron --save-dev
```

- [ ] **Step 3: Edit package.json to add start script and metadata**

Content:
```json
{
  "name": "portfolio-electron",
  "version": "1.0.0",
  "description": "Portfolio App — Electron Desktop Wrapper",
  "main": "main.js",
  "scripts": {
    "start": "electron ."
  },
  "devDependencies": {
    "electron": "^38.0.0"
  }
}
```

- [ ] **Step 4: Create preload.js**

```javascript
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform
});
```

---

### Task 2: 创建主进程 main.js

**Files:**
- Create: `electron/main.js`

- [ ] **Step 1: Write main.js with Flask lifecycle management**

```javascript
const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const FLASK_PORT = 5000;
const FLASK_URL = `http://localhost:${FLASK_PORT}`;
const SERVER_DIR = path.join(__dirname, '..', 'portfolio-app');

let mainWindow = null;
let flaskProcess = null;

function startFlask() {
  return new Promise((resolve, reject) => {
    const isWin = process.platform === 'win32';
    flaskProcess = spawn('python', ['server.py'], {
      cwd: SERVER_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: isWin,
    });

    flaskProcess.stderr.on('data', (data) => {
      const msg = data.toString();
      // Flask debug mode prints startup to stderr
      if (msg.includes('Running on')) {
        resolve();
      }
    });

    flaskProcess.on('error', (err) => {
      reject(new Error(`Failed to start Flask: ${err.message}`));
    });

    flaskProcess.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        reject(new Error(`Flask exited with code ${code}`));
      }
    });

    // Timeout: if Flask doesn't start in 30s, give up and try anyway
    setTimeout(() => resolve(), 30000);
  });
}

function waitForServer(url, retries = 30, interval = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      http.get(url, (res) => {
        if (res.statusCode < 500) resolve();
        else if (++attempts < retries) setTimeout(check, interval);
        else reject(new Error('Server not ready'));
      }).on('error', () => {
        if (++attempts < retries) setTimeout(check, interval);
        else resolve(); // Try anyway — maybe it just started
      });
    };
    check();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'Portfolio App',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(FLASK_URL);
  mainWindow.setMenuBarVisibility(false);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function cleanup() {
  if (flaskProcess && !flaskProcess.killed) {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', flaskProcess.pid.toString(), '/f', '/t']);
    } else {
      flaskProcess.kill('SIGTERM');
    }
  }
}

app.whenReady().then(async () => {
  try {
    await startFlask();
    await waitForServer(FLASK_URL);
  } catch (e) {
    console.error('Flask startup warning:', e.message);
  }
  createWindow();
});

app.on('window-all-closed', () => {
  cleanup();
  app.quit();
});

app.on('before-quit', () => {
  cleanup();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
```

---

### Task 3: 验证

- [ ] **Step 1: Start Electron**

```bash
cd C:/Users/16008/Desktop/personal/Write/portfolio/electron && npm start
```

Expected: Electron window opens, loads portfolio-app dashboard.

- [ ] **Step 2: Verify Flask cleanup on close**

Close the Electron window. Verify no Python process remains:
```bash
tasklist //FI "IMAGENAME eq python.exe" 2>/dev/null | grep python || echo "No python processes"
```

---

### Task 4: 添加 .gitignore

**Files:**
- Create: `electron/.gitignore`

```
node_modules/
dist/
.cache/
```

- [ ] **Step 1: Write .gitignore**

Create file with content above.

---

### Task 5: 提交

- [ ] **Step 1: Stage and commit**

```bash
cd C:/Users/16008/Desktop/personal/Write/portfolio
git add electron/
git commit -m "feat: Electron MVP — 桌面窗口封装 Flask 应用"
```
