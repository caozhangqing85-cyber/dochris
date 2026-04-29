"""
异常模块单元测试
"""


from dochris.exceptions import (
    APIError,
    CacheError,
    CompilationError,
    FileProcessingError,
    IngestionError,
    KnowledgeBaseError,
    QueryError,
    ValidationError,
)


class TestKnowledgeBaseError:
    """测试基础异常类"""

    def test_is_exception(self):
        """测试是 Exception 子类"""
        assert issubclass(KnowledgeBaseError, Exception)

    def test_can_instantiate(self):
        """测试可以实例化"""
        exc = KnowledgeBaseError("test message")
        assert str(exc) == "test message"
        assert isinstance(exc, Exception)

    def test_default_args(self):
        """测试默认参数"""
        exc = KnowledgeBaseError()
        assert isinstance(exc, Exception)


class TestIngestionError:
    """测试摄入异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(IngestionError, KnowledgeBaseError)

    def test_message(self):
        """测试异常消息"""
        exc = IngestionError("文件摄入失败")
        assert "文件摄入失败" in str(exc)


class TestCompilationError:
    """测试编译异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(CompilationError, KnowledgeBaseError)

    def test_message(self):
        """测试异常消息"""
        exc = CompilationError("文档编译失败")
        assert "文档编译失败" in str(exc)


class TestQueryError:
    """测试查询异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(QueryError, KnowledgeBaseError)

    def test_message(self):
        """测试异常消息"""
        exc = QueryError("查询执行失败")
        assert "查询执行失败" in str(exc)


class TestAPIError:
    """测试 API 异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(APIError, KnowledgeBaseError)

    def test_message_with_status_code(self):
        """测试带状态码的异常消息"""
        exc = APIError("API 请求失败", status_code=400)
        assert "API 请求失败" in str(exc)
        assert exc.status_code == 400

    def test_message_without_status_code(self):
        """测试不带状态码的异常消息"""
        exc = APIError("API 请求失败")
        assert "API 请求失败" in str(exc)
        assert exc.status_code is None


class TestFileProcessingError:
    """测试文件处理异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(FileProcessingError, KnowledgeBaseError)

    def test_message_with_file_path(self):
        """测试带文件路径的异常消息"""
        exc = FileProcessingError("文件处理失败", file_path="/path/to/file.pdf")
        assert "文件处理失败" in str(exc)
        assert exc.file_path == "/path/to/file.pdf"

    def test_message_without_file_path(self):
        """测试不带文件路径的异常消息"""
        exc = FileProcessingError("文件处理失败")
        assert "文件处理失败" in str(exc)
        assert exc.file_path is None


class TestCacheError:
    """测试缓存异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(CacheError, KnowledgeBaseError)

    def test_message(self):
        """测试异常消息"""
        exc = CacheError("缓存操作失败")
        assert "缓存操作失败" in str(exc)


class TestValidationError:
    """测试验证异常"""

    def test_is_kb_error(self):
        """测试是 KnowledgeBaseError 子类"""
        assert issubclass(ValidationError, KnowledgeBaseError)

    def test_message_with_field(self):
        """测试带字段的异常消息"""
        exc = ValidationError("验证失败", field="title")
        assert "验证失败" in str(exc)
        assert exc.field == "title"

    def test_message_without_field(self):
        """测试不带字段的异常消息"""
        exc = ValidationError("验证失败")
        assert "验证失败" in str(exc)
        assert exc.field is None


class TestExceptionHierarchy:
    """测试异常层次结构"""

    def test_all_inherit_from_base(self):
        """测试所有异常都继承自基类"""
        exceptions = [
            IngestionError,
            CompilationError,
            QueryError,
            APIError,
            FileProcessingError,
            CacheError,
            ValidationError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, KnowledgeBaseError)

    def test_catch_base_catches_all(self):
        """测试捕获基类可以捕获所有子类"""
        exceptions_to_test = [
            IngestionError(),
            CompilationError(),
            QueryError(),
            APIError(),
            FileProcessingError(),
            CacheError(),
            ValidationError(),
        ]
        caught_count = 0
        for exc in exceptions_to_test:
            try:
                raise exc
            except KnowledgeBaseError:
                caught_count += 1
        assert caught_count == len(exceptions_to_test)
