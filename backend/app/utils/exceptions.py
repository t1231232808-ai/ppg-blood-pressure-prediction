#自定义异常类详解（PPG 脉搏波形预处理业务异常）
class PPGPreprocessError(ValueError):
    """Base exception for invalid or unusable PPG input."""


class PPGValidationError(PPGPreprocessError):
    """Raised when the uploaded PPG file format is invalid."""


class PPGQualityError(PPGPreprocessError):
    """Raised when the PPG signal quality is below the configured threshold."""


'''
使用示例：
# 1. 解析CSV发现格式错
if "signal" not in csv_df.columns:
    raise PPGValidationError("上传CSV文件缺少PPG信号字段")

# 2. 波形质检不合格
if signal_quality < settings.confidence_threshold:
    raise PPGQualityError("PPG波形信噪比过低，无法用于血压预测")
'''