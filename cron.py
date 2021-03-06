#!/usr/bin/env python
# -*- coding:utf-8 *-*
'''
计划任务配置
'''
import requests
import traceback
import time

from app.constants import *
from apscheduler.scheduler import Scheduler
from datetime import datetime as dte
# from app.email import send_email
# from app.constants import ADMINS
from app import setup_app
from app import cron_log
from app.utils import get_redis


app = setup_app()


def check(run_in_local=False):
    """
    run_in_local 是否允许在local环境运行
    """
    def wrap(func):
        def sub_wrap(*args, **kwargs):
            res = None
            try:
                if not run_in_local and app.config["DEBUG"]:
                    cron_log.info("[ignore] forbid run at debug mode")
                    return None
                t1 = time.time()
                #cron_log.info("[start] %s %s %s", func.__name__, args, kwargs)
                with app.app_context():
                    res = func(*args, **kwargs)
                cost = time.time() - t1
                cron_log.info("[succss] %s %s %s, return: %s, cost time: %s", func.__name__, args, kwargs, res, cost)
            except:
                cron_log.error("%s,%s,%s", traceback.format_exc(), args, kwargs)
            return res
        return sub_wrap
    return wrap


@check(run_in_local=True)
def refresh_order_status():
    from app.models import Order
    cnt = 0
    for o in Order.objects.filter(status__in=[3, 12]):
        cnt += 1
        try:
            o.refresh_status()
        except:
            pass
    return cnt


@check(run_in_local=True)
def refresh_station():
    from app.models import OpenStation
    for obj in OpenStation.objects.all():
        obj.refresh()


@check()
def bus_crawl(crawl_source, province_id = None, crawl_kwargs={}):
    url_list = app.config["SCRAPYD_URLS"]
    data = {
          "project": "BusCrawl",
          "spider": crawl_source,
    }
    if province_id:
        data.update(province_id=province_id)
    data.update(crawl_kwargs)

    res_lst = []
    for url in url_list:
        res = requests.post(url, data=data)
        res_lst.append("%s: %s" % (url, res.content))


@check()
def refresh_order_fail_rate():
    from app.models import OpenStation
    from tasks import async_send_email
    today_str = dte.now().strftime("%Y-%m-%d")
    body = ''
    subject = '下单失败率高'
    for obj in OpenStation.objects.all():
        if not (obj.close_status & STATION_CLOSE_YZCX):
            res = obj.day_order_count[today_str]
            fail_ct = res['fail']
            total_ct = res['total']
            if obj.crawl_source:
                if total_ct >= 3:
                    fail_rate = fail_ct/float(total_ct)
                    if fail_rate > 0.8:
                        body += "源站: %s,<br/> 车站: %s,<br/>失败率:%s ,<br/><br/>" % (SOURCE_INFO[obj.crawl_source]['name'],obj.sta_name,"%.2f%%" %(fail_rate*100))
    if body:
        async_send_email(subject, body)

@check()
def check_autopay():
    from app.models import AdminUser
    from tasks import async_send_email
    qs = AdminUser.objects.filter(is_close=False)
    users = list(qs.filter(username__startswith="snmpay")) + list(qs.filter(username__in=["luojunping2"]))
    for u in users:
        if not u.status_check_info:
            continue
        dt = u.status_check_info["dt"]
        if (dte.now() - dt).total_seconds() > 90:
            # 支付宝掉线了
            subject = "支付宝失联-%s" % u.username
            body = subject + "<br/>" + str(dte.now())
            async_send_email(subject, body)
            break
        money = u.status_check_info.get("yue", 0) + u.status_check_info.get("yuebao", 0)
        if money < 5000:
            # 没钱了
            subject = "支付宝余额不足-%s" % u.username
            body = subject + "<br/>" + str(dte.now())
            async_send_email(subject, body)
            break

@check()
def delete_source_riders():
    """
    删除源站乘客信息
    """
    from app.models import get_rebot_class
    for source in SOURCE_INFO.keys():
        for rebot_cls in get_rebot_class(source):
            if not hasattr(rebot_cls, "clear_riders"):
                continue
            for rebot in rebot_cls.objects.all():
                rebot.clear_riders()


