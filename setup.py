import platform

from setuptools import Extension, setup


def get_ext_modules() -> list:
    """
    获取三方模块
    Linux需要编译封装接口
    Windows直接使用预编译的pyd即可
    Mac由于缺乏二进制库支持无法使用
    """
    if platform.system() != "Linux":
        return []

    compiler_flags = [
        "-std=c++17",
        "-O3",
        "-Wno-delete-incomplete", "-Wno-sign-compare",
    ]
    extra_link_args = ["-lstdc++"]
    runtime_library_dirs = ["$ORIGIN"]

    vnsgitmd = Extension(
        "vnpy_sgit.api.vnsgitmd",
        [
            "vnpy_sgit/api/vnsgit/vnsgitmd/vnsgitmd.cpp",
        ],
        include_dirs=["vnpy_sgit/api/include",
                      "vnpy_sgit/api/vnsgit"],
        define_macros=[],
        undef_macros=[],
        library_dirs=["vnpy_sgit/api/libs", "vnpy_sgit/api"],
        libraries=["sgitquotapi", "sgittradeapi"],
        extra_compile_args=compiler_flags,
        extra_link_args=extra_link_args,
        runtime_library_dirs=runtime_library_dirs,
        depends=[],
        language="cpp",
    )

    vnsgittd = Extension(
        "vnpy_sgit.api.vnsgittd",
        [
            "vnpy_sgit/api/vnsgit/vnsgittd/vnsgittd.cpp",
        ],
        include_dirs=["vnpy_sgit/api/include",
                      "vnpy_sgit/api/vnsgit"],
        define_macros=[],
        undef_macros=[],
        library_dirs=["vnpy_sgit/api/libs", "vnpy_sgit/api"],
        libraries=["sgitquotapi", "sgittradeapi"],
        extra_compile_args=compiler_flags,
        extra_link_args=extra_link_args,
        runtime_library_dirs=runtime_library_dirs,
        depends=[],
        language="cpp",
    )

    return [vnsgittd, vnsgitmd]


setup(
    ext_modules=get_ext_modules(),
)
