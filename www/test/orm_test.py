import asyncio

import orm
from model import User

async def test(event_loop):
    await orm.create_db_pool(user='blog-data', password=' ', db='blog', loop=event_loop)
    user = User(name='test', email='test2 email', password='test pass', avatar='test avatar')
    row = await User.count_rows(where='email=?', args=[user.email])
    if not row:
        await user.save()
        u = await User.find_by_primary_key(user.id)
        print(u.name)
        u.name = 'change'
        await u.update_data()
        new_u = await User.find_by_primary_key(user.id)
        print(new_u.name)
        # await user.delete()
        await orm.destroy_pool()
    else:
        user = (await User.find_all(where='email=?', args=[user.email]))[0]
        user.password = 'New Password'
        await user.update_data()
        await orm.destroy_pool()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    print("Test pass")
    loop.close()