@check(run_in_local=True)
def clear_lines():
    """
    清理过期线路数据
    """
    from app.models import Line
    today = dte.now().strftime("%Y-%m-%d")
    cnt = Line.objects.filter(drv_date__lt=today).delete()
    return "%s line deleted" % cnt


@check(run_in_local=True)
def clear_redis_data():
    """
    清理redis数据
    """
    r = get_redis("default")
    now = time.time()
    result = {}
    for k in r.keys("line:done:*"):
        result[k] = 0
        for sk, v in r.hgetall(k).items():
            if now-float(v) > 12*60*60:
                r.hdel(k, sk)
                result[k] += 1
    return result


@check(run_in_local=False)
def crawl_proxy_haodaili():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_haodaili()
    data["haodaili"] = cnt
    return data


@check(run_in_local=False)
def crawl_proxy_mimiip():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_mimiip()
    data["mimiip"] = cnt
    return data

@check(run_in_local=False)
def crawl_proxy_kuaidaili():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_kuaidaili()
    data["kuaidaili"] = cnt
    return data

@check(run_in_local=False)
def crawl_proxy_samair():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_samair()
    data["samair"] = cnt
    return data


@check(run_in_local=False)
def crawl_proxy_66ip():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_66ip()
    data["66ip"] = cnt
    return data

@check(run_in_local=False)
def crawl_proxy_xici():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_xici()
    data["xici"] = cnt
    return data

@check(run_in_local=False)
def crawl_proxy_zdaye():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_zdaye()
    data["zdaye"] = cnt
    return data

@check(run_in_local=False)
def crawl_proxy_kxdaili():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_kxdaili()
    data["kxdaili"] = cnt
    return data

@check(run_in_local=False)
def crawl_proxy_ip181():
    from app.proxy import proxy_producer
    data = {}
    cnt = proxy_producer.crawl_from_ip181()
    data["ip181"] = cnt
    return data

@check(run_in_local=False)
def check_proxy():
    from app.proxy import proxy_producer
    for ipstr in proxy_producer.all_proxy():
        if not proxy_producer.valid_proxy(ipstr):
            proxy_producer.remove_proxy(ipstr)
    return proxy_producer.proxy_size()


@check(run_in_local=False)
def check_consumer_proxy(name):
    from tasks import check_remove_proxy_ip
    from app.proxy import get_proxy
    consumer = get_proxy(name)
    for ipstr in consumer.all_proxy():
        check_remove_proxy_ip.delay(name, ipstr)
    return consumer.proxy_size()


def main():
    sched = Scheduler(daemonic=False)

    # 巴士壹佰
    #sched.add_cron_job(bus_crawl, hour=12, minute=10, args=['bus100', "450000"]) #广西
    #sched.add_cron_job(bus_crawl, hour=18, minute=20, args=['bus100', "370000"]) #山东
    #sched.add_cron_job(bus_crawl, hour=19, minute=40, args=['bus100', "410000"]) #河南

    # 巴巴快巴
    # sched.add_cron_job(bus_crawl, hour=22, minute=10, args=['baba'], kwargs={"crawl_kwargs":{"province": "安徽"}})
    sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['baba'], kwargs={"crawl_kwargs":{"province": "江苏"}})
    sched.add_cron_job(bus_crawl, hour=20, minute=10, args=['baba'], kwargs={"crawl_kwargs":{"province": "上海"}})

    # 方便网
    # sched.add_cron_job(bus_crawl, hour=1, minute=0, args=['fangbian'], kwargs={"crawl_kwargs":{"province": "山东"}})
    #sched.add_cron_job(bus_crawl, hour=23, minute=0, args=['fangbian'], kwargs={"crawl_kwargs":{"province": "河南"}})
    #sched.add_cron_job(bus_crawl, hour=23, minute=0, args=['fangbian'], kwargs={"crawl_kwargs":{"province": "广西"}})
    # sched.add_cron_job(bus_crawl, hour=2, minute=0, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "苏州,张家港"}})
    # sched.add_cron_job(bus_crawl, hour=2, minute=0, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "昆山,太仓"}})
    # sched.add_cron_job(bus_crawl, hour=2, minute=0, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "常熟,吴江"}})
    # sched.add_cron_job(bus_crawl, hour=3, minute=10, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "南京"}})
    # sched.add_cron_job(bus_crawl, hour=3, minute=5, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "无锡"}})
    # sched.add_cron_job(bus_crawl, hour=3, minute=10, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "常州"}})
    # sched.add_cron_job(bus_crawl, hour=4, minute=30, args=['fangbian'], kwargs={"crawl_kwargs":{"city": "重庆"}})
    # sched.add_cron_job(bus_crawl, hour=4, minute=10, args=['fangbian'], kwargs={"crawl_kwargs":{"province": "四川"}})
    # sched.add_cron_job(bus_crawl, hour=5, minute=10, args=['fangbian'], kwargs={"crawl_kwargs":{"province": "南通"}})

    #贵州汽车票务网
