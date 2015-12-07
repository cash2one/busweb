# -*- coding:utf-8 -*-
import math
import urllib2
import urllib
import requests
import json
import random
import pytesseract
import cStringIO

from PIL import Image
from lxml import etree
from mongoengine import Q
from app.constants import STATUS_MSG, SOURCE_MSG, BROWSER_USER_AGENT, SCQCP_ACCOUNTS
from flask import render_template, request, redirect, url_for, current_app, make_response
from flask.views import MethodView
from app.admin import admin
from app.models import Order, Line, Starting, Destination


def parse_page_data(qs):
    total = qs.count()
    page = int(request.args.get("page", default=1))
    pageCount = int(request.args.get("pageCount", default=10))
    pageNum = int(math.ceil(total*1.0/pageCount))
    skip = (page-1)*pageCount
    range_min = max(1, page-5)
    range_max = min(range_min+10, pageNum)

    query_dict = {}
    for k in  request.args.keys():
        if k == "page":
            continue
        query_dict[k] = request.args.get(k)
    query_string = urllib.urlencode(query_dict)

    return {
        "total": total,
        "pageCount": pageCount,
        "pageNum": pageNum,
        "page": page,
        "skip": skip,
        "previous": page-1,
        "next": page+1,
        "range": range(range_min, range_max),
        "items": qs[skip: skip+pageCount],
        "req_path": "%s?%s" % (request.path, query_string),
        "req_path2": "%s?" % request.path,
    }


@admin.route('/', methods=['GET'])
@admin.route('/orders', methods=['GET'])
def order_list():
    order_no =request.args.get("order_no", "")
    if order_no:
        qs = Order.objects.filter(order_no=order_no)
    else:
        qs = Order.objects
    qs = qs.order_by("-create_date_time")
    return render_template('admin/order_list.html',
                           page=parse_page_data(qs),
                           status_msg=STATUS_MSG,
                           source_msg=SOURCE_MSG,
                           scqcp_accounts=SCQCP_ACCOUNTS,
                           order_no=order_no,
                           )


@admin.route('/lines', methods=['GET'])
def line_list():
    lineid = request.args.get("line_id", "")
    starting_name = request.args.get("starting", "")
    dest_name = request.args.get("destination", "")
    queryset = Line.objects
    query = {}
    if lineid:
        query.update(line_id=lineid)
    if starting_name:
        qs_starting = Starting.objects(Q(city_name__startswith=starting_name) |
                                       Q(station_name__startswith=starting_name))
        query.update(starting__in=qs_starting)
    if dest_name:
        qs_dest = Destination.objects(Q(city_name__startswith=dest_name) |
                                      Q(station_name__startswith=dest_name))
        query.update(destination__in=qs_dest)
    queryset = Line.objects(**query)
    return render_template('admin/line_list.html',
                           page=parse_page_data(queryset),
                           starting=starting_name,
                           destination=dest_name,
                           line_id=lineid,
                           )


