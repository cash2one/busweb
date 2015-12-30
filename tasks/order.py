# -*- coding:utf-8 -*-
import urllib2
import json
import datetime
import random
import traceback

from app.constants import *
from app import celery
from app.utils import getRedisObj
from app.email import send_email


@celery.task(bind=True, ignore_result=True)
def check_order_expire(self, order_no):
    """
    定时检查订单过期情况
    """
    from app.models import Order
    order = Order.objects.get(order_no=order_no)
    if order.status != STATUS_WAITING_ISSUE:
        return
    try:
        order.refresh_issued()
    except Exception, e:
        print traceback.format_exc()
    if order.status == STATUS_WAITING_ISSUE:
        self.retry(countdown=10, max_retries=30)


@celery.task(bind=True, ignore_result=True)
def refresh_kefu_order(self, username, order_no):
    """
    刷新客服订单状态
    """
    from app.models import Order, AdminUser
    order = Order.objects.get(order_no=order_no)
    user = AdminUser.objects.get(username=username)
    if order.status != STATUS_WAITING_ISSUE:
        return
    try:
        order.refresh_issued()
    except Exception, e:
        print e
    if order.status == STATUS_WAITING_ISSUE:
        self.retry(countdown=3+random.random()*10%3, max_retries=100)


@celery.task(bind=True, ignore_result=True)
def issue_fail_send_email(self, key):
    """
    连续3个单失败就发送邮件
    """
    r = getRedisObj()
    order_nos = r.smembers(key)
    order_nos = ','.join(list(order_nos))
    subject = '连续3个单失败'
    sender = 'dg@12308.com'
    recipients = ADMINS
    text_body = ''
    html_body = subject + '</br>' + 'order :%s error' % order_nos
    send_email(subject, sender, recipients, text_body, html_body)


@celery.task(bind=True, ignore_result=True)
def check_order_completed(self, username, key, order_no):
    """
    超过三分钟订单未处理
    """
    from app.models import Order
    r = getRedisObj()
    flag = r.sismember(key, order_no)
    orderObj = Order.objects.get(order_no=order_no)
    if flag:
        subject = "超过三分钟有未处理订单"
        content = '%s,超过三分钟有未处理订单:%s,下单时间:%s,12308订单号:%s' % (username, order_no, orderObj.create_date_time,orderObj.out_order_no)
        sender = 'dg@12308.com'
        recipients = ADMINS
        text_body = ''
        html_body = content
        send_email(subject, sender, recipients, text_body, html_body)