import asyncio
import datetime
import aiohttp
from proj_common import logger, http_retry, send_notification

# 到期日
DUE_DAY = 8
# 提前提醒的工作日天数
ADVANCE_WORKDAYS = 3
# 是否将调休补班日当作工作日
INCLUDE_COMPENSATION = False

async def is_workday(session, date_str):
    """
    判断指定日期是否需要上班
    规律：
    1. holiday 为 null 时：看 type.type (0: 工作日, 1: 周末)
    2. holiday 不为 null 时：看 holiday.holiday (False: 调休补班, True: 放假)
    """
    url = f'http://timor.tech/api/holiday/info/{date_str}'
    headers = {'User-Agent': 'Mozilla/5.0'}

    async with await http_retry(session.get, (url,), kwargs={'headers': headers}) as response:
        res = await response.json()
        assert res['code'] == 0, f'API响应状态异常: {res}'

        holiday_info = res.get('holiday')
        if holiday_info is None:
            return res['type']['type'] == 0
        else:
            # holiday 为 True 表示放假，False 表示调休补班
            if not holiday_info['holiday']:
                return INCLUDE_COMPENSATION
            return False

async def main():
    today = datetime.date.today()

    # 计算下一个到期日 (当前的或下个月的8号)
    if today.day < DUE_DAY:
        target_due_date = today.replace(day=DUE_DAY)
    else:
        # 处理跨月/跨年
        if today.month == 12:
            target_due_date = today.replace(year=today.year + 1, month=1, day=DUE_DAY)
        else:
            target_due_date = today.replace(month=today.month + 1, day=DUE_DAY)

    async with aiohttp.ClientSession() as session:
        # 如果今天不是工作日，直接退出
        if not await is_workday(session, today.strftime('%Y-%m-%d')):
            logger.info(f'今天({today})是休息日，跳过检测')
            return

        # 统计从明天起到目标到期日之间的工作日数量
        workdays_counted = 0
        target_date = today + datetime.timedelta(days=1)

        while target_date <= target_due_date:
            if await is_workday(session, target_date.strftime('%Y-%m-%d')):
                workdays_counted += 1
            target_date += datetime.timedelta(days=1)

        if workdays_counted == ADVANCE_WORKDAYS:
            msg = f'距离每月到期日({DUE_DAY}号)还有{ADVANCE_WORKDAYS}个工作日'
            logger.info(f'触发通知条件: {msg}')
            await send_notification(f'到期提醒({DUE_DAY}号)', msg)
        else:
            logger.info(f'距离到期日还有 {workdays_counted} 个工作日，未到提醒时间')

if __name__ == '__main__':
    asyncio.run(main())