@admin.route('/orders/<order_no>/pay', methods=['GET'])
def order_pay(order_no):
    order = Order.objects.get(order_no=order_no)
    if order.crawl_source == "scqcp":
        pay_url = order.pay_url
        headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 6.2) AppleWebKit/536.3  (KHTML, like Gecko) Chrome/19.0.1061.0 Safari/536.3",
        }
        login_form_url = "http://scqcp.com/login/index.html"
        r = requests.get(login_form_url, headers=headers)
        sel = etree.HTML(r.content)
        cookies = dict(r.cookies)
        code_url = sel.xpath("//img[@id='txt_check_code']/@src")[0]
        token = sel.xpath("//input[@id='csrfmiddlewaretoken1']/@value")[0]

        r = requests.get(code_url, headers=headers, cookies=cookies)
        cookies.update(dict(r.cookies))
        tmpIm = cStringIO.StringIO(r.content)
        im = Image.open(tmpIm)
        code = pytesseract.image_to_string(im)
        passwd, _ = SCQCP_ACCOUNTS[order.source_account]

        data = {
            "uname": order.source_account,
            "passwd": passwd,
            "code": code,
            "token": token,
        }
        r = requests.post("http://scqcp.com/login/check.json", data=data, headers=headers, cookies=cookies)
        cookies.update(dict(r.cookies))
        ret = r.json()
        if ret["success"] == True:
            print('登录成功')
            r = requests.get(pay_url, headers=headers, cookies=cookies)
            sel = etree.HTML(r.content)
            data = dict(
                payid=sel.xpath("//input[@name='payid']/@value")[0],
                bank=sel.xpath("//input[@id='s_bank']/@value")[0],
                plate=sel.xpath("//input[@id='s_plate']/@value")[0],
                plateform="alipay",
                qr_pay_mode=0,
                discountCode=sel.xpath("//input[@id='discountCode']/@value")[0]
            )

            info_url = "http://scqcp.com:80/ticketOrder/middlePay.html"
            r = requests.post(info_url, data=data, headers=headers, cookies=cookies)
            return r.content
            sel = etree.HTML(r.content)
            data = {}
            for s in sel.xpath("//input"):
                data[s.get("name")] = s.get("value")
            alipay_url = "https://mapi.alipay.com/gateway.do?_input_charset=utf-8"
            r = requests.post(alipay_url, data=data, headers=headers)
            return r.content
        elif ret["msg"] == "验证码不正确":
            print('登录失败, 验证码错误.')
            print r.status_code, r.content, 111111111111
    return redirect(url_for('admin.order_list'))


@admin.route('/orders/<order_no>/refresh', methods=['GET'])
def order_refresh(order_no):
    order = Order.objects.get(order_no=order_no)
    if order.refresh_status():
        current_app.logger.info("刷新订单成功")
    else:
        current_app.logger.info("刷新订单失败")
    return redirect(url_for('admin.order_list'))


class SubmitOrder(MethodView):
    def get(self):
        contact = {
            "name": "罗军平",
            "phone": "15575101324",
            "idcard": "431021199004165616",
        }
        rider1 = {
            "name": "罗军平",
            "phone": "15575101324",
            "idcard": "431021199004165616",
        }

        line = Line.objects.order_by("full_price")[0]
        kwargs = dict(
            item=None,
            contact=contact,
            rider1=rider1,
            api_url="http://localhost:8000",
            line_id=line.line_id,
            order_price=line.full_price+line.fee,
        )
        return render_template('admin/submit_order.html', **kwargs)

    def post(self):
        fd = request.form
        data = {
            "line_id": fd.get("line_id"),
            "out_order_no": "12345678910",
            "order_price": float(fd.get("order_price")),
            "contact_info": {
                "name": fd.get("contact_name"),
                "telephone": fd.get("contact_phone"),
                "id_type": 1,
                "id_number": fd.get("contact_idcard"),
                "age_level": 1,                                         # 大人 or 小孩
            },
            "rider_info": [
                {                                                       # 乘客信息
                    "name": fd.get("rider1_name"),                      # 名字
                    "telephone": fd.get("rider1_phone"),                # 手机
                    "id_type": 1,                                       # 证件类型
                    "id_number": fd.get("rider1_idcard"),               # 证件号
                    "age_level": 1,                                     # 大人 or 小孩
                },
                {                                                       # 乘客信息
                    "name": fd.get("rider2_name"),                      # 名字
                    "telephone": fd.get("rider2_phone"),                # 手机
                    "id_type": 1,                                       # 证件类型
                    "id_number": fd.get("rider2_idcard"),               # 证件号
                    "age_level": 1,                                     # 大人 or 小孩
                },
            ],
            "locked_return_url": fd.get("lock_url"),
            "issued_return_url": fd.get("issue_url"),
        }

        import copy
        for d in copy.copy(data["rider_info"]):
            if not d["name"]:
                data["rider_info"].remove(d)

        api_url = urllib2.urlparse.urljoin(fd.get("api_url"), "/orders/submit")
        res = requests.post(api_url, data=json.dumps(data))
        print "submit order", res
        return redirect(url_for('admin.order_list'))


admin.add_url_rule("/submit_order", view_func=SubmitOrder.as_view('submit_order'))
