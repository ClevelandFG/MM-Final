# Python 环境创建说明

本文档记录本项目的本机 Python 虚拟环境创建方式。

## 1. 基本原则

- 使用 uv 管理虚拟环境同步和依赖锁定。
- 提交 `pyproject.toml`、`uv.lock` 和本文档。
- 不提交 `.venv`，因为 `.venv` 含有本机路径、解释器细节和平台相关文件。
- `.venv` 已在 `.gitignore` 中忽略。

## 2. 首次创建环境

项目已经存在 `pyproject.toml` 和 `uv.lock`，首次创建或同步环境执行：

```powershell
uv sync
```

如果需要安装测试开发依赖，执行：

```powershell
uv sync --extra dev
```

## 3. 后续同步环境

当依赖声明发生变化后，先在共享分支更新 `pyproject.toml` 和 `uv.lock`，其他开发者拉取最新主干后执行：

```powershell
uv sync
```

## 4. 复现边界

`uv.lock` 能让开发者获得一致的依赖解析结果和包版本。它不保证复制完全相同的 `.venv` 目录字节内容；虚拟环境目录本身仍由各自机器本地生成。

Python 版本仍等待 A 线工程师确认。当前 `pyproject.toml` 暂以 `requires-python >=3.9` 保持兼容；建议后续两位工程师统一到 Python 3.12.x 后再收紧版本下界。