#     sched.add_cron_job(bus_crawl, hour=1, minute=10, args=['gzqcp'])

    # 重庆客运
    sched.add_cron_job(bus_crawl, hour=19, minute=0, args=['cqky'])

    # 四川
#     sched.add_cron_job(bus_crawl, hour=15, minute=0, args=['scqcp'], kwargs={"crawl_kwargs":{"city": "成都市,绵阳市,南充市,德阳市,宜宾市"}})
#     sched.add_cron_job(bus_crawl, hour=18, minute=0, args=['scqcp'])

    # 江苏道路客运
    sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['jsdlky'])

    # 泰州客运
    sched.add_cron_job(bus_crawl, hour=21, minute=0, args=['tzky'])

    # 畅途网
    # sched.add_cron_job(bus_crawl, hour=20, minute=30, args=['changtu'], kwargs={"crawl_kwargs":{"city": "南京"}})
    # sched.add_cron_job(bus_crawl, hour=16, minute=30, args=['changtu'], kwargs={"crawl_kwargs":{"province": "济南"}})
    sched.add_cron_job(bus_crawl, hour=17, minute=30, args=['changtu'], kwargs={"crawl_kwargs":{"city": "淄博"}})
    sched.add_cron_job(bus_crawl, hour=19, minute=0, args=['changtu'], kwargs={"crawl_kwargs":{"city": "威海"}})
    sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['changtu'], kwargs={"crawl_kwargs":{"city": "天津"}})
    sched.add_cron_job(bus_crawl, hour=0, minute=15, args=['changtu'], kwargs={"crawl_kwargs":{"province": "湖南"}})
    sched.add_cron_job(bus_crawl, hour=3, minute=15, args=['changtu'], kwargs={"crawl_kwargs":{"province": "广东"}})

    # 江苏客运
    # sched.add_cron_job(bus_crawl, hour=8, minute=0, args=['jsky'], kwargs={"crawl_kwargs":{"city": "苏州,张家港"}})
    # sched.add_cron_job(bus_crawl, hour=9, minute=30, args=['jsky'], kwargs={"crawl_kwargs":{"city": "江阴,宜兴"}})
    # sched.add_cron_job(bus_crawl, hour=16, minute=0, args=['jsky'], kwargs={"crawl_kwargs":{"city": "宿迁"}})
    # sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['jsky'], kwargs={"crawl_kwargs":{"city": "徐州"}})
    # sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['jsky'], kwargs={"crawl_kwargs":{"city": "南京"}})
    # sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['jsky'], kwargs={"crawl_kwargs":{"city": "南通"}})
    # sched.add_cron_job(bus_crawl, hour=19, minute=10, args=['jsky'], kwargs={"crawl_kwargs":{"city": "无锡"}})
    # sched.add_cron_job(bus_crawl, hour=19, minute=10, args=['jsky'], kwargs={"crawl_kwargs":{"city": "常州"}})
    # sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['jsky'], kwargs={"crawl_kwargs":{"city": "昆山,太仓"}})
    # sched.add_cron_job(bus_crawl, hour=20, minute=30, args=['jsky'], kwargs={"crawl_kwargs":{"city": "常熟,吴江"}})
    # sched.add_cron_job(bus_crawl, hour=21, minute=30, args=['jsky'], kwargs={"crawl_kwargs":{"city": "泰州"}})

    # 车巴达
    # sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['cbd'], kwargs={"crawl_kwargs":{"city": "苏州, 张家港"}})
    # sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['cbd'], kwargs={"crawl_kwargs":{"city": "南京"}})
    # sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['cbd'], kwargs={"crawl_kwargs":{"city": "南通"}})
    # sched.add_cron_job(bus_crawl, hour=19, minute=10, args=['cbd'], kwargs={"crawl_kwargs":{"city": "无锡"}})
    # sched.add_cron_job(bus_crawl, hour=19, minute=10, args=['cbd'], kwargs={"crawl_kwargs":{"city": "常州"}})
    # sched.add_cron_job(bus_crawl, hour=20, minute=30, args=['cbd'], kwargs={"crawl_kwargs":{"city": "昆山,太仓"}})
    # sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['cbd'], kwargs={"crawl_kwargs":{"city": "常熟,吴江"}})

    # 同程旅行
    sched.add_cron_job(bus_crawl, hour=13, minute=30, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"province": "江苏"}})
    # sched.add_cron_job(bus_crawl, hour=17, minute=10, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "南通"}})
    # sched.add_cron_job(bus_crawl, hour=17, minute=30, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "天津"}})
    # sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "无锡"}})
    # sched.add_cron_job(bus_crawl, hour=19, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "镇江,宜兴"}})
    # sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "徐州"}})
    # sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "兴化,江阴"}})
    # sched.add_cron_job(bus_crawl, hour=0, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "连云港,扬州"}})
    # # sched.add_cron_job(bus_crawl, hour=1, minute=30, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "南京"}})
    # sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "苏州,张家港"}})
    # sched.add_cron_job(bus_crawl, hour=19, minute=10, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "常州"}})
    # sched.add_cron_job(bus_crawl, hour=21, minute=30, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "昆山,太仓"}})
    # sched.add_cron_job(bus_crawl, hour=21, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "常熟,吴江"}})
    # # sched.add_cron_job(bus_crawl, hour=1, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "盐城"}})
    # sched.add_cron_job(bus_crawl, hour=6, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "句容,靖江,大丰,扬中,溧阳"}})
    # sched.add_cron_job(bus_crawl, hour=5, minute=0, args=['tongcheng_app'], kwargs={"crawl_kwargs":{"city": "射阳,滨海,盱眙,涟水"}})

    # 快巴
    #sched.add_cron_job(bus_crawl, hour=20, minute=30, args=['kuaiba'], kwargs={"crawl_kwargs":{"province": "北京"}})

