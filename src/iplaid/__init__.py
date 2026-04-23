__all__ = ["extract_compound_info", "logtodf"]


def __getattr__(name: str):
    if name in __all__:
        from .log_parser import extract_compound_info, logtodf

        exports = {
            "extract_compound_info": extract_compound_info,
            "logtodf": logtodf,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
