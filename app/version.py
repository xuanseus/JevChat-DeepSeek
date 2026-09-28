# -*- coding: utf-8 -*-
"""版本号，显示在界面底部（`v{VERSION}`）。

**CI 打包前会整行覆盖它**（.github/workflows/release.yml）：有 tag 就用 tag 名去掉开头的 v
（`v0.1.0` → `0.1.0`），手动触发就用短 SHA。所以发布版显示的永远是 tag，这里是兜底值。

于是这个文件会**停在最后一次手改的号上**，不会跟着 tag 走——发了 v0.2.0 之后它还是写着
0.1.0。源码跑和本地 build.bat 打出来的包都用这个值；只有 CI 出的包才是准的。
要本地也准，把 build.bat 里加一句 `git describe --tags --always` 覆盖它就行，
代价是工作区会被改脏，得记得还原。
"""
VERSION = "0.1.0"
