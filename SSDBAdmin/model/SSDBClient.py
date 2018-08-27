# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     SSDBClient
   Description :   SSDBClient
   Author :        JHao
   date：          2018/8/24
-------------------------------------------------
   Change Activity:
                   2018/8/24: SSDBClient
-------------------------------------------------
"""
__author__ = 'JHao'

from SSDBAdmin.utils.paginator import getPagingTabsInfo
from redis.connection import BlockingConnectionPool
from SSDBAdmin.setting import DB_CONFIG
from redis import Redis


def getSAServer(request):
    """
    Get key `SSDBADMIN_SERVER` from request’s cookie
    Args:
        request: flask request
    Returns:
        current ssdb's host and post
    """
    if 'SSDBADMIN_SERVER' in request.args:
        host, port = request.args.get('SSDBADMIN_SERVER').split(':')
    elif 'SSDBADMINSERVER' in request.cookies:
        host, port = request.cookies.get('SSDBADMINSERVER').split(':')
    else:
        server = DB_CONFIG[0]
        host = server.get('host', 'localhost')
        port = server.get('port', 8888)
    return host, port


class SSDBClient(object):
    def __init__(self, request):
        host, port = getSAServer(request)
        self.__conn = Redis(connection_pool=BlockingConnectionPool(host=host, port=int(port)))

    def serverInfo(self):
        """
        DB service info(version/links/size/stats ...)
        Returns:
            info message as dict
        """
        info_list = [_.decode() for _ in self.__conn.execute_command('info')]
        version = info_list[2]
        links = info_list[4]
        total_calls = info_list[6]
        db_size = info_list[8]
        bin_logs = info_list[10]
        service_key_range = info_list[12]
        data_key_range = info_list[14]
        stats = info_list[16]

        def _parseDiskUsage(_stats):
            return sum([int(each.split()[2]) for each in _stats.split('\n')[3:-1]])

        return {'info_list': info_list, 'version': version, 'links': links, 'total_calls': total_calls,
                'db_size': db_size, 'bin_logs': bin_logs, 'service_key_range': service_key_range,
                'data_key_range': data_key_range,
                'stats': stats, 'disk_usage': _parseDiskUsage(stats)}

    # region queue operate
    def queueList(self, name_start, name_end, page_num, page_size):
        """
        return queue/list items in range(`name_start`, `name_end`)
        Args:
            name_start: The lower bound(not included) of keys to be returned, empty string ``''`` means -inf
            name_end: The upper bound(included) of keys to be returned, empty string ``''`` means +inf
            page_num: page number
            page_size: items size per page
        Returns:
            items list
        """
        limit = (page_num + 1) * page_size
        items_list = [_.decode() for _ in self.__conn.execute_command('qlist', name_start, name_end, limit)]
        page_count, page_num = getPagingTabsInfo(data_count=len(items_list), page_no=page_num, page_row_num=page_size)
        has_next = True if page_count > page_num else False
        queue_list = map(lambda queue_name: {'name': queue_name, 'size': self.__conn.llen(queue_name)},
                         items_list[(page_num - 1) * page_size: page_num * page_size])
        return queue_list, has_next

    def queuePush(self, queue_name, item, push_type):
        """
        Add `item` to the back/front(`push_type`) of queue which named `queue_name`
        Args:
            queue_name: queue's name
            item: the push item
            push_type: push type (back/front)
        Returns:
            None
        """
        if push_type == 'front':
            self.__conn.lpush(queue_name, item)
        else:
            # push_type = 'back'
            self.__conn.rpush(queue_name, item)

    def queuePop(self, queue_name, number, pop_type):
        """
        Pop `number` items from head/end(`pop_type`) of the queue which named `queue_name`
        Args:
            queue_name: queue name
            number: the number of pop items
            pop_type: back/front
        Returns:
            None
        """
        if pop_type == 'front':
            self.__conn.execute_command('qpop_front', queue_name, int(number))
        else:
            # pop_type = 'back
            self.__conn.execute_command('qpop_back', queue_name, int(number))

    def queueRange(self, queue_name, offset, limit):
        """
        Return a portion of item from the queue which named `queue_name`
        at the specified range[`offset`, `offset` + `limit`]
        Args:
            queue_name: queue_name: queue name
            offset: offset
            limit: limit

        Returns:
            items as List
        """
        start, end = int(offset), int(offset) + int(limit) - 1
        items_list = self.__conn.lrange(queue_name, start, end)
        return [_.decode('utf8') for _ in items_list if isinstance(_, bytes)]

    def queueSize(self, queue_name):
        """
        the size of queue
        Args:
            queue_name: queue name
        Returns:
            size(int)
        """
        return self.__conn.llen(queue_name)

    def queueGet(self, queue_name, index):
        """
        Get the item at `index` position from the queue which named `queue_name`
        Args:
            queue_name: queue name
            index: index (int)

        Returns:
            item info (str)
        """
        return self.__conn.lindex(queue_name, int(index)).decode()

    def queueClear(self, queue_name):
        """
        **Clear&Delete** the queue specified by `queue_name`
        Args:
            queue_name: queue name
        Returns:
            None
        """
        return self.__conn.execute_command('qclear', queue_name)

    # endregion queue operate


if __name__ == '__main__':
    class R(object):
        @property
        def args(self):
            return {"SSDBADMIN_SERVER": "118.24.52.95:8899"}

        @property
        def cookies(self):
            return {"SSDBADMIN_SERVER": "118.24.52.95:8899"}


    request = R()
    db = SSDBClient(request)
    for i in range(30):
        db.queuePush(0, i, 'back')
