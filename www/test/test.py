import time
import uuid


class Meta(type):
    def __new__(mcs, name, parents, attributes):
        print('Name: ', name)
        print('Parents: ', parents)
        print('Attributes: ', attributes)
        return type.__new__(mcs, name, parents, attributes)


class Test(dict, metaclass=Meta):
    name = 'test'
    id = '2'

    def __init__(self, name):
        super(Test, self).__init__()
        self.name = name

t = Test('123')
print(t.name)
# 如果实例没有这个attributes 会自动去父类中寻找
print(t.id)


def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)
print(next_id())

