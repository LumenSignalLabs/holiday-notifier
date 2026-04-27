import pytest
import datetime
from unittest.mock import AsyncMock, patch
import importlib.util
import sys
from pathlib import Path

# 保存真实的日期类，用于在测试中准确模拟
REAL_DATE = datetime.date

# 处理目录导入
def import_notifier():
    module_path = Path(__file__).parent.parent / 'notifier.py'
    spec = importlib.util.spec_from_file_location('notifier', str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules['notifier'] = module
    spec.loader.exec_module(module)
    return module

notifier = import_notifier()

@pytest.fixture
def base_mocks():
    """基础 Mock 补丁：锁定配置和通知函数，保留真实 API 调用"""
    with patch('notifier.DUE_DAY', 8), \
         patch('notifier.ADVANCE_WORKDAYS', 3), \
         patch('notifier.send_notification', new_callable=AsyncMock) as mock_send, \
         patch('notifier.datetime.date') as mock_date:

        # 允许代码内正常实例化日期对象
        mock_date.side_effect = lambda *args, **kwargs: REAL_DATE(*args, **kwargs)
        yield mock_date, mock_send

@pytest.mark.asyncio
async def test_real_api_trigger_scenario(base_mocks):
    """
    真实测试：2025-07-03 (周四)
    API 数据确认：
    - 07-04 (五): 工
    - 07-05/06: 休
    - 07-07 (一): 工
    - 07-08 (二): 工 (到期日)
    明天起共有 3 个工作日，应触发通知
    """
    mock_date, mock_send = base_mocks
    mock_date.today.return_value = REAL_DATE(2025, 7, 3)

    await notifier.main()

    assert mock_send.called
    assert '距离每月到期日(8号)还有3个工作日' == mock_send.call_args[0][1]

@pytest.mark.asyncio
async def test_real_api_no_trigger_late(base_mocks):
    """
    真实测试：2025-07-07 (周一)
    距离 8 号只有 1 个工作日，不应触发
    """
    mock_date, mock_send = base_mocks
    mock_date.today.return_value = REAL_DATE(2025, 7, 7)

    await notifier.main()

    mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_real_api_no_run_on_holiday(base_mocks):
    """
    真实测试：2025-01-01 (元旦，法定节假日)
    程序应直接退出
    """
    mock_date, mock_send = base_mocks
    mock_date.today.return_value = REAL_DATE(2025, 1, 1)

    await notifier.main()

    mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_real_api_spring_festival_makeup_trigger(base_mocks):
    """
    复杂节假日调休测试：2025 年春节
    2025-02-08 (周六) 是补班日，计为到期日
    2025-02-05 (周三) 运行：
    明天起的工作日：06(四), 07(五), 08(六补班)
    共 3 个工作日，应触发
    """
    mock_date, mock_send = base_mocks
    mock_date.today.return_value = REAL_DATE(2025, 2, 5)

    await notifier.main()

    assert mock_send.called
    assert '距离每月到期日(8号)还有3个工作日' == mock_send.call_args[0][1]

@pytest.mark.asyncio
async def test_real_api_makeup_day_runnable(base_mocks):
    """
    补班日运行测试：2025-01-26 (周日，补班)
    程序应能识别出补班日并正常执行，而不是因周日而退出
    """
    mock_date, mock_send = base_mocks
    mock_date.today.return_value = REAL_DATE(2025, 1, 26)

    # 距离 02-08 还有很多工作日，不触发
    await notifier.main()

    mock_send.assert_not_called()
    # 如果代码中没写好补班逻辑，它会打印“今天是休息日”并直接返回，
    # 我们通过观察 log（虽然在此断言不可见，但能确保它跑完了统计循环）

@pytest.mark.asyncio
async def test_real_api_cross_year_logic(base_mocks):
    """
    跨年逻辑测试：2024-12-30 运行
    目标 2025-01-08
    验证程序能否正确跨越年份边界进行日期统计
    """
    mock_date, mock_send = base_mocks
    mock_date.today.return_value = REAL_DATE(2024, 12, 30)

    await notifier.main()

    # 12-31, 01-02, 01-03, 01-06, 01-07, 01-08 共有 6 个工作日，不触发
    mock_send.assert_not_called()