#     # 辽宁省网
#     sched.add_cron_job(bus_crawl, hour=1, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "沈阳市,康平县,法库县,辽中县,新民市"}})
#     sched.add_cron_job(bus_crawl, hour=1, minute=40, args=['lnky'], kwargs={"crawl_kwargs":{"city": "大连市,瓦房店市,普兰店市,庄河市"}})
#     sched.add_cron_job(bus_crawl, hour=2, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "锦州市,凌海市,北镇市,义县,黑山县"}})
#     sched.add_cron_job(bus_crawl, hour=2, minute=40, args=['lnky'], kwargs={"crawl_kwargs":{"city": "辽阳市,灯塔市,弓长岭"}})
#     sched.add_cron_job(bus_crawl, hour=3, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "营口市,大石桥市,盖州市"}})
#     sched.add_cron_job(bus_crawl, hour=3, minute=40, args=['lnky'], kwargs={"crawl_kwargs":{"city": "铁岭市,西丰县,昌图县,开原市,调兵山市"}})
#     sched.add_cron_job(bus_crawl, hour=4, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "鞍山市,海城市,台安县"}})
#     sched.add_cron_job(bus_crawl, hour=4, minute=40, args=['lnky'], kwargs={"crawl_kwargs":{"city": "抚顺市,清原县,新宾县"}})
#     sched.add_cron_job(bus_crawl, hour=5, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "本溪市"}})
#     sched.add_cron_job(bus_crawl, hour=5, minute=20, args=['lnky'], kwargs={"crawl_kwargs":{"city": "丹东市,凤城市,东港市"}})
#     sched.add_cron_job(bus_crawl, hour=5, minute=30, args=['lnky'], kwargs={"crawl_kwargs":{"city": "阜新市,彰武县"}})
#     sched.add_cron_job(bus_crawl, hour=5, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "葫芦岛市,建昌县,绥中县,兴城市"}})
#     sched.add_cron_job(bus_crawl, hour=3, minute=20, args=['lnky'], kwargs={"crawl_kwargs":{"city": "朝阳市,北票市,凌源市,建平县,喀左县"}})
#     sched.add_cron_job(bus_crawl, hour=4, minute=10, args=['lnky'], kwargs={"crawl_kwargs":{"city": "盘锦市,大洼县"}})

    #张家港市民网页 & 无线苏州
    sched.add_cron_job(bus_crawl, hour=23, minute=30, args=['zjgsm'], kwargs={"crawl_kwargs":{"city": "张家港"}})
    # sched.add_cron_job(bus_crawl, hour=0, minute=30, args=['zjgsm'], kwargs={"crawl_kwargs":{"city": "苏州"}})
    sched.add_cron_job(bus_crawl, hour=1, minute=30, args=['zjgsm'], kwargs={"crawl_kwargs":{"city": "常熟"}})
    sched.add_cron_job(bus_crawl, hour=2, minute=0, args=['zjgsm'], kwargs={"crawl_kwargs":{"city": "太仓"}})
    sched.add_cron_job(bus_crawl, hour=2, minute=30, args=['zjgsm'], kwargs={"crawl_kwargs":{"city": "吴江"}})
    sched.add_cron_job(bus_crawl, hour=3, minute=0, args=['zjgsm'], kwargs={"crawl_kwargs":{"city": "昆山"}})

    # sched.add_cron_job(bus_crawl, hour=18, minute=30, args=['wxsz'], kwargs={"crawl_kwargs":{"city": "张家港"}})
    sched.add_cron_job(bus_crawl, hour=18, minute=30, args=['wxsz'], kwargs={"crawl_kwargs":{"city": "苏州"}})
    sched.add_cron_job(bus_crawl, hour=19, minute=30, args=['wxsz'], kwargs={"crawl_kwargs":{"city": "常熟"}})
    sched.add_cron_job(bus_crawl, hour=19, minute=0, args=['wxsz'], kwargs={"crawl_kwargs":{"city": "太仓"}})
    sched.add_cron_job(bus_crawl, hour=20, minute=30, args=['wxsz'], kwargs={"crawl_kwargs":{"city": "吴江"}})
    sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['wxsz'], kwargs={"crawl_kwargs":{"city": "昆山"}})


    #携程
    sched.add_cron_job(bus_crawl, hour=15, minute=0, args=['ctrip'], kwargs={"crawl_kwargs":{"province": "北京"}})

    #北京省网
    sched.add_cron_job(bus_crawl, hour=8, minute=30, args=['bjky'])

    #唐山省网
    sched.add_cron_job(bus_crawl, hour=17, minute=10, args=['hebky'],kwargs={"crawl_kwargs":{"city": "唐山"}})

