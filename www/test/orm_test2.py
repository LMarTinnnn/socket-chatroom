from orm import create_db_pool, destroy_pool
import asyncio
from model import User
import logging
logging.basicConfig(level=logging.INFO)

async def test1(loop):
    await create_db_pool(loop=loop, user='blog-data', password=' ', db='blog')

    # 测试count rows语句
    rows = await User.count_rows()
    logging.info('rows is %s' % rows)

    # 测试insert into语句
    if rows < 3:
        for idx in range(5):
            u = User(
                name='test%s' % idx,
                email='test%s@org.com' % idx,
                password='orm123%s' % idx,
                avatar='about:blank'
            )
            row = await User.count_rows(where='email = ?', args=[u.email])
            if row == 0:
                await u.save()
            else:
                print('the email is already registered...')

    # 测试select语句
    users = await User.find_all(orderBy='created_at')
    for user in users:
        logging.info('name: %s, password: %s, created_at: %s' % (user.name, user.password, user.created_at))

    # 测试update语句
    user = users[1]
    user.email = 'guest@orm.com'
    user.name = 'guest'
    await user.update_data()

    # 测试查找指定用户
    test_user = await User.find_by_primary_key(user.id)
    logging.info('name: %s, email: %s' % (test_user.name, test_user.email))

    # 测试delete语句
    users = await User.find_all(orderBy='created_at', limit=(0, 3))
    for user in users:
        logging.info('delete user: %s' % user.name)
        await user.delete()

    await destroy_pool()  # 这里先销毁连接池
    print('test ok')

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test1(loop))
    loop.close()
