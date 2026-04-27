import pytest
import datetime
from unittest.mock import AsyncMock, patch
import importlib.util
import sys
from pathlib import Path

# 处理带连字符的目录导入
def import_notifier():
    module_path = Path(__file__).parent.parent / 'notifier.py'
    spec = importlib.util.spec_from_file_location('notifier', str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules['notifier'] = module
    spec.loader.exec_module(module)
    return module

notifier = import_notifier()

@pytest.mark.asyncio
async def test_repayment_notify_real_api():
    """
    使用真实 API 进行测试。
    为了确保逻辑触发，我们需要模拟一个已知的、距离节假日 3 个工作日的日期。
    例如：2026-05-01 是劳动节，2026-04-27 是周一。
    从 27 号开始往后数：28(1), 29(2), 30(3) 是工作日，5-01 是节假日。符合条件。
    """
    today = datetime.date(2026, 4, 27)

    with patch('notifier.datetime.date') as mock_date, \
         patch('notifier.send_notification', new_callable=AsyncMock) as mock_send:

        mock_date.today.return_value = today
        # 确保 timedelta 运算返回的是真实 date 对象而非 Mock
        mock_date.side_effect = lambda *args, **kwargs: datetime.date(*args, **kwargs)

        await notifier.main()

        # 只要真实 API 返回 2026-05-01 是节假日且中间是工作日，这里就会被调用
        # 如果 API 暂无 2026 数据，测试可能会失败，这正是非模拟测试的特性
        assert mock_send.called
        args, _ = mock_send.call_args
        assert f'还有{notifier.ADVANCE_WORKDAYS}天放假' == args[0]
        assert '3个工作日' in args[1]

@pytest.mark.asyncio
async def test_repayment_no_notify_today():
    """
    测试一个已知不触发通知的日期（例如一个普通的工作日，且后面没有即将到来的节假日）
    """
    # 模拟一个远离任何节假日的日期，例如 2026-03-10 (周二)
    today = datetime.date(2026, 3, 10)

    with patch('notifier.datetime.date') as mock_date, \
         patch('notifier.send_notification', new_callable=AsyncMock) as mock_send:

        mock_date.today.return_value = today
        mock_date.side_effect = lambda *args, **kwargs: datetime.date(*args, **kwargs)

        await notifier.main()

        # 3月份通常没有节假日满足“提前3个工作日”条件
        mock_send.assert_not_called()