#     #内蒙古呼运
#     sched.add_cron_job(bus_crawl, hour=16, minute=10, args=['nmghy'])

    #巴士365
#     sched.add_cron_job(bus_crawl, hour=1, minute=20, args=['bus365'], kwargs={"crawl_kwargs":{"city": "哈尔滨市,齐齐哈尔,鸡西市,鹤岗市,双鸭山市,大庆市,伊春市,佳木斯市,七台河市,牡丹江市,黑河市"}})
#     sched.add_cron_job(bus_crawl, hour=1, minute=40, args=['bus365'], kwargs={"crawl_kwargs":{"city": "长春市,吉林市,四平市,辽源市,通化市,白山市,松原市,白城市,图们市,敦化市"}})
#     sched.add_cron_job(bus_crawl, hour=1, minute=10, args=['bus365'], kwargs={"crawl_kwargs":{"city": "兰州市,嘉峪关市,金昌市,白银市,天水市,武威市,张掖市,平凉市,酒泉市,庆阳市,定西市,陇南市"}})
#     sched.add_cron_job(bus_crawl, hour=1, minute=30, args=['bus365'], kwargs={"crawl_kwargs":{"city": "西宁市,乐都县,海北州,祁连县"}})
#     sched.add_cron_job(bus_crawl, hour=2, minute=10, args=['bus365'], kwargs={"crawl_kwargs":{"city": "呼和浩特,赤峰市,巴林左旗,巴林右旗,通辽市,海拉尔,正蓝旗,集宁区"}})

