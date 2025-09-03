import abc
import gzip
import io
import time
from collections.abc import Callable
from typing import Any, Optional

from twisted.web.http import Request

from .data import CacheableResult


class Renderer(metaclass=abc.ABCMeta):

    def __init__(self, id: str, version: int, request: Request):
        self.id = id
        self.version = version
        self.request = request

    @abc.abstractmethod
    def render(self, string_renderer: Callable[[Any, str, int], str]) -> None:
        pass

    def handle_compression(self, response_string: str, cached_response: Optional[bytes],
                           cache_updater: Optional[Callable[[bytes], None]]) -> None:
        compression = self.request.getHeader('Accept-encoding')
        original_size = len(response_string)
        if compression == "gzip" and original_size >= 1000:
            if cached_response is not None:
                response_binary = cached_response
            else:
                start_time = time.time()
                out_file = io.BytesIO()
                with gzip.GzipFile(mode='wb', fileobj=out_file) as in_file:
                    in_file.write(response_string.encode())
                response_binary = out_file.getvalue()

                compressed_size = len(response_binary)
                elapsed_time = time.time() - start_time
                break_even = (original_size - compressed_size) / elapsed_time / 1024 / 1024
                print("renderer: compress data {} -> {} ({:.1f} %) in {:.2f} ms (break even at {:.1f} MB/s)".format(original_size,
                                                                                                          compressed_size,
                                                                                                          compressed_size * 100 / original_size,
                                                                                                          elapsed_time * 1000,
                                                                                                          break_even))
                if cache_updater is not None:
                    cache_updater(response_binary)

            self.request.setHeader("content-encoding", "gzip")
        else:
            response_binary = response_string.encode()

        self.request.setHeader(b"content-length", str(len(response_binary)))
        self.request.write(response_binary)


class DefaultRenderer(Renderer):

    def __init__(self, result: Any, id: str, version: int, request: Request):
        super().__init__(id, version, request)
        self.result = result

    def render(self, string_renderer: Callable[[Any, str, int], str]) -> None:
        result_string = string_renderer(self.result, self.id, self.version)

        self.handle_compression(result_string, None, None)


class CacheableResultRenderer(Renderer):

    def __init__(self, result: CacheableResult, id: str, version: int, request: Request):
        super().__init__(id, version, request)
        self.result = result

    def render(self, call: Callable[[Any, str, int], str]) -> None:
        if self.result.string_value is not None:
            string_value = self.result.string_value
        else:
            string_value = call(self.result.value, self.id, self.version)
            self.result.string_value = string_value

        def update_value(compressed_value: bytes) -> None:
            self.result.compressed_value = compressed_value

        self.handle_compression(
            string_value,
            self.result.compressed_value,
            update_value
        )


def renderer_factory(result, id, version, request: Request):
    if isinstance(result, CacheableResult):
        return CacheableResultRenderer(result, id, version, request)
    else:
        return DefaultRenderer(result, id, version, request)
