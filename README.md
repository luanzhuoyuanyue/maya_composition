# Maya Composition Guides

一个用于 Maya 相机的构图辅助线工具，支持 **Maya 2018–2026**。

选择相机后，可以在视口或 Maya Hardware 2.0 渲染结果中显示构图参考线。辅助线会根据渲染分辨率生成，不受相机近、远裁切面影响。

## 主要功能

- 三分法、黄金螺旋、黄金三角、对角线
- 中心十字、中心圆、中心 25% 框、中心菱形
- 多种构图线可以同时叠加
- 支持视口、Maya Hardware 2.0，或两者同时输出
- 可调整颜色、透明度和线宽
- 每台相机可以保存独立设置
- 支持透视相机和正交相机

> 渲染辅助线仅支持 **Maya Hardware 2.0**，不会自动切换当前渲染器。

## 安装

1. 下载并解压安装包，保持包内文件位于同一目录。
2. 在 Maya 中打开 **Script Editor**，切换到 **Python**。
3. 修改下面的安装脚本路径，然后运行：

```python
installer_path = r"X:/path/install_composition_guides.py"
installer_scope = {"__file__": installer_path, "__name__": "__main__"}
eval(compile(open(installer_path, "rb").read(), installer_path, "exec"), installer_scope)
```

安装完成后，Maya 的 `Composition` Shelf 中会出现 `CG` 按钮。建议安装或更新后重启 Maya。

## 使用

1. 选择相机的 transform 或 camera shape。
2. 点击 Shelf 中的 `CG` 按钮。
3. 在窗口中点击“从选择获取”。
4. 选择构图类型和输出模式，调整颜色、透明度或线宽。
5. 点击“创建 / 更新”。

也可以从 Script Editor 启动：

```python
import composition_guides
composition_guides.show()
```

## 说明

- 视口辅助线使用 Viewport 2.0。
- 硬件渲染辅助线会生成透明 PNG，并通过专用 Image Plane 覆盖到画面。
- “显示 / 隐藏”可以切换辅助线，“删除”只删除当前相机的工具配置。
- Arnold、V-Ray、Redshift 等渲染器不支持最终渲染覆盖。

完整安装、缓存、卸载和测试说明请查看 [README_CN.md](README_CN.md)。