#     # 新途云
#     sched.add_cron_job(bus_crawl, hour=16, minute=10, args=['xintuyun'])

    # 河南
    sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['hn96520'])

    # 广东省网
    sched.add_cron_job(bus_crawl, hour=16, minute=0, args=['gdsw'], kwargs={"crawl_kwargs":{"city": "深圳,东莞,惠州,茂名,阳江,梅州,河源,揭阳,珠海,江门"}})
    sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['gdsw'], kwargs={"crawl_kwargs":{"city": "湛江,汕尾,清远,潮州,肇庆,韶关,佛山,中山,汕头,云浮"}})

    # 坐车网
    sched.add_cron_job(bus_crawl, hour=22, minute=0, args=['zuoche'])

    # 徐运集团
    sched.add_cron_job(bus_crawl, hour=21, minute=0, args=['xyjt'])

    # 珠海汽车购票
    sched.add_cron_job(bus_crawl, hour=11, minute=0, args=['zhw'])

    # 山东365汽车票
    sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['sd365'], kwargs={"crawl_kwargs":{"province": "山东"}})
    sched.add_cron_job(bus_crawl, hour=21, minute=10, args=['sd365'], kwargs={"crawl_kwargs":{"province": "天津"}})

    # 山东交运
    sched.add_cron_job(bus_crawl, hour=18, minute=10, args=['glcx'])

    # 青岛客运
#     sched.add_cron_job(bus_crawl, hour=2, minute=0, args=['qdky'])

    # 深圳客运
    sched.add_cron_job(bus_crawl, hour=20, minute=0, args=['szky'])

    # 旅途100
    sched.add_cron_job(bus_crawl, hour=23, minute=10, args=['lvtu100'], kwargs={"crawl_kwargs":{"province": "江西"}})
    sched.add_cron_job(bus_crawl, hour=1, minute=0, args=['lvtu100'], kwargs={"crawl_kwargs":{"province": "安徽"}})

    #东莞客运
#     sched.add_cron_job(bus_crawl, hour=12, minute=0, args=['dgky'], kwargs={"crawl_kwargs":{"city": "东莞总站"}})
#     sched.add_cron_job(bus_crawl, hour=13, minute=0, args=['dgky'], kwargs={"crawl_kwargs":{"city": "长安客运站"}})
#     sched.add_cron_job(bus_crawl, hour=14, minute=0, args=['dgky'], kwargs={"crawl_kwargs":{"city": "东莞市南城汽车客运站,"}})
#     sched.add_cron_job(bus_crawl, hour=14, minute=30, args=['dgky'], kwargs={"crawl_kwargs":{"city": "石龙客运站,石龙千里客运站,桥头车站,东坑车站"}})
#     sched.add_cron_job(bus_crawl, hour=15, minute=0, args=['dgky'], kwargs={"crawl_kwargs":{"city": "市客运东站,石排客运站,樟木头振通车站"}})
#     sched.add_cron_job(bus_crawl, hour=15, minute=30, args=['dgky'], kwargs={"crawl_kwargs":{"city": "大朗汽车客运站,凤岗客运站"}})
#     sched.add_cron_job(bus_crawl, hour=16, minute=0, args=['dgky'], kwargs={"crawl_kwargs":{"city": "塘厦车站"}})
#     sched.add_cron_job(bus_crawl, hour=16, minute=30, args=['dgky'], kwargs={"crawl_kwargs":{"city": "松山湖汽车客运站,上沙汽车客运站,虎门客运站,厚街专线车站,东城汽车客运站,沙田汽车客运站,清溪客运站"}})
#     sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['dgky'], kwargs={"crawl_kwargs":{"city": "市客运北站,东莞市黄江汽车客运站"}})


