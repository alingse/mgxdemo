# 代码检查工具安装指南

本文档说明如何安装代码检查工具，用于 `app/tools/check_tool.py` 中的代码质量检查功能。

这些工具是**可选的** - 如果未安装，系统会优雅地跳过检查而不会报错。

## 工具列表

| 工具 | 用途 | 官网 |
|------|------|------|
| tidy | HTML 语法检查 | https://www.html-tidy.org/ |
| stylelint | CSS 语法检查 | https://stylelint.io/ |
| eslint | JavaScript 语法检查 | https://eslint.org/ |

---

## macOS 安装

```bash
# HTML 检查 (tidy)
brew install tidy-html5

# CSS 检查 (stylelint) - 需要先安装 Node.js
npm install -g stylelint

# JavaScript 检查 (eslint) - 需要先安装 Node.js
npm install -g eslint
```

**前提条件**：如果未安装 Homebrew，请先执行：
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## Linux 安装

### Ubuntu / Debian

```bash
# HTML 检查 (tidy)
sudo apt-get update
sudo apt-get install tidy

# CSS/JS 检查 - 需要先安装 Node.js 和 npm
sudo apt-get install nodejs npm
npm install -g stylelint eslint
```

### CentOS / RHEL

```bash
# HTML 检查 (tidy)
sudo yum install epel-release
sudo yum install libtidy

# 安装 Node.js
curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
sudo yum install nodejs

# 安装 CSS/JS 检查工具
npm install -g stylelint eslint
```

---

## 验证安装

```bash
which tidy       # 应输出 tidy 可执行文件路径
which stylelint  # 应输出 stylelint 可执行文件路径
which eslint     # 应输出 eslint 可执行文件路径
```

---

## 使用示例

安装完成后，可在 AI 对话中使用检查工具：

```json
// 检查所有文件
{"type": "all"}

// 检查单个文件
{"type": "html", "filename": "index.html"}
{"type": "css", "filename": "style.css"}
{"type": "js", "filename": "script.js"}
```
