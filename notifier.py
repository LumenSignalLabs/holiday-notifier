import asyncio
import datetime
import aiohttp
from proj_common import logger, http_retry, send_notification

# 提前提醒的工作日天数
ADVANCE_WORKDAYS = 3

async def get_holiday_info(session, date_str):
    url = f'http://timor.tech/api/holiday/info/{date_str}'
    headers = {'User-Agent': 'Mozilla/5.0'}

    async with await http_retry(session.get, (url,), kwargs={'headers': headers}) as response:
        res = await response.json()

        # 数据结构异常将直接触发 AssertionError 报错拦截
        assert res['code'] == 0, f'API响应状态异常: {res}'
        return res['type']

async def main():
    today = datetime.date.today()
    workdays_counted = 0

    # 从明天开始向后推算
    target_date = today + datetime.timedelta(days=1)

    async with aiohttp.ClientSession() as session:
        while workdays_counted <= ADVANCE_WORKDAYS:
            date_str = target_date.strftime('%Y-%m-%d')
            day_info = await get_holiday_info(session, date_str)

            day_type = day_info['type']  # 0:工作日, 1:休息日, 2:节假日

            if day_type == 2:
                if workdays_counted == ADVANCE_WORKDAYS:
                    holiday_name = day_info['name']
                    msg = f'距离下一个法定节假日({holiday_name})还有{ADVANCE_WORKDAYS}个工作日'
                    logger.info(f'触发通知条件: {msg}')
                    await send_notification(f'还有{ADVANCE_WORKDAYS}天放假', msg)
                else:
                    logger.info('距离下一个节假日不满足提前N个工作日条件')

                # 遇到第一个节假日即停止检测
                break

            if day_type == 0:
                workdays_counted += 1

            target_date += datetime.timedelta(days=1)

if __name__ == '__main__':
    asyncio.run(main())