#     #e8s
#     sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['e8s'])
#
#     #wmcx
#     sched.add_cron_job(bus_crawl, hour=21, minute=10, args=['wmcx'], kwargs={"crawl_kwargs":{"province": "安徽"}})

    #fjky
    sched.add_cron_job(bus_crawl, hour=14, minute=30, args=['fjky'], kwargs={"crawl_kwargs":{"city": "南平市,宁德市,福安市,福鼎市,古田县,光泽县,,霞浦县,政和县,周宁县,柘荣县"}})
    sched.add_cron_job(bus_crawl, hour=15, minute=0, args=['fjky'], kwargs={"crawl_kwargs":{"city": "建阳市,建瓯市,明溪县,屏南县,浦城县,邵武市,寿宁县,顺昌县,松溪县,武夷山市,"}})
    sched.add_cron_job(bus_crawl, hour=15, minute=30, args=['fjky'], kwargs={"crawl_kwargs":{"city": "厦门市"}})

    #海南海汽
    sched.add_cron_job(bus_crawl, hour=17, minute=0, args=['hainky'])

    # 安行巴士
    sched.add_cron_job(bus_crawl, hour=21, minute=0, args=['anxingbus'], kwargs={"crawl_kwargs":{"province": "安徽"}})
    sched.add_cron_job(bus_crawl, hour=23, minute=0, args=['anxingbus'], kwargs={"crawl_kwargs":{"province": "上海"}})
    sched.add_cron_job(bus_crawl, hour=3, minute=0, args=['anxingbus'], kwargs={"crawl_kwargs":{"province": "江苏"}})

    #上海客运总站
    sched.add_cron_job(bus_crawl, hour=16, minute=0, args=['shkyzz'])

    # 代理ip相关
    sched.add_interval_job(crawl_proxy_haodaili, minutes=6)
    # sched.add_interval_job(crawl_proxy_mimiip, minutes=7)
    sched.add_interval_job(crawl_proxy_kuaidaili, minutes=6)
    # sched.add_interval_job(crawl_proxy_samair, minutes=10)
    # sched.add_interval_job(crawl_proxy_66ip, minutes=10)
    # sched.add_interval_job(crawl_proxy_xici, minutes=10)
    sched.add_interval_job(crawl_proxy_zdaye, minutes=6)
    # sched.add_interval_job(crawl_proxy_kxdaili, minutes=5)
    sched.add_interval_job(crawl_proxy_ip181, minutes=10)

    sched.add_interval_job(check_proxy, minutes=2)
    sched.add_interval_job(check_consumer_proxy, args=["cqky"], minutes=3)
    sched.add_interval_job(check_consumer_proxy, args=["hn96520"], minutes=3)
    sched.add_interval_job(check_consumer_proxy, args=["sd365"], minutes=3)
    sched.add_interval_job(check_consumer_proxy, args=["tongcheng"], minutes=3)
    # sched.add_interval_job(check_consumer_proxy, args=["cbd"], minutes=1)
#     sched.add_interval_job(check_consumer_proxy, args=["scqcp"], minutes=2)
    # sched.add_interval_job(check_consumer_proxy, args=["bjky"], minutes=1)
    #sched.add_interval_job(check_consumer_proxy, args=["lnky"], minutes=1)
    # sched.add_interval_job(check_consumer_proxy, args=["e8s"], minutes=1)
    # sched.add_interval_job(check_consumer_proxy, args=["changtu"], minutes=2)
    # sched.add_interval_job(check_consumer_proxy, args=["bus365"], minutes=2)


    #(补救措施) 定时刷新状态
    sched.add_interval_job(refresh_order_status, minutes=4)

    # 定时刷新站统计信息
    sched.add_interval_job(refresh_station, minutes=20)

    #发送订单失败邮件
    sched.add_interval_job(refresh_order_fail_rate, minutes=30)

    # 自动支付账号定时检查
    sched.add_interval_job(check_autopay, minutes=2)

    # 其他
    sched.add_cron_job(delete_source_riders, hour=22, minute=40)
    sched.add_cron_job(clear_lines, hour=1, minute=0)
    sched.add_cron_job(clear_redis_data, hour=5, minute=0)

    sched.start()

if __name__ == '__main__':
    main()
