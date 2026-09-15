# Maya 构图辅助线

目标版本：Maya 2018–2026，Python 2.7 / 3.x，无第三方安装依赖（使用 Maya 自带 Qt）。支持普通透视和正交相机；不专门支持 Stereo Camera Rig。视口使用 Viewport 2.0，最终渲染覆盖仅支持 Maya Hardware 2.0。

## 安装与启动

解压后保持六个文件在同一目录。在 Maya 的 Script Editor 切到 **Python**，修改下面的路径并运行。显式传入 `__file__`，让安装器找到相邻文件：

```python
installer_path = r"X:/path/install_composition_guides.py"
installer_scope = {"__file__": installer_path, "__name__": "__main__"}
eval(compile(open(installer_path, "rb").read(), installer_path, "exec"), installer_scope)
```

此写法使用 Python 2／3 共用的 `eval` 执行已编译的脚本，并通过 `__main__` 调用安装。在 Maya 用户 scripts 目录复制主脚本与几何模块，在用户应用目录下的 plug-ins 复制插件，加载目标插件并设置自动加载。在 `Composition` Shelf 标签创建或更新 `CG` 按钮（有可用相机图标时显示图标）。可重复安装，已从目标安装位置加载的插件和按钮会复用；若已加载解压目录或其他位置的构图插件，安装器会在修改文件前拒绝，请重启干净 Maya 会话后重装。更新代码后请重启 Maya 使用新代码。请保留解压目录供卸载和测试使用。

点击 Shelf 按钮，或在 Script Editor 运行：

```python
import composition_guides
composition_guides.show()
```

## 使用

选择一台相机的 transform 或 camera shape，点击“从选择获取”，确认窗口显示完整相机路径。每台相机保存独立配置；“创建 / 更新”重复执行会更新该相机现有配置。

| 输出模式 | 普通视口 | Maya Hardware 2.0 渲染 |
| --- | --- | --- |
| 仅视口（Viewport） | 二维辅助线 | 无 Image Plane 覆盖 |
| 仅硬件渲染（Hardware） | 隐藏 | 透明 PNG 覆盖 |
| 两者（Both） | 二维辅助线 | 透明 PNG 覆盖，临时停用二维绘制 |

默认“两者”、三分法、黄色、透明度 0.8、线宽 2 px。工具从不自动切换用户渲染器。Arnold、V-Ray、Redshift 等不支持此渲染覆盖；需要硬件输出时自行选择 Maya Hardware 2.0。

构图可以组合叠加：

- 三分法：宽、高的 1/3 和 2/3 位置各两条线。
- 黄金螺旋：黄金矩形递归划分，以连续四分之一圆弧折线近似；左上、右上、左下、右下四种方向。
- 黄金三角：一条主对角线，加另外两角向它作的垂线。垂直关系按输出像素计算，交点随宽高比变化；可选两种主对角线方向。
- 对角线：左上至右下、右上至左下可分别开关，默认两条均选中。
- 中心构图：中心十字；中心圆（默认选中，直径为画面短边 10%）；中心 25% 框（宽、高各为画幅的 25%，面积为 6.25%）；中心菱形（连接画面上、右、下、左四边中点）。
- “全部”：全选或清空五个构图大类，保留各方向及中心子项设置。

样式统一控制 RGB 颜色、透明度和 1–10 px 像素线宽。更改设置实时刷新视口；硬件 PNG 在创建/更新或渲染刷新时生成。宽高和 Pixel Aspect 来自 Render Settings，辅助线对齐相机 Resolution Gate，并随 Film Fit、Overscan、Film Offset、Pan/Zoom 重算。视口使用屏幕空间二维绘制，不受 near/far clipping plane 裁切；硬件 Image Plane 的深度通过节点连接跟随 near clip 的 1.01 倍。

“显示 / 隐藏”切换总开关。“删除”确认后只删除当前相机的有效工具配置、专用 Image Plane、深度节点及其验证过的缓存 PNG，保留其他相机及用户 Image Plane。“清理缓存”确认后只删除当前场景有效配置引用且位于专用缓存目录的图片，不删除场景节点；下次刷新会重新生成。

## 缓存与卸载

PNG 优先存入 `<当前项目>/sourceimages/composition_guides`，项目目录不可写时使用 `<cmds.internalVar(userTmpDir=True)>/composition_guides`。文件名带场景、相机与配置标识。改变项目后再次刷新会使用新位置；旧项目缓存可以在确认不再需要后手动清理。

卸载前先删除所有构图辅助线，或打开干净场景。存在活的 `compositionGuidesLocator` 节点时卸载会停止，不强制卸载插件。运行以下代码（修改路径）：

```python
import sys
package_dir = r"X:/path"
if package_dir not in sys.path:
    sys.path.append(package_dir)
import install_composition_guides
print(install_composition_guides.uninstall())
# 若也要删除当前项目与 Maya 临时目录下的两个专用缓存目录，改用：
# print(install_composition_guides.uninstall(remove_cache=True))
```

卸载只移除三个已安装的运行文件、工具标记渲染钩子与回调、所属插件及 annotation 精确匹配 `Maya Composition Guides` 的按钮。保留 Shelf 标签及其他控件。默认保留缓存；可选清理只作用于上面两个专用目录，遇到路径链接会停止。可以重复卸载。卸载后重启 Maya 清除内存中已导入的模块；已删除文件可从原始解压包重新安装恢复。

## 冒烟测试与实际画面验证

先保存工作并重新启动干净、可丢弃的 Maya 会话，避免内存中保留其他目录的旧模块。此测试显式授权后会**强制新建场景**，测试场景会留在窗口中；默认调用会拒绝执行。修改解压目录路径后运行：

```python
import sys
package_dir = r"X:/path"
sys.path.insert(0, package_dir)
import maya_smoke_test
print(maya_smoke_test.run_smoke_test(allow_new_scene=True))
```

所测副本按插件来源确定：若目标安装插件已经自动加载，则测试用户 scripts 加目标 plug-ins 的安装副本；若已加载本脚本同目录的插件，则测试同目录解压包；若尚未加载插件，则优先选择同目录完整包，缺失时才尝试完整安装副本。脚本在新建场景前核对控制器、几何模块和插件的实际文件路径；不一致或存在来源不明的节点类型时拒绝，提示重启干净会话。它会把选中目录置于导入搜索路径首位，并在加载后再次核对路径。

结果字典的 `tested_paths` 明确列出所测三个文件，其他命名项目显示透视/正交相机、重复创建、独立配置与消息所有权、0.1→10.0 near clip 对应 10.1 深度、640×360 RGBA PNG、三个输出模式渲染前后状态、只删除目标相机等检查。脚本临时使用 Hardware 2.0 检查状态并在结束或失败时恢复此前的全局渲染器。它测试实际绘制数据准备，但不证明 GPU 已画出正确像素。

最终视觉/GPU 验证取决于本地可用 Maya 版本，不能把源码、模拟测试或 mayapy 编译通过当成 Maya 2018–2026 全版本验证。请在可用版本中安装两次确认单一按钮，重启确认自动加载及启动，检查横/竖/方画幅、Pixel Aspect、Film Fit、Overscan、Film Offset、Pan/Zoom 和裁切面，实际执行 Hardware 2.0 Render View 与 `ogsRender` 检查线条位置、透明度和覆盖；也检查非 Hardware 渲染器未被切换。未实测版本需明确记录为未验证。
