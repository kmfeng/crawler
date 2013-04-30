#!/usr/bin/python                                                                                                                                                                         
#--encoding: utf-8--                                                                                                                                                                      
                                                                                                                                                                                          
import time                                                                                                                                                                               
import re                                                                                                                                                                                 
import httplib                                                                                                                                                                            
import urllib                                                                                                                                                                             
import random                                                                                                                                                                             
import os                                                                                                                                                                                 
try:                                                                                                                                                                                      
    import simplejson as json                                                                                                                                                             
except ImportError:
    import json
import threading
import Queue

import gevent
from gevent import monkey
from gevent.pool import Pool

monkey.patch_all()

import sys
reload(sys)
sys.setdefaultencoding('UTF-8')

keywords_map = None
relative_map = None
ip_pool = ["180.153.152.37", "180.153.152.66", "180.153.152.67"]
#ip_pool = ["180.153.152.37"]
regex_relative = re.compile("relatedSearch.*search\?q=(.*)&")
regex_keywords = re.compile("\((.*)\)")
regex_dealing = re.compile('col\sdealing">\\xd7\\xee\\xbd\\xfc(.*)\\xc8\\xcb\\xb3\\xc9\\xbd\\xbb</div>')
queue = Queue.Queue()


def get_random_obj(obj):
    return random.choice(obj)


def get_keyword_list_url(keyword):
    parms = dict(
        extras = 1,
        code = "utf-8",
        bucket_id = 14,
        callback = "KISSY.Suggest.callback",
        q = keyword
    )
    hostname = "suggest.taobao.com"
    url = "/sug"
    return hostname, url, urllib.urlencode(parms)


def get_query_url(query):
    parms = dict(
        q = query,
        commend = "all",
        ssid = "s5-e",
        search_type = "item",
        sourceId = "tb.index",
        initiative_id = "tbindexz_20130426"
    )
    hostname = "s.taobao.com"
    url = "/search"
    return hostname, url, urllib.urlencode(parms)


def get_data(hostname, method="GET", url=None, body=None):
    conn = httplib.HTTPConnection(hostname, source_address=(get_random_obj(ip_pool), 0))
    headers = {'Accept-Language':'zh-cn','Accept-Encoding': 'gzip, deflate', \
                        'User-Agent': 'Mozilla/4.0 (compatible; MSIE 6.0;Windows NT 5.0)','Connection':' Keep-Alive' } 
    conn.request(method, url + "?" + body, headers=headers)
    data = conn.getresponse().read()
    conn.close()
    return data


def get_keyword_list_data(data):
    temp = dict()
    result = regex_keywords.findall(data)
    keywords = json.loads(result[0])['result']
    if keywords:
        for key in keywords:
            temp[urllib.unquote(key[0])] = key[1]
    return temp


def get_keyword_list(keyword):
    hostname, url, parms = get_keyword_list_url(keyword)
    data = get_data(hostname, url=url, body=parms)
    global keywords_map
    keywords_map = get_keyword_list_data(data)


def get_relative_list_data(data):
    temp = dict()
    r = regex_relative.findall(data)
    for i in r:
        temp[urllib.unquote(i)] = None
    return temp
    
    
def get_relative_list(keyword):
    hostname, url, parms = get_query_url(keyword)
    data = get_data(hostname, url=url, body=parms)
    global relative_map
    relative_map = get_relative_list_data(data)


final_keywords = dict()
def get_final_keywords(keyword):
    hostname, url, body = get_query_url(keyword)
    data = get_data(hostname, url=url, body=body)
    relative = get_relative_list_data(data)

    hostname, url, body = get_keyword_list_url(keyword)
    data = get_data(hostname, url=url, body=body)
    keywords = get_keyword_list_data(data)
    
    final_keywords[keyword] = relative.keys() + keywords.keys()


final_dealing = dict()
def get_detail_page(keyword):
    hostname, url, body = get_query_url(keyword)
    data = get_data(hostname, url=url, body=body)
    queue.put_nowait(data)

class CalDealing(threading.Thread):
    def __init__(self, queue):
        super(CalDealing, self).__init__()
        self.queue = queue
    
    def run(self):
        while 1:
            data = self.queue.get()
            final_dealing[keyword] = sum(map(int, regex_dealing.findall(data)))


if __name__ == '__main__':
    print "PID: ", os.getpid()
    master_key = sys.argv[1]
    f = lambda i,s: [i[x:x+s] for x in xrange(0, len(i), s)]
    split_size = 15
    
    start = time.time()
    
    thread_dealing = CalDealing(queue)
    thread_dealing.start()
    
    pool = Pool(size=32)
    
    pool.add(gevent.spawn(get_keyword_list, master_key))
    pool.add(gevent.spawn(get_relative_list, master_key))
    pool.join()
    

    ##########################################################

    allkeys = keywords_map.keys() + relative_map.keys()
    random.shuffle(allkeys)
    splited = f(allkeys, split_size)
    for keys in splited:
        pool = Pool(split_size)
        [pool.add(pool.spawn(get_final_keywords, key)) for key in keys]
        pool.join()

    ##########################################################

    def decode_print(v):
        try:
            print v.decode('GBK')
        except:
            print v

    count = 1
    last_list = list()
    for k,v in final_keywords.items():
        #decode_print(k)
        #print "-" * 10
        for i in v:
            #decode_print(i)
            last_list.append(i)
            count += 1
        #print
        #print

    print "根据 %s 共得到 %s 个关键词(包括下拉列表和推荐)" % (master_key, len(final_keywords.values()))
    
    print "根据 %s 个关键词最终得到 %s 个关键词" % (len(final_keywords.values()), count)

    ##########################################################

    random.shuffle(last_list)
    splited = f(last_list, split_size)

    for i in splited:
                pool = Pool(split_size)
                [pool.add(pool.spawn(get_detail_page, key)) for key in i]
                pool.join()

    ##########################################################

    end = time.time()
    print "全部完成，整个过程消耗时间：%.2f 秒" % float(end-start)
    
    thread_dealing.join()
    print final_dealing
