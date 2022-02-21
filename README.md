# VeighNa框架的飞鼠交易接口
<p align="center">
  <img src ="https://vnpy.oss-cn-shanghai.aliyuncs.com/vnpy-logo.png"/>
</p>

<p align="center">
    <img src ="https://img.shields.io/badge/version-4.8.3-blueviolet.svg"/>
    <img src ="https://img.shields.io/badge/platform-linux-yellow.svg"/>
    <img src ="https://img.shields.io/badge/python-3.7|3.8|3.9|3.10-blue.svg" />
    <img src ="https://img.shields.io/github/license/vnpy/vnpy.svg?color=orange"/>
</p>

## 说明

基于飞鼠柜台的4.8版本API封装开发的交易接口，只支持Linux系统。

## 安装

安装环境推荐基于3.0.0版本以上的【[**VeighNa Studio**](https://www.vnpy.com)】。

直接使用pip命令：

```
pip install vnpy_sgit
```


或者下载源代码后，解压后在cmd中运行：

```
pip install .
```


## 使用

以脚本方式启动（script/run.py）：

```
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

from vnpy_sgit import SgitGateway


def main():
    """主入口函数"""
    qapp = create_qapp()

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(SgitGateway)
    
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()


if __name__ == "__main__":
    main()
```

## 注意

连接前请先将运行的python下lib/site-packages文件夹下vnpy_sgit/api中的rsa.pk文件放到运行目录。并修改libcrypto.so为libcrypto.so.10，libssl.so为libssl.so.10。
