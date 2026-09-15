# -*- coding: utf-8 -*-
"""Install from the extracted package; import to use uninstall()."""
from __future__ import absolute_import, print_function

import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel

ANNOTATION = "Maya Composition Guides"
SHELF_COMMAND = "import composition_guides; composition_guides.show()"
PLUGIN = "composition_guides_plugin.py"


def _paths():
    scripts = os.path.abspath(cmds.internalVar(userScriptDir=True))
    plugins = os.path.join(os.path.abspath(cmds.internalVar(userAppDir=True)), "plug-ins")
    return {"composition_guides.py": os.path.join(scripts, "composition_guides.py"),
            "composition_guides_core.py": os.path.join(scripts, "composition_guides_core.py"),
            PLUGIN: os.path.join(plugins, PLUGIN)}


def _normalized(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _redirected(path):
    path = os.path.abspath(path)
    if os.path.islink(path) or _normalized(path) != os.path.normcase(path):
        return True
    if os.name == "nt":
        # Python 2's realpath does not resolve Windows directory junctions.
        import ctypes
        try:
            text_type = unicode
        except NameError:
            text_type = str
        while True:
            attributes = ctypes.windll.kernel32.GetFileAttributesW(text_type(path))
            if attributes != -1 and attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                return True
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
    return False


def _loaded_plugin(paths):
    allowed = (_normalized(paths[PLUGIN]),
               _normalized(os.path.join(os.path.dirname(os.path.abspath(__file__)), PLUGIN)))
    for name in cmds.pluginInfo(query=True, listPlugins=True) or []:
        path = cmds.pluginInfo(name, query=True, path=True)
        if _normalized(path) in allowed:
            return name
        if os.path.basename(path) == PLUGIN:
            raise RuntimeError(u"另一个位置的构图插件已加载，请重新启动 Maya 后再安装或卸载。")
    return None


def _shelf(create=False):
    top = mel.eval('$cgShelfTop = $gShelfTopLevel')
    if not top:
        if create:
            raise RuntimeError(u"未找到 Shelf，请在 Maya 图形界面中运行安装器。")
        return None
    tab = top + "|Composition"
    if cmds.shelfLayout(tab, exists=True):
        return tab
    return cmds.shelfLayout("Composition", parent=top) if create else None


def _owned_buttons(tab):
    result = []
    for child in cmds.shelfLayout(tab, query=True, childArray=True) or []:
        try:
            if (cmds.shelfButton(child, exists=True) and
                    cmds.shelfButton(child, query=True, annotation=True) == ANNOTATION):
                result.append(child)
        except RuntimeError:
            continue
    return result


def install():
    source = os.path.dirname(os.path.abspath(__file__))
    paths = _paths()
    for filename in paths:
        if not os.path.isfile(os.path.join(source, filename)):
            raise RuntimeError(u"安装包不完整，缺少：%s" % filename)
    loaded = _loaded_plugin(paths)
    for filename, destination in sorted(paths.items()):
        directory = os.path.dirname(destination)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        source_path = os.path.join(source, filename)
        if _normalized(source_path) != _normalized(destination):
            shutil.copy2(source_path, destination)
    scripts = os.path.dirname(paths["composition_guides.py"])
    if scripts not in sys.path:
        sys.path.append(scripts)
    if loaded is None:
        loaded_names = cmds.loadPlugin(paths[PLUGIN], quiet=True)
        loaded = loaded_names[0] if loaded_names else paths[PLUGIN]
    cmds.pluginInfo(loaded, edit=True, autoload=True)
    tab = _shelf(create=True)
    buttons = _owned_buttons(tab)
    settings = dict(annotation=ANNOTATION, label="CG", sourceType="python",
                    command=SHELF_COMMAND)
    try:
        icons = cmds.resourceManager(nameFilter="camera.svg") or cmds.resourceManager(nameFilter="camera.png") or []
    except RuntimeError:
        icons = []
    if icons:
        settings["image1"] = icons[0]
        settings["style"] = "iconOnly"
    else:
        settings["style"] = "textOnly"
    if buttons:
        button = buttons[0]
        cmds.shelfButton(button, edit=True, **settings)
    else:
        button = cmds.shelfButton(parent=tab, **settings)
    return {"paths": paths, "shelf_button": button}


def _cache_roots():
    parents = [os.path.abspath(cmds.internalVar(userTmpDir=True))]
    workspace = cmds.workspace(query=True, rootDirectory=True)
    if workspace:
        parents.append(os.path.join(os.path.abspath(workspace), "sourceimages"))
    roots = []
    for parent in parents:
        root = os.path.abspath(os.path.join(parent, "composition_guides"))
        # Refuse redirected roots/parents: cleanup may only reach this dedicated directory.
        if (_redirected(root) or
                os.path.basename(root) != "composition_guides" or
                os.path.dirname(root) != parent):
            raise RuntimeError(u"缓存路径包含重定向，已停止清理：%s" % root)
        if os.path.isdir(root):
            for directory, subdirs, files in os.walk(root, followlinks=False):
                for name in subdirs + files:
                    child = os.path.join(directory, name)
                    if _redirected(child):
                        raise RuntimeError(u"缓存中包含链接，已停止清理：%s" % child)
        roots.append(root)
    return sorted(set(roots))


def uninstall(remove_cache=False):
    if ("compositionGuidesLocator" in (cmds.allNodeTypes() or []) and
            cmds.ls(type="compositionGuidesLocator", long=True)):
        raise RuntimeError(u"请先删除构图辅助线，或打开干净场景，再卸载工具。")
    paths = _paths()
    loaded = _loaded_plugin(paths)
    cache_roots = _cache_roots() if remove_cache else []
    try:
        import composition_guides
    except ImportError:
        composition_guides = None
    if composition_guides is not None:
        for name in ("remove_render_hooks", "_remove_callbacks"):
            cleanup = getattr(composition_guides, name, None)
            if callable(cleanup):
                cleanup()
    if loaded is not None:
        cmds.pluginInfo(loaded, edit=True, autoload=False)
        cmds.unloadPlugin(loaded)
    removed = []
    for path in sorted(paths.values()):
        if os.path.isfile(path):
            os.remove(path)
            removed.append(path)
    tab = _shelf()
    buttons = _owned_buttons(tab) if tab else []
    for button in buttons:
        cmds.deleteUI(button)
    caches = []
    for root in cache_roots:
        if os.path.isdir(root):
            shutil.rmtree(root)
            caches.append(root)
    return {"removed_files": removed, "removed_buttons": buttons, "removed_caches": caches}


if __name__ == "__main__":
    print(install())
